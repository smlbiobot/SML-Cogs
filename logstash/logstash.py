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

import asyncio
import logging
import os
import re
import pprint
from datetime import timedelta

import logstash
from __main__ import send_cmd_help
from discord import Channel
from discord import ChannelType
from discord import Game
from discord import Member
from discord import Message
from discord import Role
from discord import Server
from discord import Status
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

HOST = 'localhost'
PORT = 5959
INTERVAL = timedelta(hours=4).seconds
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

        logging.getLogger("red").addHandler(self.handler)

    def __unload(self):
        """Unhook logger when unloaded.

        Thanks Kowlin!
        """
        self.logger.removeHandler(self.handler)
        logging.getLogger("red").removeHandler(self.handler)

    async def loop_task(self):
        """Loop task."""
        await self.bot.wait_until_ready()
        self.extra = {
            'log_type': 'discord.logger',
            'application': 'red',
            'bot_id': self.bot.user.id,
            'bot_name': self.bot.user.name
        }
        self.log_all_gauges()
        await asyncio.sleep(INTERVAL)
        if self is self.bot.get_cog('Logstash'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def logstash(self, ctx: Context):
        """Logstash command. Admin only."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @logstash.command(name="all", pass_context=True)
    async def logstash_all(self):
        """Send all stats."""
        self.log_all_gauges()
        await self.bot.say("Logged all.")

    @logstash.command(name="debug", pass_context=True)
    async def logstash_debug(self, ctx, *, msg):
        """Send debug event."""
        extra = {
            'debug': 'debug',
            'debug_message': msg
        }
        self.log_discord_event(event_key="discord.debug", extra=extra)
        await self.bot.say("logstash debug")

    async def on_channel_create(self, channel: Channel):
        """Track channel creation."""
        self.log_channel_create(channel)

    async def on_channel_delete(self, channel: Channel):
        """Track channel deletion."""
        self.log_channel_delete(channel)

    async def on_command(self, command: Command, ctx: Context):
        """Track command usage."""
        self.log_command(command, ctx)

    async def on_message(self, message: Message):
        """Track on message."""
        self.log_message(message)
        # self.log_emojis(message)

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        self.log_message_delete(message)

    async def on_message_edit(self, before: Message, after: Message):
        """Track message editing."""
        self.log_message_edit(before, after)

    async def on_member_join(self, member: Member):
        """Track members joining server."""
        self.log_member_join(member)

    async def on_member_update(self, before: Member, after: Member):
        """Called when a Member updates their profile.

        Only track status after.
        """
        self.log_member_update(before, after)

    async def on_member_remove(self, member: Member):
        """Track members leaving server."""
        self.log_member_remove(member)

    async def on_ready(self):
        """Bot ready."""
        self.log_all_gauges()

    async def on_resume(self):
        """Bot resume."""
        self.log_all_gauges()

    def get_message_sca(self, message: Message):
        """Return server, channel and author from message."""
        return message.server, message.channel, message.author

    def get_server_params(self, server: Server):
        """Return extra fields for server."""
        extra = {
            'id': server.id,
            'name': server.name,
        }
        return extra

    def get_channel_params(self, channel: Channel):
        """Return extra fields for channel."""
        extra = {
            'id': channel.id,
            'name': channel.name,
            'server': self.get_server_params(channel.server),
            'position': channel.position,
            'is_default': channel.is_default,
            'created_at': channel.created_at.isoformat(),
            'type': {
                'text': channel.type == ChannelType.text,
                'voice': channel.type == ChannelType.voice,
                'private': channel.type == ChannelType.private,
                'group': channel.type == ChannelType.group
            }
        }
        return extra

    def get_server_channel_params(self, channel: Channel):
        """Return digested version of channel params"""
        extra = {
            'id': channel.id,
            'name': channel.name,
            'position': channel.position,
            'is_default': channel.is_default,
            'created_at': channel.created_at.isoformat(),
        }
        return extra

    def get_member_params(self, member: Member):
        """Return data for member."""
        extra = {
            'name': member.display_name,
            'username': member.name,
            'display_name': member.display_name,
            'id': member.id,
            'bot': member.bot
        }

        if isinstance(member, Member):
            extra.update({
                'status': self.get_extra_status(member.status),
                'game': self.get_game_params(member.game),
                'top_role': self.get_role_params(member.top_role),
                'joined_at': member.joined_at.isoformat()
            })

        if hasattr(member, 'server'):
            extra['server'] = self.get_server_params(member.server)
            # message sometimes reference a user and has no roles info
            if hasattr(member, 'roles'):
                extra['roles'] = [self.get_role_params(r) for r in member.server.role_hierarchy if r in member.roles]

        return extra

    def get_role_params(self, role: Role):
        """Return data for role."""
        if not role:
            return {}
        extra = {
            'name': role.name,
            'id': role.id
        }
        return extra

    def get_extra_status(self, status: Status):
        """Return data for status."""
        extra = {
            'online': status == Status.online,
            'offline': status == Status.offline,
            'idle': status == Status.idle,
            'dnd': status == Status.dnd,
            'invisible': status == Status.invisible
        }
        return extra

    def get_game_params(self, game: Game):
        """Return ata for game."""
        if game is None:
            return {}
        extra = {
            'name': game.name,
            'url': game.url,
            'type': game.type
        }
        return extra

    def get_sca_params(self, message: Message):
        """Return extra fields from messages."""
        server = message.server
        channel = message.channel
        author = message.author

        extra = {}

        if author is not None:
            extra['author'] = self.get_member_params(author)

        if channel is not None:
            extra['channel'] = self.get_channel_params(channel)

        if server is not None:
            extra['server'] = self.get_server_params(server)

        return extra

    def get_mentions_extra(self, message: Message):
        """Return mentions in message."""
        mentions = set(message.mentions.copy())
        names = [m.display_name for m in mentions]
        ids = [m.id for m in mentions]
        return {
            'mention_names': names,
            'mention_ids': ids
        }

    def get_emojis_params(self, message: Message):
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

    def log_command(self, command, ctx):
        """Log bot commands."""
        pass
        # extra = {
        #     'name': command.name
        # }
        # extra.update(self.get_sca_params(ctx.message))
        # self.log_discord_event("command", extra)

    def log_emojis(self, message: Message):
        """Log emoji uses."""
        emojis = []
        emojis.append(EMOJI_P.findall(message.content))
        emojis.append(UEMOJI_P.findall(message.content))
        if not self.extra:
            return
        for emoji in emojis:
            extra = self.extra.copy()
            event_key = "message.emoji"
            extra = {
                'discord_event': event_key,
                'emoji': emoji
            }
            self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_discord(self, key=None, is_event=False, is_gauge=False, extra=None):
        """Log Discord logs"""
        if key is None:
            return
        if self.extra is None:
            return
        if extra is None:
            extra = {}
        extra.update(self.extra.copy())
        if is_event:
            extra['discord_event'] = key
        if is_gauge:
            extra['discord_gauge'] = key

        self.logger.info(self.get_event_key(key), extra=extra)

    def log_discord_event(self, key=None, extra=None):
        """Log Discord events."""
        self.log_discord(key=key, is_event=True, extra=extra)

    def log_discord_gauge(self, key=None, extra=None):
        """Log Discord events."""
        self.log_discord(key=key, is_gauge=True, extra=extra)

    def log_channel_create(self, channel: Channel):
        """Log channel creation."""
        extra = {
            'channel': self.get_channel_params(channel)
        }
        self.log_discord_event("channel.create", extra)

    def log_channel_delete(self, channel: Channel):
        """Log channel deletion."""
        extra = {
            'channel': self.get_channel_params(channel)
        }
        self.log_discord_event("channel.delete", extra)

    def log_member_join(self, member: Member):
        """Log member joining the server."""
        extra = {
            'member': self.get_member_params(member)
        }
        self.log_discord_event("member.join", extra)

    def log_member_update(self, before: Member, after: Member):
        """Track member’s updated status."""
        if set(before.roles) != set(after.roles):
            extra = {
                'member': self.get_member_params(after)
            }
            if len(before.roles) > len(after.roles):
                roles_removed = set(before.roles) - set(after.roles)
                extra['role_update'] = 'remove'
                extra['roles_removed'] = [self.get_role_params(r) for r in roles_removed]
            else:
                roles_added = set(after.roles) - set(before.roles)
                extra['role_update'] = 'add'
                extra['roles_added'] = [self.get_role_params(r) for r in roles_added]

            self.log_discord_event('member.update.roles', extra)

    def log_member_remove(self, member: Member):
        """Log member leaving the server."""
        extra = {
            'member': self.get_member_params(member)
        }
        self.log_discord_event("member.remove", extra)

    def log_message(self, message: Message):
        """Log message."""
        extra = {'content': message.content}
        extra.update(self.get_sca_params(message))
        extra.update(self.get_mentions_extra(message))
        self.log_discord_event('message', extra)

    def log_message_delete(self, message: Message):
        """Log deleted message."""
        extra = {'content': message.content}
        extra.update(self.get_sca_params(message))
        extra.update(self.get_mentions_extra(message))
        self.log_discord_event('message.delete', extra)

    def log_message_edit(self, before: Message, after: Message):
        """Log message editing."""
        extra = {
            'content_before': before.content,
            'content_after': after.content
        }
        extra.update(self.get_sca_params(after))
        extra.update(self.get_mentions_extra(after))
        self.log_discord_event('message.edit', extra)

    def log_all_gauges(self):
        """Log all gauge values."""
        self.log_servers()
        self.log_channels()
        self.log_members()
        self.log_voice()
        self.log_players()
        self.log_uptime()
        self.log_server_roles()
        self.log_server_channels()

    def log_servers(self):
        """Log servers."""
        if not self.extra:
            return
        event_key = 'servers'
        extra = self.extra.copy()
        servers = list(self.bot.servers)
        extra.update({
            'discord_gauge': event_key,
            'server_count': len(servers)
        })
        servers_data = []
        for server in servers:
            servers_data.append(self.get_server_params(server))
        extra['servers'] = servers_data
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_channels(self):
        """Log channels."""
        channels = list(self.bot.get_all_channels())
        extra = {
            'channel_count': len(channels)
        }
        self.log_discord_gauge('all_channels', extra=extra)

        # individual channels
        for channel in channels:
            self.log_channel(channel)

    def log_channel(self, channel: Channel):
        """Log one channel."""
        extra = {'channel': self.get_channel_params(channel)}
        self.log_discord_gauge('channel', extra=extra)

    def log_members(self):
        """Log members."""
        members = list(self.bot.get_all_members())
        unique = set(m.id for m in members)
        extra = {
            'member_count': len(members),
            'unique_member_count': len(unique)
        }
        self.log_discord_gauge('all_members', extra=extra)

        for member in members:
            self.log_member(member)

    def log_member(self, member: Member):
        """Log member."""
        extra = {'member': self.get_member_params(member)}
        self.log_discord_gauge('member', extra=extra)

    def log_voice(self):
        """Log voice channels."""
        pass

    def log_players(self):
        """Log VC players."""
        pass

    def log_uptime(self):
        """Log updtime."""
        pass

    def log_server_roles(self):
        """Log server roles."""
        for server in self.bot.servers:
            extra = {}
            extra['server'] = self.get_server_params(server)
            extra['roles'] = []

            roles = server.role_hierarchy

            # count number of members with a particular role
            for index, role in enumerate(roles):
                count = sum([1 for m in server.members if role in m.roles])

                role_params = self.get_role_params(role)
                role_params['count'] = count
                role_params['hierachy_index'] = index

                extra['roles'].append(role_params)

            self.log_discord_gauge('server.roles', extra)

    def log_server_channels(self):
        """Log server channels."""
        for server in self.bot.servers:
            extra = {
                'server': self.get_server_params(server),
                'channels': {
                    'text': [],
                    'voice': []
                }
            }
            channels = sorted(server.channels, key=lambda x:x.position)

            for channel in channels:
                channel_params = self.get_server_channel_params(channel)
                if channel.type == ChannelType.text:
                    extra['channels']['text'].append(channel_params)
                elif channel.type == ChannelType.voice:
                    extra['channels']['voice'].append(channel_params)

            self.log_discord_gauge('server.channels', extra)


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
