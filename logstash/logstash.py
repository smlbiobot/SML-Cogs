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
        self.log_all()
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
        self.log_all()
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

    async def on_message(self, message: Message):
        """Track on message."""
        self.log_message(message)
        # self.log_emojis(message)

    async def on_command(self, command: Command, ctx: Context):
        """Track command usage."""
        self.log_command(command, ctx)

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
        self.log_all()

    async def on_resume(self):
        """Bot resume."""
        self.log_all()

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
            'type': {
                'text': channel.type == ChannelType.text,
                'voice': channel.type == ChannelType.voice,
                'private': channel.type == ChannelType.private,
                'group': channel.type == ChannelType.group
            }
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
                roles = []
                for r in member.server.role_hierarchy:
                    if r in member.roles:
                        roles.append({
                            'id': r.id,
                            'name': r.name
                        })
                extra['roles'] = roles

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

    def get_extra_mentions(self, message: Message):
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
        if not self.extra:
            return
        extra = self.extra.copy()
        event_key = "command"
        extra = {
            'discord_event': event_key,
            'command_name': command.name
        }
        extra.update(self.get_sca_params(ctx.message))
        self.logger.info(self.get_event_key(event_key), extra=extra)

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

    def log_discord_event(self, event_key=None, extra=None):
        """Log Discord events."""
        if event_key is None:
            return
        if self.extra is None:
            return
        if extra is None:
            extra = {}
        extra.update(self.extra.copy())
        extra['discord_event'] = event_key

        self.logger.info(self.get_event_key(event_key), extra=extra)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.get_event_key(event_key))
        pp.pprint(extra)

    def log_channel_create(self, channel: Channel):
        """Log channel creation."""
        extra = self.extra

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
                extra['role_removed'] = [self.get_role_params(r) for r in roles_removed][0]
            else:
                roles_added = set(after.roles) - set(before.roles)
                extra['role_update'] = 'add'
                extra['role_added'] = [self.get_role_params(r) for r in roles_added][0]

            self.log_discord_event(event_key='member.update.roles', extra=extra)

    def log_member_remove(self, member: Member):
        """Log member leaving the server."""
        extra = self.extra.copy()
        extra['member'] = self.get_member_params(member)
        self.log_discord_event("member.remove", extra)

    def log_message(self, message: Message):
        """Log message."""
        if not self.extra:
            return
        extra = self.extra.copy()
        event_key = "message"

        extra = {
            'discord_event': event_key,
            'content': message.content
        }
        extra.update(self.get_sca_params(message))
        extra.update(self.get_extra_mentions(message))
        # extra.update(self.get_extra_emojis(message))
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_message_delete(self, message: Message):
        """Log deleted message."""
        if not self.extra:
            return
        extra = self.extra.copy()
        event_key = "message.delete"

        extra = {
            'discord_event': event_key,
            'content': message.content
        }
        extra.update(self.get_sca_params(message))
        extra.update(self.get_extra_mentions(message))
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_message_edit(self, before: Message, after: Message):
        """Log message diting."""
        if not self.extra:
            return
        extra = self.extra.copy()
        event_key = "message.edit"

        extra = {
            'discord_event': event_key,
        }
        before_extra = {'content': before.content}
        before_extra.update(self.get_sca_params(before))
        before_extra.update(self.get_extra_mentions(before))
        after_extra = {'content': after.content}
        after_extra.update(self.get_sca_params(after))
        after_extra.update(self.get_extra_mentions(after))
        extra.update({
            'before': before_extra,
            'after': after_extra
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_all(self):
        """Log all gauge values."""
        self.log_servers()
        self.log_channels()
        self.log_members()
        self.log_voice()
        self.log_players()
        self.log_uptime()
        self.log_server_roles()

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
        if not self.extra:
            return
        channels = list(self.bot.get_all_channels())
        event_key = 'all_channels'
        extra = self.extra.copy()
        extra.update({
            'discord_gauge': event_key,
            'channel_count': len(channels)
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

        # individual channels
        for channel in channels:
            self.log_channel(channel)

    def log_channel(self, channel: Channel):
        """Log one channel."""
        event_key = 'channel'
        extra = self.extra.copy()
        extra['discord_gauge'] = event_key
        extra['channel'] = self.get_channel_params(channel)
        self.logger.info(self.get_event_key(event_key), extra=extra)

    def log_members(self):
        """Log members."""
        if not self.extra:
            return

        # all members
        members = list(self.bot.get_all_members())
        unique = set(m.id for m in members)
        event_key = 'all_members'
        extra = self.extra.copy()
        extra.update({
            'discord_gauge': event_key,
            'member_count': len(members),
            'unique_member_count': len(unique)
        })
        self.logger.info(self.get_event_key(event_key), extra=extra)

        for member in members:
            self.log_member(member)

    def log_member(self, member: Member):
        """Log member."""
        extra = self.extra.copy()
        event_key = 'member'
        extra['discord_gauge'] = event_key
        extra['member'] = self.get_member_params(member)
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

    def log_server_roles(self):
        """Log server roles."""
        if not self.extra:
            return

        event_key = 'server.roles'

        for server in self.bot.servers:

            roles = server.role_hierarchy

            # count number of members with a particular role
            for index, role in enumerate(roles):
                count = sum([1 for m in server.members if role in m.roles])

                extra = self.extra.copy()
                extra['discord_gauge'] = event_key
                extra['server'] = self.get_server_params(server)
                extra['role'] = self.get_role_params(role)
                extra['role']['count'] = count
                extra['role']['hierachy_index'] = index

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
