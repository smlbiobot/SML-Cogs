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
import json
from collections import defaultdict
import discord
from discord.ext import commands
import datetime as dt

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "archive")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Archive:
    """Archive activity.

    General utility used for archiving message logs
    from one channel to another.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.units = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000}

    @commands.group(pass_context=True, no_pm=True)
    async def archive(self, ctx):
        """Archive activity."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @archive.command(name="channel", pass_context=True, no_pm=True)
    async def archive_channel(self, ctx, channel: discord.Channel, count=1000):
        """Archive channel messages."""
        await self.save_channel(channel, count)
        await self.log_channel(ctx, channel)

        await self.bot.say("Channel logged.")

    async def save_channel(self, channel: discord.Channel, count=1000, before=None, after=None, reverse=False):
        """Save channel messages."""
        server = channel.server
        if server.id not in self.settings:
            self.settings[server.id] = {}

        channel_messages = []

        async for message in self.bot.logs_from(
                channel, limit=count, before=before, after=after, reverse=reverse):
            msg ={
                'author_id': message.author.id,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'id': message.id,
                'reactions': []
            }
            for reaction in message.reactions:
                r = {
                    'custom_emoji': reaction.custom_emoji,
                    'count': reaction.count
                }
                if reaction.custom_emoji:
                    # <:emoji_name:emoji_id>
                    r['emoji'] = '<:{}:{}>'.format(
                        reaction.emoji.name,
                        reaction.emoji.id)
                else:
                    r['emoji'] = reaction.emoji
                msg['reactions'].append(r)
            channel_messages.append(msg)

        channel_messages = sorted(
            channel_messages, key=lambda x: x['timestamp'])

        self.settings[server.id][channel.id] = channel_messages
        dataIO.save_json(JSON, self.settings)

    async def log_channel(self, ctx, channel: discord.Channel):
        """Write channel messages from a channel."""
        server = ctx.message.server

        channel_messages = self.settings[server.id][channel.id]
        for message in channel_messages:
            author_id = message['author_id']
            author = server.get_member(author_id)
            author_mention = author_id
            if author is not None:
                author_mention = author.mention
            content = message['content']
            timestamp = message['timestamp']
            message_id = message['id']

            description = '{}: {}'.format(author_mention, content)

            em = discord.Embed(
                title=channel.name,
                description=description)

            for reaction in message['reactions']:
                em.add_field(name=reaction['emoji'], value=reaction['count'])

            em.set_footer(text='{} - ID: {}'.format(timestamp, message_id))
            await self.bot.say(embed=em)

    @checks.serverowner_or_permissions()
    @commands.group(pass_context=True, no_pm=True)
    async def archiveserver(self, ctx):
        """Archive server."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.serverowner_or_permissions()
    @archiveserver.command(name="after", pass_context=True, no_pm=True)
    async def archiveserver_after(self, ctx, server_name, channel_name, message_id, count=1000):
        """Archive server after a message"""
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Server not found.")
            return
        channel = discord.utils.get(server.channels, name=channel_name)
        if channel is None:
            await self.bot.say("Channel not found.")
            return
        message = await self.bot.get_message(channel, message_id)

        await self.log_server_channel(ctx, server, channel, count, after=message)
        await self.bot.say("Channel logged.")

    @checks.serverowner_or_permissions()
    @archiveserver.command(name="since", pass_context=True, no_pm=True)
    async def archiveserver_since(self, ctx, server_name, channel_name, quantity : int, time_unit : str, count=1000):
        """Archive server channel since a timestamp.

        Accepts: minutes, hours, days, weeks, month
        Example:
        [p]archiveserver since "ABC Server" "EFG Channel" 2 days 2000
        """
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Server not found.")
            return
        channel = discord.utils.get(server.channels, name=channel_name)
        if channel is None:
            await self.bot.say("Channel not found.")
            return

        if time_unit.endswith("s"):
            time_unit = time_unit[:-1]
            s = "s"
        if not time_unit in self.units:
            await self.bot.say("Invalid time unit. Choose minutes/hours/days/weeks/month")
            return
        if quantity < 1:
            await self.bot.say("Quantity must not be 0 or negative.")
            return

        seconds = self.units[time_unit] * quantity
        after = dt.datetime.utcnow() - dt.timedelta(seconds=seconds)

        await self.log_server_channel(ctx, server, channel, count, after=after)
        await self.bot.say("Channel logged.")

    @checks.serverowner_or_permissions()
    @archiveserver.command(name="full", pass_context=True, no_pm=True)
    async def archiveserver_full(self, ctx, server_name):
        """Archive all messages from a server. Return as JSON."""
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Server not found.")
            return
        log = {}
        for channel in server.channels:
            await self.bot.type()
            log[channel.id] = {
                "id": channel.id,
                "name": channel.name,
                "messages": await self.channel_messages(channel, count=10000)
            }

        filename = "server_archive-{}.json".format(server.id)
        with io.StringIO() as f:
            json.dump(log, f, indent=4)
            f.seek(0)
            await ctx.bot.send_file(
                ctx.message.channel,
                f,
                filename=filename
            )

    async def channel_messages(self, channel: discord.Channel,
            count=1000, before=None, after=None, reverse=False):
        messages = []

        async for message in self.bot.logs_from(
                channel, limit=count, before=before, after=after, reverse=reverse):
            msg = {
                "timestamp": message.timestamp.isoformat(),
                "author_id": message.author.id,
                "author_name": message.author.name,
                "content": message.content,
                "embeds": message.embeds,
                "channel_id": message.channel.id,
                "channel_name": message.channel.name,
                "server_id": message.server.id,
                "server_name": message.server.name,
                "mention_everyone": message.mention_everyone,
                "mentions_id": [m.id for m in message.mentions],
                "mentions_name": [m.name for m in message.mentions],
                "reactions": [],
                "attachments": []
            }
            for reaction in message.reactions:
                r = {
                    'custom_emoji': reaction.custom_emoji,
                    'count': reaction.count
                }
                if reaction.custom_emoji:
                    # <:emoji_name:emoji_id>
                    r['emoji'] = '<:{}:{}>'.format(
                        reaction.emoji.name,
                        reaction.emoji.id)
                else:
                    r['emoji'] = reaction.emoji
                msg['reactions'].append(r)

            for attach in message.attachments:
                msg['attachments'].append(attach['url'])
                messages.append(msg)

        messages = sorted(messages, key=lambda x: x['timestamp'])
        return messages


    async def log_server_channel(
            self, ctx, server: discord.Server, channel: discord.Channel,
            count=1000, before=None, after=None, reverse=False):
        """Save channel messages."""
        channel_messages = []

        await self.bot.say("Logging messages.")

        async for message in self.bot.logs_from(
                channel, limit=count, before=before, after=after, reverse=reverse):
            msg ={
                'author_id': message.author.id,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'id': message.id,
                'reactions': [],
                'attachments': []
            }
            for reaction in message.reactions:
                r = {
                    'custom_emoji': reaction.custom_emoji,
                    'count': reaction.count
                }
                if reaction.custom_emoji:
                    # <:emoji_name:emoji_id>
                    r['emoji'] = '<:{}:{}>'.format(
                        reaction.emoji.name,
                        reaction.emoji.id)
                else:
                    r['emoji'] = reaction.emoji
                msg['reactions'].append(r)

            for attach in message.attachments:
                msg['attachments'].append(attach['url'])
            channel_messages.append(msg)

        channel_messages = sorted(
            channel_messages, key=lambda x: x['timestamp'])

        self.settings[server.id][channel.id] = channel_messages
        dataIO.save_json(JSON, self.settings)

        # write out
        for message in channel_messages:
            author_id = message['author_id']
            author = server.get_member(author_id)
            author_mention = author_id
            if author is not None:
                author_mention = author.mention
            content = message['content']
            timestamp = message['timestamp']
            message_id = message['id']

            description = '{}: {}'.format(author_mention, content)

            em = discord.Embed(
                title=channel.name,
                description=description)

            for reaction in message['reactions']:
                em.add_field(name=reaction['emoji'], value=reaction['count'])

            for attach in message['attachments']:
                em.set_image(url=attach)

            em.set_footer(text='{} - ID: {}'.format(timestamp, message_id))
            await self.bot.say(embed=em)


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
    n = Archive(bot)
    bot.add_cog(n)
