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
import csv
import datetime as dt
import io
import os
import yaml
from addict import Dict
from discord.ext import commands

from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "trade")
JSON = os.path.join(PATH, "settings.json")
CARDS_AKA_YML_URL = 'https://raw.githubusercontent.com/smlbiobot/SML-Cogs/master/deck/data/cards_aka.yaml'


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    return t


class Settings(Dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self):
        dataIO.save_json(JSON, self.to_dict())

    def add_card(self, server_id, author_id, give_card=None, get_card=None, clan_tag=None):
        if not self[server_id].trades:
            self[server_id].trades = []

        self[server_id].trades.append(dict(
            author_id=author_id,
            give=give_card,
            get=get_card,
            clan_tag=clan_tag,
            timestamp=dt.datetime.utcnow().timestamp()
        ))

        self.save()


class Trade:
    """Clash Royale Trading"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Settings(dataIO.load_json(JSON))
        self._cards_aka = None
        self._aka_to_card = None

    async def get_cards_aka(self):
        if self._cards_aka is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(CARDS_AKA_YML_URL) as resp:
                    data = await resp.read()
                    self._cards_aka = yaml.load(data)
        return self._cards_aka

    async def aka_to_card(self, abbreviation):
        """Go through all abbreviation to find card dict"""
        if self._aka_to_card is None:
            akas = await self.get_cards_aka()
            self._aka_to_card = dict()
            for k, v in akas.items():
                self._aka_to_card[k] = k
                for item in v:
                    self._aka_to_card[item] = k
        return self._aka_to_card.get(abbreviation)

    @commands.group(name="trade", pass_context=True)
    async def trade(self, ctx):
        """Clash Royale trades."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @trade.command(name="add", aliases=['a'], pass_context=True)
    async def add_trade(self, ctx, give: str, get: str, clan_tag: str):
        """Add a trade. Can use card shorthand"""
        server = ctx.message.server
        author = ctx.message.author

        give_card = await self.aka_to_card(give)
        get_card = await self.aka_to_card(get)
        clan_tag = clean_tag(clan_tag)
        self.settings.add_card(server.id, author.id, give_card, get_card, clan_tag)
        self.settings.save()
        await self.bot.say(
            "Give: {give_card}, Get: {get_card}, {clan_tag}".format(
                give_card=give_card,
                get_card=get_card,
                clan_tag=clan_tag,
            )
        )

    @trade.command(name="import", aliases=['i'], pass_context=True)
    async def import_trade(self, ctx):
        """Import list of trades from CSV file.

        First row is header:
        give,get,clan_tag
        """
        if len(ctx.message.attachments) == 0:
            await self.bot.say(
                "Please attach CSV with this command. "
            )
            return

        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()

        reader = csv.DictReader(io.StringIO(data))

        def get_field(row, field, is_card=False, is_clan_tag=False):
            s = row.get(field)
            v = None
            if s is None:
                return None
            if is_card:
                s = s.lower().replace(' ', '-')
                v = self.aka_to_card(s)
            elif is_clan_tag:
                v = clean_tag(s)
            return v

        dicts = []

        for row in reader:
            # normalize string
            give_card = get_field(row, 'give', is_card=True)
            get_card = get_field(row, 'get', is_card=True)
            clan_tag = get_field(row, 'clan_tag', is_clan_tag=True)
            dicts.append(dict(
                give_card=give_card,
                get_card=get_card,
                clan_tag=clan_tag
            ))

        server = ctx.message.server
        author = ctx.message.author
        for d in dicts:
            self.settings.add_card(server.id, author.id, **d)

        self.settings.save()

        o = ["Give: {give_card}, Get: {get_card}, {clan_tag}".format(**d) for d in dicts]
        for page in pagify("\n".join(o)):
            await self.bot.say(page)


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
    n = Trade(bot)
    bot.add_cog(n)
