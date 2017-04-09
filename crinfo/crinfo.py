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
import io
import os
import pprint
import datetime as dt
import string
import asyncio
from collections import OrderedDict
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
        self.data = {}

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setcrinfo(self, ctx: Context):
        """CRInfo settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcrinfo.command(name="update", pass_context=True, no_pm=True)
    async def setcrinfo_update(self):
        """Update data."""
        await self.update_data()

    async def update_data(self):
        """Update data."""
        self.data["chests"] = {}
        url = urljoin(CSV_LOGIC_BASE, FILES["CHESTS"])
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            chests = {
                k: v for k, v in row.items()
                if k
                in ["Name", "RareChance", "EpicChance", "LegendaryChance"]}
            self.data["chests"][row["Name"]] = chests



        # pp = pprint.pformat(self.data["chests"])
        # print(pp)

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
    async def crinfo_chest(self, ctx: Context, chest_type: str):
        """Clash Royale chests."""
        if "chests" not in self.data:
            await self.update_data()

        await self.bot.say("chest type: {}".format(chest_type))

        if chest_type == "cc":
            await self.bot.say("cc")
            datadict = self.data["chests"]
            data = [
                (k, datadict[k]) for k in datadict
                if k.startswith('Survival_Bronze')]
            # data = [
            #     (k, v) for k, v in self.data["chests"].items()
            #     if k.startswith('Survival_Bronze')]

            for page in pagify(str(data)):
                await self.bot.say(page)
            # await self.bot.say(box(pprint.pformat(data)))


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
