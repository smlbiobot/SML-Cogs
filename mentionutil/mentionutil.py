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

import argparse
import itertools
import os
from collections import defaultdict
from random import choice

import discord
from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context
from box import Box, BoxList

PATH = os.path.join("data", "mentionutil")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class MentionUtil:
    """Control mentioning utility."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Box(dataIO.load_json(JSON), default_box=True)

    def save(self):
        """Save settings."""
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    async def mentionutilset(self, ctx):
        """Mention Utility settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @mentionutilset.command(name="add", aliases=['a'], pass_context=True, no_pm=True)
    async def mentionutilset_add(self, ctx, member: discord.Member):
        """Add a user."""
        if member is None:
            await send_cmd_help(ctx)
            return

        if self.settings.mentionblock.users == Box():
            self.settings.mentionblock.users = BoxList()
        self.settings.mentionblock.users.append(member)
        await self.bot.say("User added.")
        self.save()


    @mentionutilset.command(name="remove", aliases=['rm', 'r'], pass_context=True, no_pm=True)
    async def mentionutilset_remove(self, ctx, member: discord.Member):
        """Add a user."""
        if member is None:
            await send_cmd_help(ctx)
            return

        if self.settings.mentionblock.users == Box():
            self.settings.mentionblock.users = BoxList()
        self.settings.mentionblock.users.remove(member)
        await self.bot.say("User removed.")
        self.save()




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
    n = MentionUtil(bot)
    bot.add_cog(n)
