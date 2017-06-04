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
from discord.ext import commands

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

import trueskill

PATH = os.path.join("data", "ladder")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "SERIES": {}
}


class Ladder:
    """Ladder ranking system.

    Based on http://www.moserware.com/2010/03/computing-your-skill.html
    http://trueskill.org/

    Reuirements:
    pip install trueskill
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def check_server(self, server):
        """Check server settings."""
        if server.id not in self.settings:
            self.settings[server.id] = SERVER_DEFAULTS
        dataIO.save_json(JSON, self.settings)

    def check_series(self, server, series):
        """Check series settings."""
        self.check_server(server)
        if series in self.settings[server.id]["SERIES"]:
            return self.settings[server.id]["SERIES"][series]
        return None

    def check_player(self, server, player):
        """Check player settings."""
        self.check_server(server)
        if player.id not in self.settings[server.id]:
            self.settings[server.id][player.id] = {
                "ratings": [],
                "matches": []
            }
        dataIO.save_json(JSON, self.settings)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def setladder(self, ctx):
        """Set ladder settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setladder.command(name="create", pass_context=True)
    async def setladder_create(self, ctx, name, *players: discord.Member):
        """Create a new series.

        Creates a new ladder series and initialize with players.
        """
        server = ctx.message.server
        if self.check_series(server, name) is not None:
            await self.bot.say("{} already exists.".format(name))
            return
        self.settings[server.id]["SERIES"][name] = {
            "players": list(set([m.id for m in players])),
            "matches": [],
            "id": len(self.settings[server.id]["SERIES"])
        }
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Create new series named: {}\n"
            "with players: {}".format(
                name,
                ", ".join([m.display_name for m in players])))

    @setladder.command(name="addplayers", pass_context=True)
    async def setladder_addplayers(self, ctx, name, *players: discord.Member):
        """Add players to an existing series."""
        server = ctx.message.server
        if self.check_series(server, name) is None:
            await self.bot.say("{} does not exist.".format(name))
            return
        series = self.settings[server.id]["SERIES"][name]
        for player in players:
            if player is not None:
                if player.id in series["players"]:
                    await self.bot.say(
                        "{} is already a registered player.".format(
                            player.display_name))
                else:
                    series["players"].append(player.id)
                    await self.bot.say(
                        "Added {} to {}.".format(player.display_name, name))
        dataIO.save_json(JSON, self.settings)


    @commands.group(pass_context=True)
    async def ladder(self, ctx):
        """Ladder anking system using TrueSkills."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @ladder.command(name="register", pass_context=True)
    async def ladder_register(self, ctx):
        """Allow player to self-register to system."""
        server = ctx.message.server
        author = ctx.message.author
        self.check_player(server, author)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = Ladder(bot)
    bot.add_cog(n)

