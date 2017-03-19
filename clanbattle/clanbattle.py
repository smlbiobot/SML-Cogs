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
from discord.ext import commands
from discord.ext.commands import Context
from discord import Member
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help

PATH_LIST = ['data', 'clanbattle']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")


class ClanBattle:
    """Clan battle modules for Clash Royale 2v2 mode."""

    def __init__(self, bot):
        """Clan battle module for Clash Royale 2v2 mode."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(aliases=['cb'], pass_context=True, no_pm=True)
    async def clanbattle(self, ctx: Context):
        """Clan Battles."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @clanbattle.command(name="create", pass_context=True, no_pm=True)
    async def clanbattle_create(self, ctx: Context, *members: Member):
        """Create clan battle voice channels.

        Example:
        !clanbattle
        !clanbattle create SML
        !clanbattle create @SML @vin
        """
        server = ctx.message.server
        author = ctx.message.author
        if members is None:
            members = [author]

        vc_name = "CB: {}".format(author.display_name)

        await self.bot.create_channel(
            server, vc_name, type=discord.ChannelType.voice)




def check_folder():
    """check data folder exists and create if needed."""
    if not os.path.exists(PATH):
        print("Creating {} folder".format(PATH))
        os.makedirs(PATH)


def check_file():
    """Check data folder exists and create if needed."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        print("Creating default clanbattle settings.json")
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Add cog to bot."""
    check_folder()
    check_file()
    n = ClanBattle(bot)
    bot.add_cog(n)