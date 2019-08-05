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

import io
import json
import os
from collections import defaultdict
import discord

from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "sml")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class SML:
    """SML utilities"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @checks.is_owner()
    @commands.group(pass_context=True)
    async def sml(self, ctx):
        """SML"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @sml.command(name="copypin", pass_context=True, no_pm=True)
    async def sml_copypin(self, ctx):
        """Copy pinned messages from this channel."""
        channel = ctx.message.channel
        messages = await self.bot.pins_from(channel)
        message_dicts = []
        for message in messages:
            message_dicts.append({
                "timestamp": message.timestamp.isoformat(),
                "author_id": message.author.id,
                "author_name": message.author.name,
                "content": message.content,
                "emebeds": message.embeds,
                "channel_id": message.channel.id,
                "channel_name": message.channel.name,
                "server_id": message.server.id,
                "server_name": message.server.name,
                "mention_everyone": message.mention_everyone,
                "mentions_id": [m.id for m in message.mentions],
                "mentions_name": [m.name for m in message.mentions]
            })

        filename = "pinned_messages.json"
        with io.StringIO() as f:
            json.dump(message_dicts, f, indent=4)
            f.seek(0)
            await ctx.bot.send_file(
                channel,
                f,
                filename=filename
            )

    @commands.command(pass_context=True)
    async def somecog(self, ctx, *args):
        if not args:
            await self.bot.say(1)
        elif args[0] == 'help':
            if len(args) == 1:
                await self.bot.say(2)
            elif args[1] == 'this':
                await self.bot.say(3)

    @commands.command(pass_context=True)
    async def testinlinelink(self, ctx):
        desc = "[`inline block`](http://google.com)"
        em = discord.Embed(
            title="Test",
            description=desc
        )
        await self.bot.say(embed=em)




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
    n = SML(bot)
    bot.add_cog(n)
