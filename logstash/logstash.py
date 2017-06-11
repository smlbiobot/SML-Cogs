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
import re
import uuid
import logging
import logstash

from discord import Message
from discord import Member
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context
from cogs.utils.dataIO import dataIO

from cogs.utils import checks

from __main__ import send_cmd_help

HOST = 'localhost'
PORT = 5959
DB_PATH = os.path.join('data', 'logstash', 'logstash.db')

PATH = os.path.join('data', 'logstash')
JSON = os.path.join(PATH, 'settings.json')

EMOJI_P = re.compile('\<\:.+?\:\d+\>')
UEMOJI_P = re.compile(u'['
                      u'\U0001F300-\U0001F64F'
                      u'\U0001F680-\U0001F6FF'
                      u'\uD83C-\uDBFF\uDC00-\uDFFF'
                      u'\u2600-\u26FF\u2700-\u27BF]{1,2}',
                      re.UNICODE)


class Logstash:
    """Send activity of Discord using Google Analytics."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

        self.logger = logging.getLogger('discord.logger')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(
            logstash.LogstashHandler(
                HOST, PORT, version=1))
        self.logger.info('discord.logger: Logstash cog init')

    def get_message_sca(self, message: Message):
        """Return server, channel and author from message."""
        return message.server, message.channel, message.author

    def get_extra_sca(self, message: Message):
        """Return extra fields from messages."""
        server, channel, author = self.get_message_sca(message)

        # list roles in server hiearchy
        roles = [r for r in server.role_hierarchy if r in author.roles]
        role_names = [r.name for r in roles if not r.is_everyone]
        role_ids = [r.id for r in roles if not r.is_everyone]

        return {
            'author_id': author.id,
            'author_name': author.display_name,
            'server_id': server.id,
            'server_name': server.name,
            'channel_id': channel.id,
            'channel_name': channel.name,
            'role_ids': role_ids,
            'role_names': role_names
        }

    def get_extra_mentions(self, message: Message):
        """Return mentions in message."""
        mentions = set(message.mentions.copy())
        names = [m.display_name for m in mentions]
        ids = [m.id for m in mentions]
        return {
            'mention_names': names,
            'mention_ids': ids
        }

    def get_extra_emojis(self, message: Message):
        """Return list of emojis used in messages."""
        emojis = EMOJI_P.findall(message.content)
        emojis.append(UEMOJI_P.findall(message.content))
        return {
            'emojis': emojis
        }

    def get_event_key(self, name: str):
        """Return event name used in logger."""
        return "discord.logger.{}".format(name)

    async def on_message(self, message: Message):
        """Track on message."""
        event_key = "message"
        extra = {
            'discord_event': event_key
        }
        extra.update(self.get_extra_sca(message))
        extra.update(self.get_extra_mentions(message))
        extra.update(self.get_extra_emojis(message))
        self.logger.info(self.get_event_key(event_key), extra=extra)

    async def on_command(self, command: Command, ctx: Context):
        """Track command usage."""
        self.log_command(command, ctx)

    def log_command(self, command, ctx):
        """Log bot commands."""
        server = ctx.message.server
        author = ctx.message.author
        channel = ctx.message.channel

        extra = {
            'discord_event': "command",
            'author_id': author.id,
            'author_name': author.display_name,
            'server_id': server.id,
            'server_name': server.name,
            'channel_id': channel.id,
            'channel_name': channel.name,
            'command_name': command.name
        }
        self.logger.info('discord.logger.command', extra=extra)


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
    n = Logstash(bot)
    bot.add_cog(n)
