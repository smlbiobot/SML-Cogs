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
from collections import defaultdict

from __main__ import send_cmd_help
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "quotes")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Quotes:
    """Quotes Manager."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(aliases=['qs'], pass_context=True, no_pm=True)
    async def quoteset(self, ctx):
        """Quotes."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @quoteset.command(name="add", aliases=['a'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def quoteset_add(self, ctx, name, *, quote):
        """Add a quote."""
        server = ctx.message.server
        try:
            if name in self.settings[server.id]:
                await self.bot.say(
                    '{} already exists. Use edit to edit the quote.'.format(
                        name
                    )
                )
                return
        except KeyError:
            pass

        self.settings[server.id][name] = quote
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Quote saved.")

    @quoteset.command(name="edit", aliases=['e'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def quoteset_edit(self, ctx, name, *, quote):
        """Edit a quote."""
        server = ctx.message.server
        self.settings[server.id][name] = quote
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Quote saved.")

    @quoteset.command(name="remove", aliases=['r', 'rm'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def quoteset_remove(self, ctx, name):
        """Remove a quote."""
        server = ctx.message.server
        q = self.settings[server.id].pop(name, None)
        if q is None:
            await self.bot.say("That name does not exist")
            return
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Quote removed.")

    @quoteset.command(name="list", aliases=['l'], pass_context=True, no_pm=True)
    async def quoteset_list(self, ctx):
        """List all the quotes."""
        server = ctx.message.server

        try:
            qs = [k for k, v in self.settings[server.id].items()]
        except KeyError:
            await self.bot.say("No quotes found on this server.")
            return

        for page in pagify(', '.join(qs)):
            await self.bot.say(page)

    @commands.command(aliases=['q'], pass_context=True, no_pm=True)
    async def quote(self, ctx, name):
        """Show quotes by name."""
        server = ctx.message.server
        try:
            q = self.settings[server.id].get(name, None)
            if q is not None:
                await self.bot.say(q)
                return
        except KeyError:
            pass
        await self.bot.say("Cannot find any quotes under that name.")


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = Quotes(bot)
    bot.add_cog(n)
