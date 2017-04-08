# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2017 SML

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
import csv
import os
import datetime as dt
import string
import asyncio
import pprint
from datetime import timedelta
from urllib.parse import urljoin

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

from collections import namedtuple

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

try:
    import pandas
except ImportError:
    raise ImportError("Please install the pandas package.") from None

PATH = os.path.join("data", "crinfo")
SETTINGS_JSON = os.path.join(PATH, "settings.json")
CLASHROYALE_JSON = os.path.join(PATH, "clashroyale.json")
CSV_LOGIC_BASE = (
    "https://raw.githubusercontent.com/smlbiobot"
    "/cr/master/apk/1.8.2/com.supercell.clashroyale-1.8.2-decoded"
    "/assets/csv_logic/")
FILES = {
    "CHESTS": "treasure_chests.decoded.csv"
}


class CRInfo:
    """Clash Royale data on cards and chests."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(SETTINGS_JSON)
        self.clashroyale = dataIO.load_json(CLASHROYALE_JSON)


    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setcrinfo(self, ctx: Context):
        """CRInfo settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcrinfo.command(name="update", pass_context=True, no_pm=True)
    async def setcrinfo_update(self):
        """Load and return data according to key."""
        url = (
            "https://raw.githubusercontent.com/smlbiobot"
            "/cr/master/apk/1.8.2/com.supercell.clashroyale-1.8.2-decoded"
            "/assets/csv_logic/"
            "treasure_chests.decoded.csv")

        conn = aiohttp.TCPConnector()
        session = aiohttp.ClientSession(connector=conn)
        async with session.get(url) as r:
            text = await r.text()
        session.close()

        dr = csv.DictReader(text)
        for i, row in enumerate(dr):
            out = []
            out.append(str(i))
            for k, v in row.items():
                out.append('{}: {}'.format(k, v))
            print(' | '.join(out))

    @commands.group(pass_context=True, no_pm=True)
    async def crinfo(self, ctx: Context):
        """Clash Royale Stats."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crinfo.command(name="card", pass_context=True, no_pm=True)
    async def crinfo_card(self, ctx: Context):
        """Clash Royale cards."""
        url = urljoin(CSV_LOGIC_BASE, FILES["CHESTS"])
        await self.bot.say(url)

    @crinfo.command(name="chest", pass_context=True, no_pm=True)
    async def crinfo_chest(self, ctx: Context):
        """Clash Royale chests."""
        url = urljoin(CSV_LOGIC_BASE, FILES["CHESTS"])
        await self.bot.say(url)





def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)

def check_file():
    """Check settings."""
    defaults = {}
    if not dataIO.is_valid_json(SETTINGS_JSON):
        dataIO.save_json(SETTINGS_JSON, defaults)

def setup(bot):
    """Setup cog."""
    check_folder()
    check_file()
    bot.add_cog(CRInfo(bot))
