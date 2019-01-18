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

from collections import defaultdict

import aiohttp
import asyncio
import datetime as dt
import discord
import io
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "racf_decks")
JSON = os.path.join(PATH, "settings.json")

DELAY = dt.timedelta(minutes=5).total_seconds()
# DELAY = dt.timedelta(seconds=1).total_seconds()


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
        # print("post_decks")
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
            cards = deck.get('deck_name').split(',')
            player_name = deck.get('player_name', '')
            clan_name = deck.get('clan_name', '')
            ts = deck.get('timestamp_epoch_millis')
            timestamps.append(ts)
            ts_dt = dt.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M UTC")
            cc = deck.get('cc', False)
            gc_star = ':star: ' if fam and not cc else ''
            message = "{}**12-win {} deck by {}**, {}\n{}".format(
                gc_star,
                'CC' if cc else 'GC',
                player_name,
                clan_name,
                ts_dt
            )
            deck_img_name = player_name
            await self.bot.send_message(
                channel,
                message
            )

            deck_image = await self.bot.loop.run_in_executor(
                self.threadex,
                deck_cog.get_deck_image,
                cards, deck_img_name, self.bot.user
            )

            # construct a filename using first three letters of each card
            filename = "deck-{}.png".format("-".join([card[:3] for card in deck]))

            with io.BytesIO() as f:
                deck_image.save(f, "PNG")
                f.seek(0)
                await self.bot.send_file(
                    channel, f,
                    filename=filename, content="")

            await self.bot.send_message(channel, embed=await deck_cog.decklink_embed(cards))

        # store latest timestamp
        if len(decks) != 0:
            max_time = max(timestamps)
            if fam:
                self.settings["family_timestamp"] = max_time
            else:
                self.settings["gc_timestamp"] = max_time
            dataIO.save_json(JSON, self.settings)

    async def update_decks(self):
        while self == self.bot.get_cog("RACFDecks"):
            server = None
            server_id = self.settings.get("server_id")
            if server_id:
                server = self.bot.get_server(server_id)
            if server:
                family_auto = self.settings.get('family_auto')
                family_channel_id = self.settings.get('family_channel_id')
                if family_auto and family_channel_id:
                    channel = discord.utils.get(server.channels, id=family_channel_id)
                    if channel:
                        await self.post_decks(channel, fam=True, show_empty=False)

                gc_auto = self.settings.get('gc_auto')
                gc_channel_id = self.settings.get('gc_channel_id')
                if gc_auto and gc_channel_id:
                    channel = discord.utils.get(server.channels, id=gc_channel_id)
                    if channel:
                        await self.post_decks(channel, fam=False, show_empty=False)

            await asyncio.sleep(DELAY)


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
    bot.loop.create_task(n.update_decks())
