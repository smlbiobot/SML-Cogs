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

import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "channelfilter")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ChannelFilter:
    """Channelf filter"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def init_server_settings(self, server):
        self.settings[server.id] = {}
        dataIO.save_json(JSON, self.settings)

    def get_server_settings(self, server):
        """Return server settings."""
        if server.id not in self.settings:
            self.settings[server.id] = {}
            dataIO.save_json(JSON, self.settings)
        return self.settings[server.id]

    def get_channel_settings(self, server, channel):
        """Return channel settings."""
        server_settings = self.get_server_settings(server)
        if channel.id not in server_settings:
            self.settings[server.id][channel.id] = {}
            dataIO.save_json(JSON, self.settings)
        return self.settings[server.id][channel.id]

    def add_word(self, server, channel, word, reason=None):
        """Add word to filter."""
        channel_settings = self.get_channel_settings(server, channel)
        channel_settings[word.lower()] = {
            'reason': reason
        }
        dataIO.save_json(JSON, self.settings)

    def remove_word(self, server, channel, word):
        """Remove word from filter."""
        channel_settings = self.get_channel_settings(server, channel)
        success = channel_settings.pop(word, None)
        dataIO.save_json(JSON, self.settings)
        if success is None:
            return False
        else:
            return True

    @checks.mod_or_permissions()
    @commands.group(pass_context=True, aliases=['cf', 'cfilter'])
    async def channelfilter(self, ctx):
        """Filter words by channel."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.is_owner()
    @channelfilter.command(name="init", pass_context=True)
    async def channelfilter_init(self, ctx):
        """Init server settings."""
        server = ctx.message.server
        self.init_server_settings(server)
        await self.bot.say("Settings initialized.")

    @checks.mod_or_permissions()
    @channelfilter.command(name="add", pass_context=True, no_pm=True)
    async def channelfilter_add(self, ctx, word, reason=None):
        """Add words."""
        server = ctx.message.server
        channel = ctx.message.channel
        self.add_word(server, channel, word, reason=reason)
        await self.bot.say("Added word to filter.")

    @checks.mod_or_permissions()
    @channelfilter.command(name="remove", pass_context=True, no_pm=True)
    async def channelfilter_remove(self, ctx, word):
        """Remove words."""
        server = ctx.message.server
        channel = ctx.message.channel
        success = self.remove_word(server, channel, word)
        if success:
            await self.bot.say("Removed word from filter.")
        else:
            await self.bot.say("Cannot find that word in filter.")

    @checks.mod_or_permissions()
    @channelfilter.command(name="list", pass_context=True, no_pm=True)
    async def channelfilter_list(self, ctx):
        """Words filtered in channel."""
        server = ctx.message.server
        channel = ctx.message.channel
        channel_settings = self.get_channel_settings(server, channel)
        if len(channel_settings.keys()) == 0:
            await self.bot.say("No words are filtered here.")
            return
        await self.bot.say(", ".join(channel_settings.keys()))

    @checks.mod_or_permissions()
    @channelfilter.command(name="listserver", pass_context=True, no_pm=True)
    async def channelfilter_listserver(self, ctx):
        """Words filtered on server."""
        server = ctx.message.server
        server_settings = self.get_server_settings(server)
        out = []
        for channel_id in server_settings:
            channel = self.bot.get_channel(channel_id)
            channel_settings = self.get_channel_settings(server, channel)
            if len(channel_settings):
                out.append("{}: {}".format(channel.mention, ", ".join(channel_settings)))
        if not len(out):
            await self.bot.say("Nothing is filtered on this server.")
            return
        await self.bot.say(", ".join(out))

    async def on_message(self, message):
        """Filter words by channel."""
        server = message.server
        channel = message.channel
        author = message.author
        if server is None or self.bot.user == author:
            return

        valid_user = isinstance(author, discord.Member) and not author.bot

        # Ignore bots
        if not valid_user:
            return

        # Ignore people with manage messages perms
        if author.server_permissions.manage_messages:
            return

        channel_settings = self.get_channel_settings(server, channel)
        if not isinstance(channel_settings, dict):
            return

        for word in channel_settings.keys():
            if word.lower() in message.content.lower():
                reason = channel_settings[word].get('reason', 'that')
                await self.bot.send_message(
                    channel,
                    "{} {}. "
                    "Repeat offenders will be kicked/banned.".format(
                        author.mention,
                        reason
                    ))
                await self.bot.delete_message(message)


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
    n = ChannelFilter(bot)
    bot.add_cog(n)
