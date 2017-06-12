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
import asyncio

from discord import Message
from discord import Member
from discord import Server
from discord import ChannelType
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context
from cogs.utils.dataIO import dataIO

from cogs.utils import checks

from __main__ import send_cmd_help

HOST = 'localhost'
PORT = 5959
INTERVAL = 3600
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
        self.extra = {}
        self.task = bot.loop.create_task(self.loop_task())

        self.handler = logstash.LogstashHandler(HOST, PORT, version=1)

        self.logger = logging.getLogger('discord.logger')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.info('discord.logger: Logstash cog init')

    def __unload__(self):
        """Unhook logger when unloaded.

        Thanks Kowlin!
        """
        self.logger.removeHandler(self.handler)


    async def loop_task(self):
        """Loop task."""
        await self.bot.wait_until_ready()
        self.extra = {
            'log_type': 'discord.logger',
            'application': 'red',
            'bot_id': self.bot.user.id,
            'bot_name': self.bot.user.name
        }
        self.log_all()
        await asyncio.sleep(INTERVAL)
        if self is self.bot.get_cog('Logstash'):
            self.task = self.bot.loop.create_task(self.loop_task())

    def get_message_sca(self, message: Message):
        """Return server, channel and author from message."""
        return message.server, message.channel, message.author

    def get_extra_sca(self, message: Message):
        """Return extra fields from messages."""
        server, channel, author = self.get_message_sca(message)

        extra = {
            'author_id': author.id,
            'author_name': author.display_name,
            'server_id': server.id,
            'server_name': server.name,
            'channel_id': channel.id,
            'channel_name': channel.name
        }

        # message sometimes reference a user and has no roles info
        if hasattr(author, 'roles'):
            # list roles in server hiearchy
            roles = [r for r in server.role_hierarchy if r in author.roles]
            role_names = [r.name for r in roles if not r.is_everyone]
            role_ids = [r.id for r in roles if not r.is_everyone]
            extra.update({
                'role_ids': role_ids,
                'role_names': role_names
            })

        return extra

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
        emojis = []
        emojis.append(EMOJI_P.findall(message.content))
        emojis.append(UEMOJI_P.findall(message.content))
        return {
            'emojis': emojis
        }

    def get_event_key(self, name: str):
        """Return event name used in logger."""
        return "discord.logger.{}".format(name)

    async def on_message(self, message: Message):
        """Track on message."""
        self.log_message(message)

    def log_message(self, message: Message):
        """Log message."""
        if not self.extra:
            return
        extra = self.extra.copy()
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
        if not self.extra:
            return
        extra = self.extra.copy()
        event_key = "command"
        extra = {
            'discord_event': event_key,
            'command_name': command.name
        }
        extra.update(self.get_extra_sca(ctx.message))
        self.logger.info(self.get_event_key(event_key), extra=extra)

    async def on_ready(self):
        """Bot ready."""
        self.log_all()

    async def on_resume(self):
        """Bot resume."""
        self.log_all()

    def log_all(self):
        """Log all gauge values."""
        self.log_servers()
        self.log_channels()
        self.log_members()
        self.log_voice()
        self.log_players()
        self.log_uptime()
        self.log_roles()

    def log_servers(self):
        """Log servers."""
        if not self.extra:
            return
        event_key = 'servers'
        extra = self.extra.copy()
        servers = list(self.bot.servers)
        extra.update({
            'discord_gauge': event_key,
            # 'server_names': [s.name for s in servers],
            # 'server_ids': [s.id for s in servers],
            'server_count': len(servers)
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_channels(self):
        """Log channels."""
        if not self.extra:
            return
        channels = list(self.bot.get_all_channels())
        event_key = 'channels'
        extra = self.extra.copy()
        extra.update({
            'discord_gauge': event_key,
            'channel_count': len(channels),
            # 'channel_ids': [c.id for c in channels],
            # 'channel_names': [c.name for c in channels],
            'text_channel_count': len(
                [c.id for c in channels if c.type == ChannelType.text]),
            # 'text_channel_ids': [
            #     c.id for c in channels if c.type == ChannelType.text],
            # 'text_channel_names': [
            #     c.name for c in channels if c.type == ChannelType.text],
            'voice_channel_count': len(
                [c.id for c in channels if c.type == ChannelType.text]),
            # 'voice_channel_ids': [
            #     c.id for c in channels if c.type == ChannelType.text],
            # 'voice_channel_names': [
            #     c.name for c in channels if c.type == ChannelType.text]
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_members(self):
        """Log members."""
        if not self.extra:
            return
        members = list(self.bot.get_all_members())
        unique = set(m.id for m in members)
        event_key = 'members'
        extra = self.extra.copy()
        extra.update({
            'discord_gauge': event_key,
            'member_count': len(members),
            'unique_member_count': len(unique)
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_voice(self):
        """Log voice channels."""
        pass

    def log_players(self):
        """Log VC players."""
        pass

    def log_uptime(self):
        """Log updtime."""
        pass

    def log_roles(self):
        """Log server roles."""
        if not self.extra:
            return
        for server in self.bot.servers:
            self.log_server_roles(server)

    def log_server_roles(self, server: Server):
        """Log server roles."""
        if not self.extra:
            return
        event_key = 'server.roles'
        extra = self.extra.copy()

        roles = server.role_hierarchy

        # count number of members with a particular role
        role_counts = []
        for role in roles:
            count = 0
            for member in server.members:
                if role in member.roles:
                    count += 1
            role_counts.append(count)

            # in order for logstash time series to work,
            # create fields with the role names with the count
            field_name = 'role_count_{}'.format(role.name)
            extra.update({field_name: count})

        extra.update({
            'discord_gauge': event_key,
            'role_count': len(roles),
            'role_names': [r.name for r in roles],
            'role_ids': [r.id for r in roles],
            'role_counts': role_counts,
            'server_id': server.id,
            'server_name': server.name
        })

        self.logger.info(self.get_event_key(event_key), extra=extra)


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
