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

import argparse
import asyncio
import datetime as dt
import itertools
import os
import re
from collections import defaultdict
from collections import Counter
from datetime import timedelta
from random import choice

import discord
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
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import QueryString
from elasticsearch_dsl.query import Range
from elasticsearch_dsl import Index, DocType, Date, Nested, Boolean, \
    analyzer, InnerObjectWrapper, Completion, Keyword, Text, Integer

from cogs.utils.chat_formatting import inline
from cogs.utils.dataIO import dataIO
from cogs.utils import checks

# global ES connection
from elasticsearch_dsl.connections import connections
connections.create_connection(hosts=['localhost'], timeout=20)

INTERVAL = timedelta(hours=4).seconds

PATH = os.path.join('data', 'eslog')
JSON = os.path.join(PATH, 'settings.json')

EMOJI_P = re.compile('\<\:.+?\:\d+\>')
UEMOJI_P = re.compile(u'['
                      u'\U0001F300-\U0001F64F'
                      u'\U0001F680-\U0001F6FF'
                      u'\uD83C-\uDBFF\uDC00-\uDFFF'
                      u'\u2600-\u26FF\u2700-\u27BF]{1,2}',
                      re.UNICODE)


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


class ServerInnerObject(InnerObjectWrapper):
    """Server Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class ChannelInnerObject(InnerObjectWrapper):
    """Channel Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})

class RoleInnerObject(InnerObjectWrapper):
    """Role Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class MemberInnerObject(InnerObjectWrapper):
    """Member Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})
    display_name = Text(fields={'raw': Keyword()})
    bot = Boolean()
    top_role = Nested(doc_class=RoleInnerObject)
    roles = Nested(doc_class=RoleInnerObject)


class MessageDoc(DocType):
    """Discord Message."""
    id = Integer()
    content = Text(
        fields={'raw': Keyword()}
    )
    author = Nested(doc_class=MemberInnerObject)
    server = Nested(doc_class=ServerInnerObject)
    channel = Nested(doc_class=ChannelInnerObject)
    mentions = Nested(doc_class=MemberInnerObject)
    timestamp = Date()

    class Meta:
        doc_type = 'message'

    @classmethod
    def log(cls, message, **kwargs):
        """Log all."""
        doc = MessageDoc(
            content=message.content,
            embeds=message.embeds,
            attachments=message.attachments,
            id=message.id,
            timestamp=dt.datetime.utcnow()
        )
        doc.set_server(message.server)
        doc.set_channel(message.channel)
        doc.set_author(message.author)
        doc.set_mentions(message.mentions)
        doc.save(**kwargs)

    def member_dict(self, member):
        """Member dictionary."""
        return {
            'id': member.id,
            'name': member.display_name,
            'username': member.name,
            'display_name': member.display_name,
            'bot': member.bot,
            'roles': [
                {'id': r.id, 'name': r.name} for r in member.roles
            ],
            'top_role': {
                'id': member.top_role.id,
                'name': member.top_role.name
            },
            'joined_at': member.joined_at
        }

    def set_author(self, author):
        """Set author."""
        self.author = self.member_dict(author)

    def set_server(self, server):
        """Set server."""
        self.server = {
            'id': server.id,
            'name': server.name
        }

    def set_channel(self, channel):
        """Set channel."""
        self.channel = {
            'id': channel.id,
            'name': channel.name,
            'is_default': channel.is_default,
            'position': channel.position
        }

    def set_mentions(self, mentions):
        """Set mentions."""
        self.mentions = [self.member_dict(m) for m in mentions]

    def save(self, **kwargs):
        return super(MessageDoc, self).save(**kwargs)


class MessageDeleteDoc(MessageDoc):
    """Discord Message Delete."""

    class Meta:
        doc_type = 'message_delete'

    @classmethod
    def log(cls, message, **kwargs):
        """Log all."""
        doc = MessageDeleteDoc(
            content=message.content,
            embeds=message.embeds,
            attachments=message.attachments,
            id=message.id,
            timestamp=dt.datetime.utcnow()
        )
        doc.set_server(message.server)
        doc.set_channel(message.channel)
        doc.set_author(message.author)
        doc.set_mentions(message.mentions)
        doc.save(**kwargs)

    def save(self, **kwargs):
        return super(MessageDeleteDoc, self).save(**kwargs)


class ESLogger2:
    """Elastic Search Logging v2.
    
    Separated into own class to make migration easier.
    """
    def __init__(self):
        pass

    @property
    def index_name(self):
        """ES index name.
        
        Automatically generated using current time.
        """
        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')
        index_name = 'discord2-{}'.format(now_str)
        return index_name

    @property
    def now(self):
        """Current time"""
        return dt.datetime.utcnow()

    def log_message(self, message: Message):
        """Log message v2."""
        MessageDoc.log(message, index=self.index_name)

    def log_message_delete(self, message: Message):
        """Log deleted message."""
        MessageDeleteDoc.log(message, index=self.index_name)

    def search_author_messages(self, author):
        """Search messages by author."""
        s = MessageDoc.search()
        # s = s.filter('terms', author={'id': author.id})
        s = s.query('term', **{'author.id': author.id})
        results = s.execute()
        for message in results:
            print(message.meta.score, message.content)


class ESLogger:
    """Elastic Search Logging module.
    
    Handle logging for everything.
    Most of these methods were orginally inside the Cog class,
    but it makes navigating the commands difficult.
    """

    def __init__(self, bot, es: Elasticsearch):
        """Init."""
        self.bot = bot
        self.es = es
        self.extra = None

        # DMessage.init('discord2', using=self.es)

    def init_extra(self):
        """Initialize extra settings.
        
        This doubles as a flag for when the cog is ready to log to ES.
        As such it is not initialized in __init__
        """
        self.extra = {
            'log_type': 'discord.logger',
            'application': 'red',
            'bot_id': self.bot.user.id,
            'bot_name': self.bot.user.name
        }

    def get_message_sca(self, message: Message):
        """Return server, channel and author from message."""
        return message.server, message.channel, message.author

    def param_server(self, server: Server):
        """Return extra fields for server."""
        extra = {
            'id': server.id,
            'name': server.name,
        }
        return extra

    def param_channel(self, channel: Channel):
        """Return extra fields for channel."""
        extra = {
            'id': channel.id,
            'name': channel.name,
            'server': self.param_server(channel.server),
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

    def param_server_channel(self, channel: Channel):
        """Return digested version of channel params"""
        extra = {
            'id': channel.id,
            'name': channel.name,
            'position': channel.position,
            'is_default': channel.is_default,
            'created_at': channel.created_at.isoformat(),
        }
        return extra

    def param_member(self, member: Member):
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
                'status': self.param_status(member.status),
                'game': self.param_game(member.game),
                'top_role': self.param_role(member.top_role),
                'joined_at': member.joined_at.isoformat()
            })

        if hasattr(member, 'server'):
            extra['server'] = self.param_server(member.server)
            # message sometimes reference a user and has no roles info
            if hasattr(member, 'roles'):
                extra['roles'] = [self.param_role(r) for r in member.server.role_hierarchy if r in member.roles]

        return extra

    def param_role(self, role: Role):
        """Return data for role."""
        if not role:
            return {}
        extra = {
            'name': role.name,
            'id': role.id
        }
        return extra

    def param_status(self, status: Status):
        """Return data for status."""
        extra = {
            'online': status == Status.online,
            'offline': status == Status.offline,
            'idle': status == Status.idle,
            'dnd': status == Status.dnd,
            'invisible': status == Status.invisible
        }
        return extra

    def param_game(self, game: Game):
        """Return ata for game."""
        if game is None:
            return {}
        extra = {
            'name': game.name,
            'url': game.url,
            'type': game.type
        }
        return extra

    def param_sca(self, message: Message):
        """Return extra fields from messages."""
        server = message.server
        channel = message.channel
        author = message.author

        extra = {}

        if author is not None:
            extra['author'] = self.param_member(author)

        if channel is not None:
            extra['channel'] = self.param_channel(channel)

        if server is not None:
            extra['server'] = self.param_server(server)

        return extra

    def param_mention(self, message: Message):
        """Return mentions in message."""
        mentions = []
        for member in set(message.mentions.copy()):
            mentions.append(self.param_member(member))
        return {
            'mentions': mentions
        }

    def param_attachment(self, message: Message):
        """Return attachments in message."""
        attach = [{'url': a['url']} for a in message.attachments]
        # attach = []
        return {
            'attachments': attach
        }

    def param_embed(self, message: Message):
        """Return list of embeds as dictionary."""
        embeds = [em for em in message.embeds]
        return {
            'embeds': embeds
        }

    def param_emoji(self, message: Message):
        """Return list of emojis used in messages."""
        emojis = []
        emojis.append(EMOJI_P.findall(message.content))
        emojis.append(UEMOJI_P.findall(message.content))
        return {
            'emojis': emojis
        }

    def log(self, key, extra=None):
        """Generic logging.

        Used to allow other cogs to log with this cog.
        """
        pass
        # self.logger.info(key, extra=extra)

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

        if is_event:
            doc_type = 'discord_event'
        elif is_gauge:
            doc_type = 'discord_gauge'
        else:
            doc_type = 'discord'

        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')

        extra['timestamp'] = now

        self.es.index(
            index='discord-{}'.format(now_str),
            doc_type=doc_type,
            body=extra,
            timestamp=now
        )

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
        for emoji in emojis:
            event_key = "message.emoji"
            extra = {
                'discord_event': event_key,
                'emoji': emoji
            }
            self.log_discord_event("message.emoji", extra=extra)

    def log_discord_event(self, key=None, extra=None):
        """Log Discord events."""
        self.log_discord(key=key, is_event=True, extra=extra)

    def log_discord_gauge(self, key=None, extra=None):
        """Log Discord events."""
        self.log_discord(key=key, is_gauge=True, extra=extra)

    def log_channel_create(self, channel: Channel):
        """Log channel creation."""
        extra = {
            'channel': self.param_channel(channel)
        }
        self.log_discord_event("channel.create", extra)

    def log_channel_delete(self, channel: Channel):
        """Log channel deletion."""
        extra = {
            'channel': self.param_channel(channel)
        }
        self.log_discord_event("channel.delete", extra)

    def log_member_join(self, member: Member):
        """Log member joining the server."""
        extra = {
            'member': self.param_member(member)
        }
        self.log_discord_event("member.join", extra)

    def log_member_update(self, before: Member, after: Member):
        """Track member’s updated status."""
        if set(before.roles) != set(after.roles):
            extra = {
                'member': self.param_member(after)
            }
            if len(before.roles) > len(after.roles):
                roles_removed = set(before.roles) - set(after.roles)
                extra['role_update'] = 'remove'
                extra['roles_removed'] = [self.param_role(r) for r in roles_removed]
            else:
                roles_added = set(after.roles) - set(before.roles)
                extra['role_update'] = 'add'
                extra['roles_added'] = [self.param_role(r) for r in roles_added]

            self.log_discord_event('member.update.roles', extra)

    def log_member_remove(self, member: Member):
        """Log member leaving the server."""
        extra = {
            'member': self.param_member(member)
        }
        self.log_discord_event("member.remove", extra)

    def log_message(self, message: Message):
        """Log message."""
        extra = {'content': message.content}
        extra.update(self.param_sca(message))
        extra.update(self.param_attachment(message))
        extra.update(self.param_mention(message))
        extra.update(self.param_embed(message))
        extra.update(self.param_emoji(message))
        extra.update(self.param_mention(message))
        self.log_discord_event('message', extra)

    def log_message_delete(self, message: Message):
        """Log deleted message."""
        extra = {'content': message.content}
        extra.update(self.param_sca(message))
        extra.update(self.param_mention(message))
        self.log_discord_event('message.delete', extra)

    def log_message_edit(self, before: Message, after: Message):
        """Log message editing."""
        extra = {
            'content_before': before.content,
            'content_after': after.content
        }
        extra.update(self.param_sca(after))
        extra.update(self.param_mention(after))
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
            servers_data.append(self.param_server(server))
        extra['servers'] = servers_data
        self.log_discord_gauge('servers', extra=extra)

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
        extra = {'channel': self.param_channel(channel)}
        self.log_discord_gauge('channel', extra=extra)

    def log_members(self):
        """Log members."""
        members = list(self.bot.get_all_members())
        unique = set(m.id for m in members)
        extra = {'member_count': len(members), 'unique_member_count': len(unique)}

        # log all members in single call
        # extra.update({"members": [self.param_member(m) for m in members]})
        self.log_discord_gauge('all_members', extra=extra)

        for member in members:
            self.log_member(member)

    def log_member(self, member: Member):
        """Log member."""
        extra = {'member': self.param_member(member)}
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
            extra['server'] = self.param_server(server)
            extra['roles'] = []

            roles = server.role_hierarchy

            # count number of members with a particular role
            for index, role in enumerate(roles):
                count = sum([1 for m in server.members if role in m.roles])

                role_params = self.param_role(role)
                role_params['count'] = count
                role_params['hierachy_index'] = index

                extra['roles'].append(role_params)

            self.log_discord_gauge('server.roles', extra)

    def log_server_channels(self):
        """Log server channels."""
        for server in self.bot.servers:
            extra = {
                'server': self.param_server(server),
                'channels': {
                    'text': [],
                    'voice': []
                }
            }
            channels = sorted(server.channels, key=lambda x: x.position)

            for channel in channels:
                channel_params = self.param_server_channel(channel)
                if channel.type == ChannelType.text:
                    extra['channels']['text'].append(channel_params)
                elif channel.type == ChannelType.voice:
                    extra['channels']['voice'].append(channel_params)

            self.log_discord_gauge('server.channels', extra)


class ESLogModel:
    """Elastic Search Logging Model.
    
    This is the settings file. It is placed in its own class so 
    settings doesn’t need to be a long chain of dict references,
    even though it still is under the hood.
    """

    def __init__(self, file_path, search: Search):
        """Init."""
        self.file_path = file_path
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(file_path))
        self.search = search

    @staticmethod
    def parser():
        """Process arguments."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]eslog messagecount')
        # parser.add_argument('key')
        parser.add_argument(
            '-t', '--time',
            default="7d",
            help="Time span in ES notation. 7d for 7 days, 1h for 1 hour"
        )
        parser.add_argument(
            '-c', '--count',
            type=int,
            default="10",
            help='Number of results')
        parser.add_argument(
            '-ec', '--excludechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '-ic', '--includechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '-eb', '--excludebot',
            action='store_true'
        )
        parser.add_argument(
            '-er', '--excluderoles',
            nargs='+',
            help='List of roles to exclude'
        )
        parser.add_argument(
            '-ir', '--includeroles',
            nargs='+',
            help='List of roles to include'
        )
        parser.add_argument(
            '-ebc', '--excludebotcommands',
            action='store_true'
        )
        parser.add_argument(
            '-s', '--split',
            default='channel',
            choices=['channel']
        )
        return parser

    def es_query_author(self, parser_arguments, server, member: Member):
        """Elasticsearch query for author"""
        p_args = parser_arguments

        time_gte = 'now-{}'.format(p_args.time)
        r = Range(timestamp={'gte': time_gte, 'lt': 'now'})

        source_list = ['author.id', 'author.roles', 'channel.id', 'channel.name', 'timestamp']

        query_str = (
            'discord_event:message'
            ' AND server.name:\"{server_name}\"'
            ' AND author.id:{author_id}'
        ).format(server_name=server.name, author_id=member.id)
        qs = QueryString(query=query_str)

        s = self.search.query(qs).query(r).source(source_list)
        return s

    def es_query_authors(self, parser_arguments, server):
        """Construct Elasticsearch query."""
        p_args = parser_arguments

        time_gte = 'now-{}'.format(p_args.time)

        query_str = (
            "discord_event:message"
            " AND server.name:\"{server_name}\""
        ).format(server_name=server.name)

        if p_args.excludebot:
            query_str += " AND author.bot:false"
        if p_args.excludechannels is not None:
            for channel_name in p_args.excludechannels:
                query_str += " AND !channel.name:\"{}\"".format(channel_name)
        if p_args.includechannels is not None:
            qs = ""
            for i, channel_name in enumerate(p_args.includechannels):
                if i > 0:
                    qs += " OR"
                qs += " channel.name:\"{}\"".format(channel_name)
            query_str += " AND ({})".format(qs)
        if p_args.excluderoles is not None:
            for role_name in p_args.excluderoles:
                query_str += " AND !author.roles.name:\"{}\"".format(role_name)
        if p_args.includeroles is not None:
            qs = ""
            for i, role_name in enumerate(p_args.includeroles):
                if i > 0:
                    qs += " AND"
                qs += " author.roles.name:\"{}\"".format(role_name)
            query_str += " AND ({})".format(qs)
        if p_args.excludebotcommands:
            cmd_prefix = ['!', '?', ';', '$']
            prefix_qs = [' AND !content.keyword:\{}*'.format(p) for p in cmd_prefix]
            query_str += ' '.join(prefix_qs)

        source_list = ['author.id', 'author.roles', 'channel.id', 'channel.name']

        qs = QueryString(query=query_str)
        r = Range(timestamp={'gte': time_gte, 'lt': 'now'})
        s = self.search.query(qs).query(r).source(source_list)
        return s

    def es_query_channels(self, parser_arguments, server):
        """Construct Elasticsearch query."""
        p_args = parser_arguments

        time_gte = 'now-{}'.format(p_args.time)

        query_str = (
            "discord_event:message"
            " AND server.name:\"{server_name}\""
        ).format(server_name=server.name)

        if p_args.excludebot:
            query_str += " AND author.bot:false"
        if p_args.excludechannels is not None:
            for channel_name in p_args.excludechannels:
                query_str += " AND !channel.name:\"{}\"".format(channel_name)
        if p_args.includechannels is not None:
            qs = ""
            for i, channel_name in enumerate(p_args.includechannels):
                if i > 0:
                    qs += " OR"
                qs += " channel.name:\"{}\"".format(channel_name)
            query_str += " AND ({})".format(qs)
        if p_args.excluderoles is not None:
            for role_name in p_args.excluderoles:
                query_str += " AND !author.roles.name:\"{}\"".format(role_name)
        if p_args.includeroles is not None:
            qs = ""
            for i, role_name in enumerate(p_args.includeroles):
                if i > 0:
                    qs += " AND"
                qs += " author.roles.name:\"{}\"".format(role_name)
            query_str += " AND ({})".format(qs)
        if p_args.excludebotcommands:
            cmd_prefix = ['!', '?', ';', '$']
            prefix_qs = [' AND !content.keyword:\{}*'.format(p) for p in cmd_prefix]
            query_str += ' '.join(prefix_qs)

        qs = QueryString(query=query_str)
        r = Range(timestamp={'gte': time_gte, 'lt': 'now'})

        s = self.search.query(qs).query(r).source([
            'channel.created_at',
            'channel.id',
            'channel.is_default',
            'channel.name',
            'channel.position',
            'channel.server.id',
            'channel.server.name',
            'channel.type.group',
            'channel.type.private',
            'channel.type.text',
            'channel.type.voice',
            'author.id'
        ])
        return s


class AuthorHits:
    """
    Construct results in this format:
    {
        "11111": {
            "author_id": "11111",
            "count": 100,
            "channels": {
                "12345": {
                    "channel_name": "Channel Name 1",
                    "count": 100,
                    "channel_id": "12345"
                },
                "23456": {
                    "channel_name": "Channel Name 2",
                    "count": 200,
                    "channel_id": "23456"
                },       
            } 
        }
    }
    """

    def __init__(self):
        self.authors = {}

    def max_author_count(self):
        """Maximum author count."""
        return max([ah.counter for k, ah in self.authors.items()])

    def add_hit(self, hit):
        if hit.author.id not in self.authors:
            self.authors[hit.author.id] = AuthorHit(hit)
        self.authors[hit.author.id].add_count()
        self.authors[hit.author.id].add_channel(hit)

    def sorted_author_list(self):
        """Sorted author list.
        Sort author list by author count and return result.
        
        """
        authors = [v for k, v in self.authors.items()]
        authors = sorted(authors, key=lambda ah: ah.counter, reverse=True)
        return authors

    def author_count_rank(self, author_id):
        """Return author rank by count."""
        authors = self.sorted_author_list()
        for rank, author_hit in enumerate(authors):
            if author_id == author_hit.author_id:
                return rank + 1


class AuthorHit:
    def __init__(self, hit):
        self.author_id = hit.author.id
        self.counter = 0
        self.channels = nested_dict()

    def add_count(self):
        self.counter += 1

    def add_channel(self, hit):
        channel_id = hit.channel.id
        channel_name = hit.channel.name
        if channel_id not in self.channels:
            self.channels[channel_id] = {
                "channel_name": channel_name,
                "channel_id": channel_id,
                "count": 1
            }
        else:
            self.channels[channel_id]["count"] += 1

    def sorted_channels(self):
        """List of channels sorted by count"""
        channels = [v for k, v in self.channels.items()]
        channels = sorted(channels, key = lambda c: c["count"], reverse=True)
        return channels

    def to_dict(self):
        return {
            'counter': self.counter,
            'channels': [{
                'channel_name': v['channel_name'],
                'channel_id': v['channel_id'],
                'count': v['count']
            } for k, v in self.channels.items()]
        }


class UserActivityModel:
    """User activitiy model."""

    def __init__(self, *args, **kwargs):
        """Init.
        
        Parameters:
        """
        self.__dict__.update(kwargs)


class ESLogView:
    """ESLog views.
    
    A collection of views depending on result types
    """
    def __init__(self, bot):
        self.bot = bot

    async def user_activity(self, server: Server, member: Member, hits, p_args, rank="_"):
        """User actvity"""
        await self.bot.type()

        title = "Member Activity: {}".format(member.display_name)
        description = self.description(p_args, show_top=False)
        color = random_discord_color()

        em = discord.Embed(title=title, description=description, color=color)

        em.add_field(name="Rank", value='{} / {}'.format(rank, len(server.members)))
        em.add_field(name="Messages", value='{}'.format(len(hits)))

        # sort hits chronologically
        hits = sorted(hits, key=lambda hit: hit.timestamp)

        # skip if no results
        if len(hits):
            last_hit = hits[-1]
            if hasattr(last_hit, 'timestamp'):
                dt_ts = dt.datetime.strptime(hits[-1].timestamp, "%Y-%m-%dT%H:%M:%S.%f")
                value = dt_ts.strftime("%Y-%m-%d %H:%M:%S UTC")
                em.add_field(name="Last seen", value=value)
        else:
            em.add_field(name="_", value="_")

        channel_ids = []
        for hit in hits:
            channel_ids.append(hit.channel.id)
        channel_id_counter = Counter(channel_ids)

        for channel_id, count in channel_id_counter.most_common(10):
            channel = server.get_channel(channel_id)
            em.add_field(name=channel.name, value='{} messages'.format(count))

        await self.bot.say(embed=em)

    @staticmethod
    def embed_message(hit):
        """Message events."""
        em = discord.Embed(title=hit.server.name, description="Message")
        em.add_field(name="channel.name", value=hit.channel.name)
        em.add_field(name="author.name", value=hit.author.name)
        em.add_field(name="content", value=hit.content)
        em.set_footer(text=hit["@timestamp"])
        return em

    @staticmethod
    def description(p_args, show_top=True):
        """Embed description based on supplied arguments."""
        descriptions = []
        descriptions.append('Time: {}.'.format(p_args.time))
        if p_args.includechannels is not None:
            descriptions.append('Including channels: {}.'.format(', '.join(p_args.includechannels)))
        if p_args.excludechannels is not None:
            descriptions.append('Excluding channels: {}.'.format(', '.join(p_args.excludechannels)))
        if p_args.includeroles is not None:
            descriptions.append('Including roles: {}.'.format(', '.join(p_args.includeroles)))
        if p_args.excluderoles is not None:
            descriptions.append('Excluding roles: {}.'.format(', '.join(p_args.excluderoles)))
        if p_args.excludebot:
            descriptions.append('Excluding bot users.')
        if p_args.excludebotcommands:
            descriptions.append('Excluding bot commands.')
        if show_top:
            descriptions.append('Showing top {} results.'.format(p_args.count))
        return ' '.join(descriptions)

    @staticmethod
    def inline_barchart(count, max_count):
        """Inline bar chart."""
        width = 30
        bar_count = int(width * (count / max_count))
        chart = '▇' * bar_count if bar_count > 0 else '░'
        return inline(chart)

    @staticmethod
    def channel_count(author_hit: AuthorHit):
        """Channel count. """
        channels = author_hit.sorted_channels()
        chart = ['{}: {}'.format(c["channel_name"], c["count"]) for c in channels]
        return ', '.join(chart)

    @staticmethod
    def embeds_user_rank(author_hits: AuthorHits, p_args, server):
        """User rank display."""
        title = 'Message count by author'
        description = ESLogView.description(p_args)
        color = random_discord_color()
        footer_text = server.name
        footer_icon_url = server.icon_url
        num_results = p_args.count

        em = discord.Embed(title=title, description=description, color=color)
        sorted_author_list = author_hits.sorted_author_list()
        sorted_author_list = sorted_author_list[:num_results]
        for rank, author_hit in enumerate(sorted_author_list, 1):
            counter = author_hit.counter
            author_id = author_hit.author_id
            member = server.get_member(author_id)
            if member is not None:
                name = member.display_name
            else:
                name = "User ID: {}".format(author_id)

            max_count = author_hits.max_author_count()

            if p_args.split is None:
                chart = ESLogView.inline_barchart(counter, max_count)
            elif p_args.split == 'channel':
                chart = '{}\n{}'.format(
                    ESLogView.inline_barchart(counter, max_count),
                    ESLogView.channel_count(author_hit)
                )
                # chart = ESLogView.inline_barchart(counter, max_count)
                # chart = ESLogView.channel_count(author_hit)
                # chart = ESLogView.inline_barchart(counter, max_count)

            em.add_field(
                name='{}. {}: {}'.format(rank, name, counter),
                value=chart,
                inline=False)
            rank += 1
        em.set_footer(text=footer_text, icon_url=footer_icon_url)

        return [em]

    @staticmethod
    def embeds_channel_rank(hit_counts, p_args, server):
        """Channel rank display.
        
        Available fields:
        s = search.query(qs).query(r).source([
            'channel.created_at',
            'channel.id',
            'channel.is_default',
            'channel.name',
            'channel.position',
            'channel.server.id',
            'channel.server.name',
            'channel.type.group',
            'channel.type.private',
            'channel.type.text',
            'channel.type.voice'
        ])
        
        """
        embeds = []
        # group by 25 for embeds
        hit_counts_group = grouper(25, hit_counts)

        title = 'Message count by channel'
        description = ESLogView.description(p_args)
        color = random_discord_color()
        footer_text = server.name
        footer_icon_url = server.icon_url

        rank = 1
        max_count = None

        for hit_counts in hit_counts_group:
            em = discord.Embed(title=title, description=description, color=color)
            for hit_count in hit_counts:
                if hit_count is not None:
                    count = hit_count["count"]
                    channel = server.get_channel(hit_count["channel_id"])
                    if channel is not None:
                        name = channel.name
                    else:
                        name = "Channel ID: {}".format(hit_count["channel_id"])
                    if max_count is None:
                        max_count = count

                    em.add_field(
                        name='{}. {}: {}'.format(rank, name, count),
                        value=ESLogView.inline_barchart(count, max_count),
                        inline=False)
                    rank += 1
            em.set_footer(text=footer_text, icon_url=footer_icon_url)
            embeds.append(em)
        return embeds



class ESLog:
    """Elastic Search Logging.
    
    Interface directly with ES. Logstash is used as the middleman in a previous iteration.
    This cog instead log directly into ES with the intention to have better control and also
    to allow fetching search results using bot comamnds.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot

        self.es = Elasticsearch()
        self.search = Search(using=self.es, index="discord-*")
        self.model = ESLogModel(JSON, self.search)

        self.extra = {
            'log_type': 'discord.logger',
            'application': 'red',
            'bot_id': self.bot.user.id,
            'bot_name': self.bot.user.name
        }

        self.eslogger = ESLogger(bot, self.es)
        self.eslogger2 = ESLogger2()

        # temporarily disable gauges
        self.task = bot.loop.create_task(self.loop_task())

        self.view = ESLogView(bot)

    def __unload(self):
        """Unhook logger when unloaded.

        Thanks Kowlin!
        """
        pass

    async def loop_task(self):
        """Loop task."""
        await self.bot.wait_until_ready()
        self.eslogger.init_extra()
        # temporarily disable gauges
        # self.eslogger.log_all_gauges()
        await asyncio.sleep(INTERVAL)
        if self is self.bot.get_cog('ESLog'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    async def eslogset(self, ctx):
        """ES Log settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @eslogset.command(name="logall", pass_context=True, no_pm=True)
    async def eslogset_logall(self, ctx):
        """Log all gauges."""
        self.eslogger.log_all_gauges()
        await self.bot.say("Logged all gauges.")

    @checks.serverowner_or_permissions()
    @commands.group(pass_context=True, no_pm=True)
    async def ownereslog(self, ctx):
        """Bot owner level data access.
        
        Mainly difference is that the bot owner is allowed to see data from another server
        since he/she admins those servers.
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @ownereslog.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def ownereslog_user(self, ctx, server_name, member: Member, *args):
        """User activity."""
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Cannot find server named {}.".format(server_name))
            return
        await self.search_user(ctx, server, member, *args)

    @ownereslog.command(name="users", aliases=['us'], pass_context=True, no_pm=True)
    async def ownereslog_users(self, ctx, server_name, *args):
        """Message count by user."""
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Cannot find server named {}.".format(server_name))
            return
        await self.search_message_authors(ctx, server, *args)

    @ownereslog.command(name="channel", aliases=['c'], pass_context=True, no_pm=True)
    async def ownereslog_channel(self, ctx, server_name, *args):
        """Message count by user."""
        server = discord.utils.get(self.bot.servers, name=server_name)
        if server is None:
            await self.bot.say("Cannot find server named {}.".format(server_name))
            return
        await self.search_channel(ctx, server, *args)

    @commands.group(pass_context=True, no_pm=True)
    async def eslog2(self, ctx):
        """Elastic search logging v2."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @eslog2.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def eslog_user2(self, ctx, member: discord.Member, *args):
        """Message statstics of a user."""
        self.eslogger2.search_author_messages(member)

    @commands.group(pass_context=True, no_pm=True)
    async def eslog(self, ctx):
        """Elastic Search Logging."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @eslog.command(name="users", aliases=['us'], pass_context=True, no_pm=True)
    async def eslog_users(self, ctx, *args):
        """Message count by users.
        
        Params:
        --time TIME, -t    
          Time in ES notation. 7d for 7 days, 1h for 1 hour
          Default: 7d (7 days)
        --count COUNT, -c   
          Number of results to show
          Default: 10
        --excludechannels EXCLUDECHANNEL [EXCLUDECHANNEL ...], -ec
          List of channels to exclude
        --includechannels INCLUDECHANNEL [INCLUDECHANNEL ...], -ic
          List of channels to include (multiples are interpreted as OR)
        --excluderoles EXCLUDEROLE [EXCLUDEROLE ...], -er
          List of roles to exclude
        --includeroles INCLUDEROLE [INCLUDEROLE ...], -ir
          List of roles to include (multiples are interpreted as AND)
        --excludebot, -eb
          Exclude bot accounts
        --excludebotcommands, -ebc
          Exclude bot commands. 
        --split {none, channel}, -s
          Split chart
        
        Example:
        [p]eslog user --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel
        
        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """
        server = ctx.message.server
        await self.search_message_authors(ctx, server, *args)

    @eslog.command(name="channel", aliases=['c'], pass_context=True, no_pm=True)
    async def eslog_channel(self, ctx, *args):
        """Message count by channel.

        Params:
        --time TIME, -t    
          Time in ES notation. 7d for 7 days, 1h for 1 hour
          Default: 7d (7 days)
        --count COUNT, -c   
          Number of results to show
          Default: 10
        --excludechannels EXCLUDECHANNEL [EXCLUDECHANNEL ...], -ec
          List of channels to exclude
        --includechannels INCLUDECHANNEL [INCLUDECHANNEL ...], -ic
          List of channels to include (multiples are interpreted as OR)
        --excluderoles EXCLUDEROLE [EXCLUDEROLE ...], -er
          List of roles to exclude
        --includeroles INCLUDEROLE [INCLUDEROLE ...], -ir
          List of roles to include (multiples are interpreted as AND)
        --excludebot, -eb
          Exclude bot accounts
        --excludebotcommands, -ebc
          Exclude bot commands. 

        Example:
        [p]eslog channel --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel

        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """
        server = ctx.message.server
        await self.search_channel(ctx, server, *args)

    @eslog.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def eslog_user(self, ctx, member: Member, *args):
        """Message statistics for a user."""
        server = ctx.message.server
        await self.search_user(ctx, server, member, *args)

    async def search_user(self, ctx, server, member: Member, *args):
        """Perform the server for users.
        
        1. Search against all authors to find relative rank in activity.
        2. Filter just that user to display other stats.
        """
        parser = ESLogModel.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        if member is None:
            await self.bot.say("Invalid user.")
            await send_cmd_help(ctx)
            return

        await self.bot.type()

        # 1. Get author activity rank
        s = self.model.es_query_authors(p_args, server)
        author_hits = AuthorHits()
        for hit in s.scan():
            author_hits.add_hit(hit)

        rank = author_hits.author_count_rank(member.id)

        # 2. Get author activity
        s = self.model.es_query_author(p_args, server, member)
        hits = []
        for hit in s.scan():
            hits.append(hit)

        await self.view.user_activity(server, member, hits, p_args, rank=rank)

    async def search_message_authors(self, ctx, server, *args):
        """Perform the search for authors."""
        parser = ESLogModel.parser()

        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            # await self.bot.send_message(ctx.message.channel, box(parser.format_help()))
            await send_cmd_help(ctx)
            return

        await self.bot.type()

        # s = ESLogModel.es_query_authors(p_args, self.search, server)
        s = self.model.es_query_authors(p_args, server)

        author_hits = AuthorHits()

        for hit in s.scan():
            author_hits.add_hit(hit)

        for em in ESLogView.embeds_user_rank(author_hits, p_args, server):
            await self.bot.say(embed=em)

    async def search_channel(self, ctx, server, *args):
        """Perform search for channels."""
        parser = ESLogModel.parser()

        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            # await self.bot.send_message(ctx.message.channel, box(parser.format_help()))
            await send_cmd_help(ctx)
            return

        await self.bot.type()

        s = self.model.es_query_channels(p_args, server)

        # perform search using scan()
        hit_counts = {}
        for hit in s.scan():
            if hit.channel.id in hit_counts:
                hit_counts[hit.channel.id] += 1
            else:
                hit_counts[hit.channel.id] = 1

        hit_counts = [{"channel_id": k, "count": v} for k, v in hit_counts.items()]
        hit_counts = sorted(hit_counts, key=lambda hit: hit["count"], reverse=True)

        max_results = p_args.count

        hit_counts = hit_counts[:max_results]

        for em in ESLogView.embeds_channel_rank(hit_counts, p_args, server):
            await self.bot.say(embed=em)

    # Events
    async def on_channel_create(self, channel: Channel):
        """Track channel creation."""
        self.eslogger.log_channel_create(channel)

    async def on_channel_delete(self, channel: Channel):
        """Track channel deletion."""
        self.eslogger.log_channel_delete(channel)

    async def on_command(self, command: Command, ctx: Context):
        """Track command usage."""
        self.eslogger.log_command(command, ctx)

    async def on_message(self, message: Message):
        """Track on message."""
        self.eslogger.log_message(message)
        self.eslogger2.log_message(message)
        # self.log_emojis(message)

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        self.eslogger.log_message_delete(message)
        self.eslogger2.log_message_delete(message)

    async def on_message_edit(self, before: Message, after: Message):
        """Track message editing."""
        self.eslogger.log_message_edit(before, after)

    async def on_member_join(self, member: Member):
        """Track members joining server."""
        self.eslogger.log_member_join(member)

    async def on_member_update(self, before: Member, after: Member):
        """Called when a Member updates their profile.

        Only track status after.
        """
        self.eslogger.log_member_update(before, after)

    async def on_member_remove(self, member: Member):
        """Track members leaving server."""
        self.eslogger.log_member_remove(member)

    async def on_ready(self):
        """Bot ready."""
        self.eslogger.log_all_gauges()

    async def on_resume(self):
        """Bot resume."""
        self.eslogger.log_all_gauges()


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
    n = ESLog(bot)
    bot.add_cog(n)