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

import argparse
import itertools
import os
from collections import defaultdict
from random import choice

import discord
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context

PATH = os.path.join("data", "brawlstars")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class BrawlStars:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def bsset(self, ctx):
        """Set Brawl Stars API settings.

        Require https://brawlapi.cf/api
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @bsset.command(name="init", pass_context=True)
    async def bsset_init(self, ctx):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings[server.id] = {}
        if self._save_settings:
            await self.bot.say("Server settings initialized.")

    @bsset.command(name="auth", pass_context=True)
    async def bsset_auth(self, ctx, token):
        """Authorization (token)."""
        self.settings['brawlapi_token'] = token
        if self._save_settings:
            await self.bot.say("Authorization (token) updated.")
        await self.bot.delete_message(ctx.message)


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
    n = BrawlStars(bot)
    bot.add_cog(n)
