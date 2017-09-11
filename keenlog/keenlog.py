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
import datetime as dt
import itertools
import os
import pprint
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import timedelta
from random import choice

import discord
from __main__ import send_cmd_help
from discord import Member
from discord import Message
from discord.ext import commands
from elasticsearch_dsl import DocType, Date, Nested, Boolean, \
    analyzer, Keyword, Text, Integer
from elasticsearch_dsl import FacetedSearch, TermsFacet
# global ES connection
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl.query import Match, Range, Q

from cogs.utils import checks
from cogs.utils.chat_formatting import inline, pagify, box
from cogs.utils.dataIO import dataIO


INTERVAL = timedelta(hours=4).seconds

PATH = os.path.join('data', 'keenlog')
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


class BaseModel:
    """Base model."""
    def __init__(self, *args, **kwargs):
        pass


class ServerDoc(BaseModel):
    """Server Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class ChannelDoc(BaseModel):
    """Channel Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class RoleDoc(BaseModel):
    """Role Inner Object."""
    id = Integer()
    name = Text(fields={'raw': Keyword()})


class UserDoc(BaseModel):
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


class MemberDoc(BaseModel):
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


class MessageDoc(BaseModel):
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


class KeenLogger:
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
        parser = argparse.ArgumentParser(prog='[p]keenlog uers')
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

    def search_author_messages(self, author):
        """Search messages by author."""
        s = MessageDoc.search()
        time_gte = 'now-1d'

        s = s.filter('match', **{'author.id': author.id}) \
            .query(Range(timestamp={'gte': time_gte, 'lt': 'now'}))
        for message in s.scan():
            print('-' * 40)
            print(message.to_dict())


class KeenLogView:
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
            chart = KeenLogView.inline_barchart(count, max_count)
            em.add_field(
                name='{}: {} message'.format(channel.name, count),
                value=chart,
                inline=False)

        return em

    def embed_members(self, server=None, results=None, p_args=None):
        """Results by members"""
        results = sorted(results, key=lambda x: x["timestamp"])

        count = 10
        if p_args.count is not None:
            count = p_args.count

        most_common_author_ids = Counter([r["doc"].author.id for r in results]).most_common(count)

        # split results in channel ids by count
        author_channels = nested_dict()
        for author_id, count in most_common_author_ids:
            channel_ids = []
            for result in results:
                doc = result["doc"]
                if doc.author.id == author_id:
                    channel_ids.append(doc.channel.id)
            author_channels[author_id] = Counter(channel_ids).most_common()

        # embed
        embed = discord.Embed(
            title="{}: User activity by messages".format(server.name),
            description=self.description(p_args),
            color=random_discord_color()
        )

        max_count = 0
        for rank, (author_id, count) in enumerate(most_common_author_ids, 1):
            max_count = max(count, max_count)
            # author name
            author = server.get_member(author_id)
            if author is None:
                author_name = 'User {}'.format(author_id)
            else:
                author_name = server.get_member(author_id).display_name

            inline_chart = self.inline_barchart(count, max_count)
            # channels
            channel_str = ', '.join([
                '{}: {}'.format(
                    server.get_channel(
                        cid), count) for cid, count in author_channels[author_id]])

            # output
            field_name = '{}. {}: {}'.format(rank, author_name, count)
            field_value = '{}\n{}'.format(
                inline(inline_chart),
                channel_str)
            embed.add_field(name=field_name, value=field_value, inline=False)

        return embed

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


class MessageSearch:
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

    def server_author_messages(self, server, author, parser_args):
        """An author’s messages on a specific server."""
        time = parser_args.time
        s = self.search \
            .query(Match(**{'server.id': server.id})) \
            .query(Match(**{'author.id': author.id})) \
            .query(self.time_range(time)) \
            .sort({'timestamp': {'order': 'asc'}})
        return s

    def server_members_heatmap(self, server, parser_args=None):
        """Members heatmap.

        Kibana Visualization request:
        {
          "query": {
            "bool": {
              "must": [
                {
                  "query_string": {
                    "query": "_type:message AND server.name:\"Reddit Alpha Clan Family\" AND author.bot:false",
                    "analyze_wildcard": true
                  }
                },
                {
                  "range": {
                    "timestamp": {
                      "gte": 1501018393274,
                      "lte": 1501104793274,
                      "format": "epoch_millis"
                    }
                  }
                }
              ],
              "must_not": []
            }
          },
          "size": 0,
          "_source": {
            "excludes": []
          },
          "aggs": {
            "3": {
              "terms": {
                "field": "author.name.keyword",
                "size": 20,
                "order": {
                  "_count": "desc"
                }
              },
              "aggs": {
                "2": {
                  "date_histogram": {
                    "field": "timestamp",
                    "interval": "30m",
                    "time_zone": "Asia/Shanghai",
                    "min_doc_count": 1
                  }
                }
              }
            }
          }
        }
        """
        time = parser_args.time
        s = self.search \
            .query(Match(**{'server.id': server.id})) \
            .query(self.time_range(time)) \
            .sort({'timestamp': {'order': 'asc'}})

        s.aggs.bucket('author_names', 'terms', field='author.name.keyword') \
            .bucket('overtime', 'date_histogram', field='timestamp', interval='30m')
        return s


class KeenLog:
    """Keen.IO Logging.

    Event interface.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.message_search = MessageSearch(index="discord-*")
        self.eslogger = KeenLogger(index_name_fmt='discord-{}')
        self.view = KeenLogView(bot)

    @commands.group(pass_context=True, no_pm=True)
    async def keenlogset(self, ctx):
        """ES Log settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @keenlogset.command(name="logall", pass_context=True, no_pm=True)
    async def keenlogset_logall(self, ctx):
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

    @ownereslog.command(name="users", pass_context=True, no_pm=True)
    async def ownerkeenlog_users(self, ctx, *args):
        """Show debug"""
        parser = KeenLogger.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        await self.bot.type()
        server = ctx.message.server
        s = self.message_search.server_messages(server, p_args)

        results = [{
            "author_id": doc.author.id,
            "channel_id": doc.channel.id,
            "timestamp": doc.timestamp,
            "rng_index": None,
            "rng_timestamp": None,
            "doc": doc
        } for doc in s.scan()]

        p = pprint.PrettyPrinter(indent="4")
        out = p.pformat(results)

        for page in pagify(out, shorten_by=80):
            await self.bot.say(box(page, lang='py'))

    @commands.group(pass_context=True, no_pm=True)
    async def keenlog(self, ctx):
        """Elasticsearch Log"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @keenlog.command(name="user", aliases=['u'], pass_context=True, no_pm=True)
    async def keenlog_user(self, ctx, member: Member = None, *args):
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
        --excludebotcommands, -ebc
          Exclude bot commands. 

        Example:
        [p]keenlog user --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel

        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """
        parser = KeenLogger.parser()
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

    @keenlog.command(name="users", aliases=['us'], pass_context=True, no_pm=True)
    async def keenlog_users(self, ctx, *args):
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
        [p]keenlog user --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel

        Note:
        It might take a few minutes to process for servers which have many users and activity.
        """
        parser = KeenLogger.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        await self.bot.type()
        server = ctx.message.server

        s = MessageDoc.search()
        s = s.filter('match', **{'server.id': server.id})

        if p_args.time is not None:
            s = s.filter('range', timestamp={'gte': 'now-{}/m'.format(p_args.time), 'lte': 'now/m'})
        if p_args.includechannels is not None:
            for channel in p_args.includechannels:
                s = s.filter('match', **{'channel.name.keyword': channel})
        if p_args.excludechannels is not None:
            for channel in p_args.excludechannels:
                s = s.query('bool', must_not=[Q('match', **{'channel.name.keyword': channel})])
        if p_args.includeroles is not None:
            for role in p_args.includeroles:
                s = s.filter('match', **{'author.roles.name.keyword': role})
        if p_args.excluderoles is not None:
            for role in p_args.excluderoles:
                s = s.query('bool', must_not=[Q('match', **{'author.roles.name.keyword': role})])
        if p_args.excludebot:
            s = s.filter('match', **{'author.bot': False})

        # s = self.message_search.server_messages(server, p_args)

        results = [{
            "author_id": doc.author.id,
            "channel_id": doc.channel.id,
            "timestamp": doc.timestamp,
            "rng_index": None,
            "rng_timestamp": None,
            "doc": doc
        } for doc in s.scan()]

        server = ctx.message.server

        embed = self.view.embed_members(server, results, p_args)
        await self.bot.say(embed=embed)

    @keenlog.command(name="userheatmap", pass_context=True, no_pm=True)
    async def keenlog_userheatmap(self, ctx, *args):
        """User heat map"""
        parser = KeenLogger.parser()
        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        s = self.message_search.server_members_heatmap(server, p_args)

        p = pprint.PrettyPrinter(indent="4")
        for hit in s.scan():
            p.pprint(hit.to_dict())

    async def on_message(self, message: Message):
        """Track on message."""
        self.eslogger.log_message(message)

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        self.eslogger.log_message_delete(message)

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
    n = KeenLog(bot)
    bot.add_cog(n)
