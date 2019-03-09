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

from collections import defaultdict

import discord
import os
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

import re

PATH = os.path.join("data", "channelallow")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ChannelAlow:
    """Remove messages that don’t contain specific text or regex in channel."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def check_server(self, server):
        if server.id not in self.settings:
            self.settings[server.id] = {}
            dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    @checks.mod_or_permissions()
    async def channelallow(self, ctx):
        """channeel allow settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help()

    @channelallow.command(name="add", pass_context=True)
    @checks.mod_or_permissions()
    async def add(self, ctx, regex, channel: discord.Channel = None):
        """Add regex to channel"""
        if channel is None:
            channel = ctx.message.channel

        server = ctx.messge.server
        self.check_server(server)

        self.settings[server.id][channel.id] = regex
        dataIO.save_json(JSON, self.settings)

    @channelallow.command(name="remove", pass_context=True, aliases=["rm", "del"])
    @checks.mod_or_permissions()
    async def remove(self, ctx, channel: discord.Channel = None):
        """Remove rules from channel"""
        if channel is None:
            channel = ctx.message.channel

        server = ctx.message.server
        self.check_server(server)

        self.settings[server.id].pop(channel.id, None)
        dataIO.save_json(JSON, self.settings)

    async def on_message(self, msg):
        """Handle messages.

        For testing, only run on specific channels
        """

        # if not self == self.bot.get_cog("ChannelAllow"):
        #     return

        s = dict(
            friendlink=dict(
                regex='https://link.clashroyale.com/invite/friend/..\?tag=([A-Z0-9]+)&token=([a-z0-9]+)&platform=([A-Za-z0-9]+)',
                channel_ids=[
                    # '553917858694823954',  # rr-test2
                    '550405517223395338',  # friendlinks on racf
                ]
            )
        )
        if msg.channel.id not in s['friendlink']['channel_ids']:
            return

        # ignore bots
        if msg.author.bot:
            return

        for k, v in s.items():
            if msg.channel.id in v.get('channel_ids'):
                m = re.search(v.get('regex'),  msg.content)
                if not m:
                    await self.bot.delete_message(msg)
                    return

        #
        # server = msg.server
        # if server not in self.settings:
        #     return
        #
        # channel = msg.channel
        # self.check_server(server)
        # if channel.id not in self.settings[server.id]:
        #     return
        #
        # regex = self.settings[server.id][channel.id]
        # if not regex:
        #     return


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
    n = ChannelAlow(bot)
    bot.add_cog(n)
