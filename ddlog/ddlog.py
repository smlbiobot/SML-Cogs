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
import io
import datetime
import asyncio
import discord

from discord import Message
from discord import Server
from discord import ChannelType
from discord.ext.commands import Command
from discord.ext.commands import Context

from cogs.utils.dataIO import dataIO

try:
    import datadog
    from datadog import statsd
except ImportError:
    raise ImportError("Please install the datadog package from pip") from None

PATH_LIST = ['data', 'ddlog']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
HOST = '127.0.0.1'
INTERVAL = 5

class DataDogLog:
    """DataDog Logger.

    Using DataDog cog as starting point:
    https://github.com/calebj/calebj-cogs/tree/master/datadog
    """
    def __init__(self, bot):
        self.bot = bot
        self.tags = []
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(JSON)
        datadog.initialize(statsd_host=self.settings['HOST'])

    def save(self):
        dataIO.save_json(JSON, self.settings)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        await self.bot.wait_until_ready()
        self.tags = [
            'application:red',
            'bot_id:' + self.bot.user.id,
            'bot_name:' + self.bot.user.name]
        self.send_all()
        await asyncio.sleep(self.settings['INTERVAL'])
        if self is self.bot.get_cog('DataDogLog'):
            self.task = self.bot.loop.create_task(self.loop_task())

    async def on_message(self, message: Message):
        """Logs messages."""
        author = message.author
        server = message.server
        # Don’t log bot messages
        if server is None:
            return
        if author is server.me:
            return
        self.dd_log_messages(message)
        self.dd_log_mentions(message)
        self.dd_log_message_author_roles(message)

    async def on_command(self, command: Command, ctx: Context):
        """Logs commands."""
        self.dd_log_command(command, ctx)

    async def on_channel_create(self, channel):
        if channel.type == 'text':
            self.send_channels()

    async def on_channel_delete(self, channel):
        if channel.type == 'text':
            self.send_channels()

    async def on_member_join(self, member):
        self.send_members()

    async def on_member_remove(self, member):
        self.send_members()

    async def on_server_join(self, server):
        channels = server.channels
        text_channels = sum(c.type == ChannelType.text for c in channels)
        voice_channels = sum(c.type == ChannelType.voice for c in channels)
        statsd.event(tags=self.tags,
                     title='%s joined %s!' % (self.bot.user.name, server),
                     text='\n'.join([
                         '* %i new members' % len(server.members),
                         '* %i new text channels' % text_channels,
                         '* %i new voice channels' % voice_channels
                     ]))
        self.send_servers()

    async def on_server_remove(self, server):
        channels = server.channels
        text_channels = sum(c.type == ChannelType.text for c in channels)
        voice_channels = sum(c.type == ChannelType.voice for c in channels)
        statsd.event(tags=self.tags,
                     title='%s left %s :(' % (self.bot.user.name, server),
                     text='\n'.join([
                         '* %i less members' % len(server.members),
                         '* %i less text channels' % text_channels,
                         '* %i less voice channels' % voice_channels
                     ]))
        self.send_servers()

    async def on_ready(self):
        self.send_all()

    async def on_resume(self):
        self.send_all()

    def dd_log_mentions(self, message: discord.Message):
        """Send mentions to datadog."""
        for member in message.mentions:
            statsd.increment(
                'bot.mentions',
                tags=[
                    *self.tags,
                    'member:' + str(member.display_name),
                    'member_id:' + str(member.id),
                    'member_name:' + str(member.display_name)])

    def dd_log_messages(self, message: discord.Message):
        """Send message stats to datadog."""
        channel = message.channel
        channel_name = ''
        channel_id = ''
        if channel is not None:
            if not channel.is_private:
                channel_name = channel.name
                channel_id = channel.id

        server_id = message.server.id
        server_name = message.server.name

        statsd.increment(
            'bot.msg',
            tags=[
                *self.tags,
                'author:' + str(message.author.display_name),
                'author_id:' + str(message.author.id),
                'author_name:' + str(message.author.name),
                'server_id:' + str(server_id),
                'server_name:' + str(server_name),
                'channel:' + str(channel_name),
                'channel_name:' + str(channel_name),
                'channel_id:' + str(channel_id)])

    def dd_log_message_author_roles(self, message: discord.Message):
        """Go through author’s roles and send each."""
        for r in message.author.roles:
            if not r.is_everyone:
                statsd.increment(
                    'bot.msg.author.role',
                    tags=[
                        *self.tags,
                        'role:' + str(r.name)])

    def dd_log_command(self, command: Command, ctx: Context):
        """Log commands with datadog."""
        channel = ctx.message.channel
        channel_name = ''
        channel_id = ''
        if channel is not None:
            if not channel.is_private:
                channel_name = channel.name
                channel_id = channel.id
        server = ctx.message.server
        server_id = server.id
        server_name = server.name
        statsd.increment(
            'bot.cmd',
            tags=[
                *self.tags,
                'author:' + str(ctx.message.author.display_name),
                'author_id:' + str(ctx.message.author.id),
                'author_name:' + str(ctx.message.author.name),
                'server_id:' + str(server_id),
                'server_name:' + str(server_name),
                'channel_name:' + str(channel_name),
                'channel_id:' + str(channel_id),
                'command_name:' + str(command),
                'cog_name:' + type(ctx.cog).__name__])

    def send_all(self):
        self.send_servers()
        self.send_channels()
        self.send_members()
        self.send_voice()
        self.send_players()
        self.send_uptime()
        self.send_roles()

    def send_uptime(self):
        if not self.tags:
            return
        now = datetime.datetime.now()
        uptime = (now - self.bot.uptime).total_seconds()
        statsd.gauge('bot.uptime', uptime, tags=self.tags)

    def send_servers(self):
        if not self.tags:
            return
        servers = len(self.bot.servers)
        statsd.gauge('bot.servers', servers, tags=self.tags)

    def send_channels(self):
        if not self.tags:
            return
        channels = list(self.bot.get_all_channels())
        text_channels = sum(c.type == ChannelType.text for c in channels)
        voice_channels = sum(c.type == ChannelType.voice for c in channels)
        statsd.gauge('bot.channels', voice_channels,
                     tags=[*self.tags, 'channel_type:voice'])
        statsd.gauge('bot.channels', text_channels,
                     tags=[*self.tags, 'channel_type:text'])

    def send_members(self):
        if not self.tags:
            return
        members = list(self.bot.get_all_members())
        unique = set(m.id for m in members)
        statsd.gauge('bot.members', len(members), tags=self.tags)
        statsd.gauge('bot.unique_members', len(unique), tags=self.tags)

    def send_voice(self):
        if not self.tags:
            return
        vcs = len(self.bot.voice_clients)
        statsd.gauge('bot.voice_clients', vcs, tags=self.tags)

    def send_roles(self):
        """Send roles from all servers."""
        if not self.tags:
            return
        for server in self.bot.servers:
            self.send_server_roles(server)

    def send_server_roles(self, server: Server):
        """Log server roles on datadog."""
        if not self.tags:
            return
        roles = {}
        for role in server.roles:
            roles[role.id] = {'role': role, 'count': 0}
        for member in server.members:
            for role in member.roles:
                roles[role.id]['count'] += 1

        for role in server.roles:
            role_count = roles[role.id]['count']
            statsd.gauge(
                'bot.roles.{}'.format(server.id),
                role_count,
                tags=[
                    *self.tags,
                    'role_name:' + role.name,
                    'role_id:' + role.id,
                    'server_id:' + server.id,
                    'server_name:' + server.name])

    def notbot(self, channel):
        return sum(m != self.bot.user for m in channel.voice_members)

    def send_players(self):
        if not self.tags:
            return
        avcs = []
        for vc in self.bot.voice_clients:
            if hasattr(vc, 'audio_player') and not vc.audio_player.is_done():
                avcs.append(vc)
        num_avcs = len(avcs)
        audience = sum(self.notbot(vc.channel) for vc in avcs if vc.channel)
        statsd.gauge('bot.voice_playing', num_avcs, tags=self.tags)
        statsd.gauge('bot.voice_audience', audience, tags=self.tags)


def check_folders():
    if not os.path.exists(PATH):
        print("Creating %s folder..." % PATH)
        os.makedirs(PATH)


def check_files():
    defaults = {
        'HOST': HOST,
        'INTERVAL': INTERVAL
    }
    if not dataIO.is_valid_json(JSON):
        print("Creating empty %s" % JSON)
        dataIO.save_json(JSON, defaults)


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(DataDogLog(bot))



