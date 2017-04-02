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

import os
import datetime as dt
import asyncio
from datetime import timedelta

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

from cogs.deck import Deck
from collections import namedtuple

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

PATH = os.path.join("data", "crdata")
SETTINGS_JSON = os.path.join(PATH, "settings.json")
CR_JSON = os.path.join(PATH, "clashroyale.json")
CARDPOP_FILE = "cardpop-%Y-%m-%d.json"

DATA_UPDATE_INTERVAL = timedelta(days=1).seconds

class CRData:
    """Clash Royale card popularity using Starfi.re"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(SETTINGS_JSON)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        """Loop task: update data daily."""
        await self.bot.wait_until_ready()
        await self.updatedata()
        await asyncio.sleep(DATA_UPDATE_INTERVAL)
        if self is self.bot.get_cog('CRData'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setcrdata(self, ctx: Context):
        """Set Clash Royale Data settings.

        Require: Starfire access permission.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcrdata.command(name="username", pass_context=True)
    async def setcrdata_username(self, ctx: Context, username):
        """Set Starfire username."""
        self.settings["STARFIRE_USERNAME"] = username
        await self.bot.say("Starfire username saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="password", pass_context=True)
    async def setcrdata_password(self, ctx: Context, password):
        """Set Starfire username."""
        self.settings["STARFIRE_PASSWORD"] = password
        await self.bot.say("Starfire password saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="url", pass_context=True)
    async def setcrdata_url(self, ctx: Context, url):
        """Set Starfire url."""
        self.settings["STARFIRE_URL"] = url
        await self.bot.say("Starfire URL saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="update", pass_context=True)
    async def setcrdata_update(self, ctx):
        """Grab data from Starfire if does not exist."""
        file = await self.update_data()
        if file is not None:
            await self.bot.say("Saved {}.".format(file))
        else:
            await self.bot.say("Today’s data already downloaded.")

    async def update_data(self):
        """Grab data from URL."""
        today = dt.date.today()
        today_file = today.strftime(CARDPOP_FILE)
        today_path = os.path.join(PATH, today_file)
        if not os.path.exists(today_path):
            url = self.settings["STARFIRE_URL"]
            session = aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(
                    login=self.settings["STARFIRE_USERNAME"],
                    password=self.settings["STARFIRE_PASSWORD"]))
            resp = await session.get(url)
            data = await resp.json()
            dataIO.save_json(today_path, data)
            return today_file
        return None

    def get_today_data(self):
        """Return today’s data."""
        today = dt.date.today()
        return self.get_data(today)

    def get_data(self, date):
        """Get data as json by date."""
        file = date.strftime(CARDPOP_FILE)
        path = os.path.join(PATH, file)
        if os.path.exists(path):
            return dataIO.load_json(path)
        return None


def check_folder():
    if not os.path.exists(PATH):
        os.makedirs(PATH)

def check_file():
    defaults = {}
    if not dataIO.is_valid_json(SETTINGS_JSON):
        dataIO.save_json(SETTINGS_JSON, defaults)

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(CRData(bot))
