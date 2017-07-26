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
from collections import OrderedDict
from datetime import timedelta
from random import choice

import discord
from __main__ import send_cmd_help
import sparklines
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
from elasticsearch_dsl import Search, FacetedSearch, TermsFacet
from elasticsearch_dsl.query import QueryString, Query, Q, Filtered, Match
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


class ServerDoc(DocType):
    """Server Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class ChannelDoc(DocType):
    """Channel Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class RoleDoc(DocType):
    """Role Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class UserDoc(DocType):
    """Discord user."""
    name = Text(fields={'raw': Keyword()})
    id = Integer()
    discriminator = Integer()
    bot = Boolean()
    avatar_url = Text(
        analyzer=analyzer("simple"),
        fields={'raw': Keyword()})

    class Meta:
        doc_type = 'user'


class MemberDoc(UserDoc):
    """Discord member."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})
    display_name = Text(fields={'raw': Keyword()})
    bot = Boolean()
    top_role = Nested(doc_class=RoleDoc)
    roles = Nested(doc_class=RoleDoc)
    server = Nested(doc_class=ServerDoc)

    class Meta:
        doc_type = 'member'

    @classmethod
    def member_dict(cls, member):
        """Member dictionary."""
        d = {
            'id': member.id,
            'username': member.name,
            'bot': member.bot
        }
        if isinstance(member, Member):
            d.update({
                'name': member.display_name,
                'display_name': member.display_name,
                'roles': [
                    {'id': r.id, 'name': r.name} for r in member.roles
                ],
                'top_role': {
                    'id': member.top_role.id,
                    'name': member.top_role.name
                },
                'joined_at': member.joined_at
            })
        return d


class MemberJoinDoc(MemberDoc):
    """Discord member join"""

    class Meta:
        doc_type = 'member_join'

    @classmethod
    def log(cls, member, **kwargs):
        pass


class MessageDoc(DocType):
    """Discord Message."""
    id = Integer()
    content = Text(
        analyzer=analyzer("simple"),
        fields={'raw': Keyword()}
    )
    author = Nested(doc_class=MemberDoc)
    server = Nested(doc_class=ServerDoc)
    channel = Nested(doc_class=ChannelDoc)
    mentions = Nested(doc_class=MemberDoc)
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

    def set_author(self, author):
        """Set author."""
        self.author = MemberDoc.member_dict(author)

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
        self.mentions = [MemberDoc.member_dict(m) for m in mentions]

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


class MessageAuthorSearch(FacetedSearch):
    doc_types = [MessageDoc]
    fields = ['author']
    facets = {
        'channel': TermsFacet(field='channel')
    }


class ESLogger:
    """Elastic Search Logging v2.
    
    Separated into own class to make migration easier.
    """
    def __init__(self, index_name_fmt=None):
        self.index_name_fmt = index_name_fmt

    @property
    def index_name(self):
        """ES index name.
        
        Automatically generated using current time.
        """
        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')
        index_name = self.index_name_fmt.format(now_str)
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

    @staticmethod
    def parser():
        """Process arguments."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]eslog messagecount')
        # parser.add_argument('key')
        parser.add_argument(
            '-t', '--time',
            default="1d",
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

    def search_author_messages(self, author):
        """Search messages by author."""
        s = MessageDoc.search()
        time_gte = 'now-1d'

        s = s.filter('match', **{'author.id': author.id}) \
            .query(Range(timestamp={'gte': time_gte, 'lt': 'now'}))
        for message in s.scan():
            print('-'*40)
            print(message.to_dict())

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

    def embed_member(self, member=None,
                     message_count=0, active_members=0, rank=0, channels=None,
                     last_seen=None, p_args=None):
        """User view."""
        em = discord.Embed(
            title="Member Activity: {}".format(member.display_name),
            description=self.description(p_args, show_top=False),
            color=random_discord_color()
        )

        em.add_field(
            name="Rank",
            value="{} / {} (active) / {} (all)".format(
                rank, active_members, len(member.server.members)
            )
        )
        em.add_field(name="Messages", value=message_count)
        last_seen_str = last_seen.strftime("%Y-%m-%d %H:%M:%S UTC")
        em.add_field(name="Last seen", value=last_seen_str)

        max_count = None

        for channel_id, count in channels.items():
            if max_count is None:
                max_count = count
            channel = member.server.get_channel(channel_id)
            chart = ESLogView.inline_barchart(count, max_count)
            em.add_field(
                name='{}: {} message'.format(channel.name, count),
                value=chart,
                inline=False)

        return em




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


class MessageDocSearch:
    """Message author.
    
    Initialized with a list of all messages.
    Find the author’s relative rank and other properties.
    """
    def __init__(self, **kwargs):
        self.search = MessageDoc.search(**kwargs)

    def time_range(self, time):
        """ES Range in time"""
        time_gte = 'now-{}'.format(time)
        return Range(timestamp={'gte': time_gte, 'lt': 'now'})

    def active_members(self, server, time):
        """Number of active users during this period."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': server.id}))
        return len(set([doc.author.id for doc in s.scan()]))

    def author_lastseen(self, author):
        """Last known date where author has send a message."""
        server = author.server
        s = self.search \
            .query(Match(**{'server.id': server.id})) \
            .query(Match(**{'author.id': author.id})) \
            .sort({'timestamp': {'order': 'desc'}})
        s = s[0]
        for hit in s.execute():
            return hit.timestamp

    def author_rank(self, author, time):
        """Author’s activity rank on a server."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': author.server.id}))

        author_ids = [doc.author.id for doc in s.scan()]
        counter = Counter(author_ids)
        for rank, (author_id, count) in enumerate(counter.most_common(), 1):
            if author_id == author.id:
                return rank
        return 0

    def author_messages_search(self, author, time):
        """"All of author’s activity on a server."""
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': author.server.id})) \
            .query(Match(**{'author.id': author.id}))
        return s

    def author_messages_count(self, author, time):
        """Total of author’s activity on a server."""
        return self.author_messages_search(author, time).count()

    def author_channels(self, author, time):
        """Author’s activity by channel on a server.
        
        Return as OrderedDict with channel IDs and count.
        """
        s = self.author_messages_search(author, time)
        channel_ids = [doc.to_dict()["channel"]["id"] for doc in s.scan()]
        channels = OrderedDict()
        for channel_id, count in Counter(channel_ids).most_common():
            channels[channel_id] = count
        return channels

    def server_messages(self, server, parser_args):
        """all of server messages."""
        time = parser_args.time
        s = self.search \
            .query(self.time_range(time)) \
            .query(Match(**{'server.id': server.id})) \
            .sort({'timestamp': {'order': 'asc'}})
        return s


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
        self.message_search = MessageDocSearch(index="discord-*")
        # self.model = ESLogModel(JSON, self.search)

        # self.extra = {
        #     'log_type': 'discord.logger',
        #     'application': 'red',
        #     'bot_id': self.bot.user.id,
        #     'bot_name': self.bot.user.name
        # }

        self.eslogger = ESLogger(index_name_fmt='discord-{}')

        # temporarily disable gauges
        # self.task = bot.loop.create_task(self.loop_task())

        self.view = ESLogView(bot)

    def __unload(self):
        """Unhook logger when unloaded.

        Thanks Kowlin!
        """
        pass

    # async def loop_task(self):
    #     """Loop task."""
    #     await self.bot.wait_until_ready()
    #     self.eslogger.init_extra()
    #     # temporarily disable gauges
    #     # self.eslogger.log_all_gauges()
    #     await asyncio.sleep(INTERVAL)
    #     if self is self.bot.get_cog('ESLog'):
    #         self.task = self.bot.loop.create_task(self.loop_task())

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
    async def eslog(self, ctx):
        """Elasticsearch Log"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @eslog.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def eslog_user(self, ctx, member: Member, *args):
        """Message statistics by user.
        
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
        parser = ESLogger.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        author = ctx.message.author

        if member is None:
            member = author

        await self.bot.type()

        mds = self.message_search

        time = p_args.time
        rank = mds.author_rank(member, time)
        channels = mds.author_channels(member, time)
        active_members = mds.active_members(member.server, time)
        message_count = mds.author_messages_count(member, time)
        last_seen = mds.author_lastseen(member)

        await self.bot.say(
            embed=self.view.embed_member(
                member=member,
                active_members=active_members,
                rank=rank,
                channels=channels,
                p_args=p_args,
                message_count=message_count,
                last_seen=last_seen
            ))

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
        parser = ESLogger.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        await self.bot.type()
        server = ctx.message.server
        s = self.message_search.server_messages(server, p_args)

        """
        Create a list of counts over time intervals
        """
        docs = [doc for doc in s.scan()]
        docs = sorted(docs, key=lambda doc: doc.timestamp)

        start = docs[0].timestamp
        steps = 30
        now = dt.datetime.utcnow()
        interval = (now - start) / steps

        timed_docs = OrderedDict()
        for index in range(steps):
            timed_docs[index] = []
        for doc in docs:
            time_index = (doc.timestamp - start) // interval
            timed_docs[time_index].append(doc)

        for k, docs in timed_docs.items():
            print(k)
            for doc in docs:
                print(doc.timestamp)



        #     if start is None:
        #         start = doc.timestamp
        #     end = start + td / steps
        #
        #     print(doc, start, end, doc.timestamp)
        #
        #     count = messages.get(doc.author.id, 1)
        #     messages[doc.author.id] = count + 1
        #
        #     if doc.timestamp > end:
        #         start = end
        #         messages_over_time.append(messages)
        #         messages = {}
        #
        # print(messages_over_time)







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

    async def search_user(self, ctx, server, member: Member, *args):
        """Perform the search for users.
        
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
    # async def on_channel_create(self, channel: Channel):
    #     """Track channel creation."""
    #     self.eslogger.log_channel_create(channel)
    #
    # async def on_channel_delete(self, channel: Channel):
    #     """Track channel deletion."""
    #     self.eslogger.log_channel_delete(channel)
    #
    # async def on_command(self, command: Command, ctx: Context):
    #     """Track command usage."""
    #     self.eslogger.log_command(command, ctx)

    async def on_message(self, message: Message):
        """Track on message."""
        self.eslogger.log_message(message)
        # self.eslogger2.log_message(message)
        # self.log_emojis(message)

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        self.eslogger.log_message_delete(message)
        # self.eslogger2.log_message_delete(message)

    # async def on_message_edit(self, before: Message, after: Message):
    #     """Track message editing."""
    #     self.eslogger.log_message_edit(before, after)
    #
    # async def on_member_join(self, member: Member):
    #     """Track members joining server."""
    #     self.eslogger.log_member_join(member)
    #
    # async def on_member_update(self, before: Member, after: Member):
    #     """Called when a Member updates their profile.
    #
    #     Only track status after.
    #     """
    #     self.eslogger.log_member_update(before, after)
    #
    # async def on_member_remove(self, member: Member):
    #     """Track members leaving server."""
    #     self.eslogger.log_member_remove(member)
    #
    # async def on_ready(self):
    #     """Bot ready."""
    #     self.eslogger.log_all_gauges()
    #
    # async def on_resume(self):
    #     """Bot resume."""
    #     self.eslogger.log_all_gauges()


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