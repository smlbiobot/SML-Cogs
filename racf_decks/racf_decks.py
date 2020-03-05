"""
The MIT License (MIT)

Copyright (c) 2018 SML

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import asyncio
import datetime as dt
import os
import socket
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

import logging

PATH = os.path.join("data", "racf_decks")
JSON = os.path.join(PATH, "settings.json")

DELAY = dt.timedelta(minutes=5).total_seconds()
# DELAY = dt.timedelta(minutes=1).total_seconds()
DEBUG = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug(*args):
    if DEBUG:
        print(*args)

def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


async def fetch_decks(time=None, fam=True, auth=None, cc=False):
    conn = aiohttp.TCPConnector(
        family=socket.AF_INET,
        verify_ssl=False,
    )

    if fam:
        if cc:
            url = 'https://royaleapi.com/bot/cc/fam?auth={}'.format(auth)
        else:
            url = 'https://royaleapi.com/bot/gc/fam?auth={}'.format(auth)
    else:
        url = 'https://royaleapi.com/bot/gc?auth={}'.format(auth)

    if time is not None:
        url = '{}&t={}'.format(url, time)

    data = None

    async with aiohttp.ClientSession(connector=conn) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()

    if data is None:
        return []

    total = data.get('hits', {}).get('total')
    if total == 0:
        return []

    decks = []
    hits = data.get('hits', {}).get('hits')

    for hit in hits:
        _source = hit.get('_source')
        team = _source.get('team')[0]
        deck = dict(
            timestamp_epoch_millis=_source.get('battleTime_timestamp_epoch_millis', 0),
            deck_name=team.get('deck', {}).get('name'),
            player_name=team.get('name'),
            player_tag=team.get('tag'),
            clan_name=team.get('clan', {}).get('name', ''),
            cc=cc
        )
        decks.append(deck)

    decks = sorted(decks, key=lambda x: x['timestamp_epoch_millis'])

    return decks


class RACFDecks:
    """RACF GC decks"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.task = None
        self.threadex = ThreadPoolExecutor(max_workers=2)

        self.loop = asyncio.get_event_loop()
        self.task = self.loop.create_task(self.update_decks())

    def __unload(self):
        """Remove task when unloaded."""
        try:
            self.task.cancel()
        except Exception:
            pass

    @checks.mod_or_permissions()
    @commands.command(no_pm=True, pass_context=True)
    async def rdecks_reset_timestamp(self, ctx):
        self.settings["family_timestamp"] = 1545709664
        await self.bot.say("Reset family decks timestamp")

    @checks.mod_or_permissions()
    @commands.command(aliases=['rdecks', 'rdeck'], no_pm=True, pass_context=True)
    async def racf_decks(self, ctx):
        """Auto-fetch 12-win GC decks in channel."""
        self.settings["server_id"] = ctx.message.server.id
        self.settings["family_auto"] = True
        self.settings["family_channel_id"] = ctx.message.channel.id
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Automatically sending 12-win family decks to this channel.")
        # await self.post_decks(ctx, fam=True, show_empty=True)

    @checks.mod_or_permissions()
    @commands.command(no_pm=True, pass_context=True)
    async def stoprdecks(self, ctx):
        """Stop auto fetch"""
        self.settings["family_auto"] = False
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Stopped automatic deck fetch.")

    @checks.admin()
    @commands.command(aliases=['rdeckauth'], no_pm=True, pass_context=True)
    async def rdeck_auth(self, ctx, token):
        """Auto-fetch 12-win GC decks in channel."""
        self.settings["auth"] = token
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Saved token")

    @checks.mod_or_permissions()
    @commands.command(aliases=['gcdecks'], no_pm=True, pass_context=True)
    async def gc_decks(self, ctx):
        """Auto-fetch 12-win GC decks in channel."""
        self.settings["server_id"] = ctx.message.server.id
        self.settings["gc_auto"] = True
        self.settings["gc_channel_id"] = ctx.message.channel.id
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Automatically sending 12-win GC decks to this channel.")
        # await self.post_decks(ctx, fam=False, show_empty=True)

    @checks.mod_or_permissions()
    @commands.command(no_pm=True, pass_context=True)
    async def stopgcdecks(self, ctx):
        """Stop auto fetch"""
        self.settings["gc_auto"] = False
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Stopped automatic deck fetch.")

    async def post_decks(self, channel: discord.Channel, show_empty=True, fam=True):
        if fam:
            time = self.settings.get('family_timestamp')
        else:
            time = self.settings.get('gc_timestamp')

        gc_decks = await fetch_decks(time=time, fam=fam, auth=self.settings['auth'])

        cc_decks = []
        if fam:
            cc_decks = await fetch_decks(time=time, fam=fam, auth=self.settings['auth'], cc=True)

        decks = gc_decks + cc_decks

        deck_cog = self.bot.get_cog("Deck")
        timestamps = []

        if len(decks) == 0 and show_empty:
            await self.bot.send_message(channel, "No more decks found.")

        for deck in decks:
            card_keys = deck.get('deck_name').split(',')
            player_name = deck.get('player_name', '')
            player_tag = deck.get('player_tag')
            clan_name = deck.get('clan_name', '')
            ts = deck.get('timestamp_epoch_millis')
            timestamps.append(ts)
            cc = deck.get('cc', False)

            if cc:
                color = discord.Color.green()
            else:
                color = discord.Color.gold()

            try:
                if cc:
                    link = 'https://royaleapi.com/decks/winner/cc'
                else:
                    link = 'https://royaleapi.com/decks/winner/gc'
                await deck_cog.post_deck(
                    channel=channel,
                    title="12-win {} deck".format('CC' if cc else 'GC'),
                    description="**{}**, {}".format(player_name, clan_name),
                    card_keys=card_keys,
                    deck_author=player_name,
                    timestamp=dt.datetime.utcfromtimestamp(ts / 1000),
                    color=color,
                    player_tag=player_tag,
                    link=link
                )
            except discord.DiscordException as e:
                print(e)

        # store latest timestamp
        if len(decks) != 0:
            max_time = max(timestamps)
            if fam:
                self.settings["family_timestamp"] = max_time
            else:
                self.settings["gc_timestamp"] = max_time
            dataIO.save_json(JSON, self.settings)

        logger.info("Posted {count} decks to {channel}".format(count=len(decks), channel=channel.name))

    async def update_decks(self):
        try:
            if self == self.bot.get_cog("RACFDecks"):
                while True:
                    debug("RACF DECKS: update decks")

                    server = None
                    server_id = self.settings.get("server_id")

                    debug("RACF DECKS: update decks server_id:", server_id)

                    if server_id:
                        server = self.bot.get_server(server_id)

                    debug("RACF DECKS: update decks server:", server)
                    if server:
                        try:
                            tasks = []
                            family_auto = self.settings.get('family_auto')
                            family_channel_id = self.settings.get('family_channel_id')
                            if family_auto and family_channel_id:
                                channel = discord.utils.get(server.channels, id=family_channel_id)
                                if channel:
                                    # self.loop.create_task(
                                    #     self.post_decks(channel, fam=True, show_empty=False)
                                    # )
                                    # await self.post_decks(channel, fam=True, show_empty=False)
                                    tasks.append(
                                        self.post_decks(channel, fam=True, show_empty=False)
                                    )

                            gc_auto = self.settings.get('gc_auto')
                            gc_channel_id = self.settings.get('gc_channel_id')
                            if gc_auto and gc_channel_id:
                                channel = discord.utils.get(server.channels, id=gc_channel_id)
                                if channel:
                                    # self.loop.create_task(
                                    #     self.post_decks(channel, fam=False, show_empty=False)
                                    # )
                                    # await self.post_decks(channel, fam=False, show_empty=False)
                                    tasks.append(
                                        self.post_decks(channel, fam=False, show_empty=False)
                                    )

                        except discord.DiscordException as e:
                            print(e)
                        else:
                            debug("RACF DECKS: Task Length: {}".format(len(tasks)))
                            await asyncio.gather(*tasks, return_exceptions=True)
                            debug("RACF DECKS: Gather done")


                    # await asyncio.sleep(3)
                    await asyncio.sleep(DELAY)
        except asyncio.CancelledError:
            pass


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = RACFDecks(bot)
    bot.add_cog(n)
