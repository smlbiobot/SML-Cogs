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

from cogs.utils.chat_formatting import inline
from cogs.utils.dataIO import dataIO

HOST = 'localhost'
PORT = 9200
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


# global ES connection
from elasticsearch_dsl.connections import connections
connections.create_connection(hosts=[HOST], timeout=20)


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

        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')

        extra['timestamp'] = now

        self.es.index(
            index='discord-{}'.format(now_str),
            doc_type='discord',
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
        self.log_discord_gauge('servers', extra=extra)
        # self.logger.info(self.get_event_key(event_key), extra=extra)

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
            channels = sorted(server.channels, key=lambda x: x.position)

            for channel in channels:
                channel_params = self.get_server_channel_params(channel)
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

    def __init__(self, file_path):
        """Init."""
        self.file_path = file_path
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(file_path))

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
        return parser

    @staticmethod
    def es_query(parser_arguments, search, server):
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

        s = search.query(qs).query(r).source(['author.id', 'author.roles'])
        return s


class ESLogView:
    """ESLog views.
    
    A collection of views depending on result types
    """
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
    def embeds_user_rank(hit_counts, p_args, server):
        """User rank display."""
        embeds = []
        # group by 25 for embeds
        hit_counts_group = grouper(25, hit_counts)

        title = 'Message count by author'
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
        descriptions.append('Showing top {} results.'.format(p_args.count))
        description = ' '.join(descriptions)
        footer_text = server.name
        footer_icon_url = server.icon_url

        rank = 1
        max_count = None
        color = random_discord_color()
        for hit_counts in hit_counts_group:
            em = discord.Embed(title=title, description=description, color=color)
            for hit_count in hit_counts:
                if hit_count is not None:
                    count = hit_count["count"]
                    member = server.get_member(hit_count["author_id"])
                    if member is not None:
                        name = member.display_name
                    else:
                        name = "User ID: {}".format(hit_count["author_id"])
                    if max_count is None:
                        max_count = count

                    # chart
                    width = 30
                    bar_count = int(width * (count / max_count))
                    chart = '▇' * bar_count if bar_count > 0 else '░'

                    em.add_field(name='{}. {}: {}'.format(rank, name, count), value=inline(chart), inline=False)
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
        self.model = ESLogModel(JSON)

        self.es = Elasticsearch()
        self.search = Search(using=self.es, index="discord-*")

        self.extra = {
            'log_type': 'discord.logger',
            'application': 'red',
            'bot_id': self.bot.user.id,
            'bot_name': self.bot.user.name
        }

        self.eslogger = ESLogger(bot, self.es)

        self.task = bot.loop.create_task(self.loop_task())

    def __unload(self):
        """Unhook logger when unloaded.

        Thanks Kowlin!
        """
        pass
        # self.logger.removeHandler(self.handler)
        # logging.getLogger("red").removeHandler(self.handler)

    async def loop_task(self):
        """Loop task."""
        # pass
        # disabled to see if it is causing memory problems
        await self.bot.wait_until_ready()
        self.eslogger.init_extra()
        self.eslogger.log_all_gauges()
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

    @commands.group(pass_context=True, no_pm=True)
    async def eslog(self, ctx):
        """Elastic Search Logging."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @eslog.command(name="message", pass_context=True, no_pm=True)
    async def eslog_message(self, ctx, time="7d", server_name=None):
        """Search ES.
        
        TODO
        
        Params:
            time: in ES format, e.g. 7d for 7 days
        
        """
        if server_name is None:
            server_name = ctx.message.server.name

        time_gte = 'now-{}'.format(time)

        qs = QueryString(query="discord_event:message AND author.bot:false AND server.name:\"Reddit Alpha Clan Family\"")
        r = Range(** {'@timestamp': {'gte': time_gte, 'lt': 'now'}})

        s = self.search.query(qs).query(r)
        response = s.execute()
        await self.bot.say("Number of results: {}".format(s.count()))

        for h in response:
            em = ESLogView.embed_message(h)
            await self.bot.say(embed=em)

    @eslog.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def eslog_user(self, ctx, *args):
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
        
        Example:
        [p]eslog messagecount --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel
        
        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """
        parser = ESLogModel.parser()

        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            # await self.bot.send_message(ctx.message.channel, box(parser.format_help()))
            await send_cmd_help(ctx)
            return

        await self.bot.type()

        server = ctx.message.server
        s = ESLogModel.es_query(p_args, self.search, server)

        # print(s.to_dict())
        # print(s.count())

        # perform search using scan()
        hit_counts = {}
        for hit in s.scan():
            if hit.author.id in hit_counts:
                hit_counts[hit.author.id] += 1
            else:
                hit_counts[hit.author.id] = 1

        hit_counts = [{"author_id": k, "count": v} for k, v in hit_counts.items()]
        hit_counts = sorted(hit_counts, key=lambda hit: hit["count"], reverse=True)

        max_results = p_args.count

        hit_counts = hit_counts[:max_results]

        for em in ESLogView.embeds_user_rank(hit_counts, p_args, server):
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
        # self.log_emojis(message)

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        self.eslogger.log_message_delete(message)

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