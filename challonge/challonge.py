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

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

try:
    import challonge
except ImportError:
    raise ImportError("Please install the challonge package from https://github.com/russ-/pychallonge.") from None

PATH = os.path.join("data", "challonge")
JSON = os.path.join(PATH, "settings.json")


class Challonge:
    """Challonge API."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(pass_context=True, no_pm=True)
    async def setchallonge(self, ctx: Context):
        """Set challonge settings.

        http://api.challonge.com/v1"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setchallonge.command(name="username", pass_context=True)
    async def setchallonge_username(self, ctx: Context, username: str):
        """Set challonge username."""
        server = ctx.message.server
        author = ctx.message.author
        self.check_server_settings(server)
        if username is None:
            await send_cmd_help(ctx)
            return
        if author.id not in self.settings[server.id]:
            self.settings[server.id][author.id] = {}
        self.settings[server.id][author.id]["API_USERNAME"] = username
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Challonge API username saved.")

    @setchallonge.command(name="apikey", pass_context=True)
    async def setchallonge_apikey(self, ctx: Context, apikey: str):
        """Set challonge username."""
        server = ctx.message.server
        author = ctx.message.author
        self.check_server_settings(server)
        if apikey is None:
            await send_cmd_help(ctx)
            return
        if author.id not in self.settings[server.id]:
            self.settings[server.id][author.id] = {}
        self.settings[server.id][author.id]["API_KEY"] = apikey
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Challonge API Key saved.")

    def setchallonge_init(self, server, user):
        """Init Challonge api."""
        settings = self.settings[server.id][user.id]
        challonge.set_credentials(
            settings["API_USERNAME"],
            settings["API_KEY"])

    @commands.group(pass_context=True, no_pm=True)
    async def challonge(self, ctx: Context):
        """Challonge API access."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @challonge.command(name="create", pass_context=True)
    async def challonge_create(
            self, ctx: Context,
            name, url, tournament_type="single elimination"):
        """Create new tournament."""
        author = ctx.message.author
        server = ctx.message.server
        self.check_server_settings(server)
        if not self.check_user_credentials(server, author):
            await self.bot.say(
                "Use !setchallonge to set your api credentials.")
            return
        self.setchallonge_init(server, author)
        settings = self.settings[server.id][author.id]
        if "TOUNAMENTS" not in settings:
            settings["TOURNAMENTS"] = {}
        try:
            t = challonge.tournaments.create(name, url, tournament_type)
            settings["TOURNAMENTS"][t["id"]] = {
                "id": t["id"],
                "name": t["name"],
                "url": t["url"],
                "full-challonge-url": t["full-challonge-url"]
            }
            s = settings["TOURNAMENTS"][t["id"]]
            out = ["{}: {}".format(k, v) for k, v in s.items()]
            await self.bot.say("\n".join(out))
            dataIO.save_json(JSON, self.settings)
        except challonge.api.ChallongeException as e:
            await self.bot.say(e)

    def check_server_settings(self, server: discord.Server):
        """Add server to settings if it does not exist."""
        if server.id not in self.settings:
            self.settings[server.id] = {}
            dataIO.save_json(JSON, self.settings)

    def check_user_credentials(
            self, server: discord.Server, user: discord.Member):
        """Check author has set credentials."""
        if user.id not in self.settings[server.id]:
            return False
        settings = self.settings[server.id][user.id]
        if "API_USERNAME" not in settings:
            return False
        if "API_KEY" not in settings:
            return False
        return True


def check_folder():
    if not os.path.exists(PATH):
        os.makedirs(PATH)

def check_file():
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(Challonge(bot))