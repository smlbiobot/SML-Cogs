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
from collections import Counter, defaultdict
from datetime import timedelta
from random import choice

import discord
import keen
from __main__ import send_cmd_help
from discord import Member
from discord import Message
from discord.ext import commands
# global ES connection
from elasticsearch_dsl.query import Q

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

    def save(self, *args, **kwargs):
        pass


class ServerModel(BaseModel):
    """Server Inner Object."""

    def __init__(self, server):
        """Init."""
        self.server = server

    def to_dict(self):
        """Return as dictionary."""
        return {
            "id": self.server.id,
            "name": self.server.name
        }


class ChannelModel(BaseModel):
    """Server Inner Object."""

    def __init__(self, channel):
        """Init."""
        self.channel = channel

    def to_dict(self):
        """Return as dictionary."""
        return {
            "id": self.channel.id,
            "name": self.channel.name,
            "is_default": self.channel.is_default,
            "position": self.channel.position
        }


class RoleModel(BaseModel):
    """Role Inner Object."""

    def __init__(self, role):
        """Init."""
        self.role = role

    def to_dict(self):
        """Return as dictionary."""
        return {
            "id": self.role.id,
            "name": self.role.name,
            "position": self.role.position,
            "color": {
                "rgb": self.role.color.to_tuple(),
                "value": self.role.color.value
            },
            "created_at": self.role.created_at.isoformat()
        }

class RolesModel(BaseModel):
    """Roles."""
    def __init__(self, roles):
        self.roles = roles

    def to_dict(self):
        """Return as dictionary."""
        d = []
        for role in self.roles:
            role_dict = RoleModel(role).to_dict()
            d.append(role_dict)
        d = sorted(d, key=lambda r: r["position"])
        return {r["position"]: r for r in d}


class UserModel(BaseModel):
    """Discord user."""

    def __init__(self, user):
        self.user = user

    def to_dict(self):
        """Return member as dictionary."""
        return {
            "name": self.user.name,
            "id": self.user.id,
            "discriminator": self.user.discriminator,
            "bot": self.user.bot,
            "avatar_url": self.user.avatar_url,
            "created_at": self.user.created_at.isoformat()
        }


class MemberModel(BaseModel):
    """Discord member."""

    def __init__(self, member):
        self.member = member

    def to_dict(self):
        """Return member as dictionary."""
        d = UserModel(self.member).to_dict()
        if isinstance(self.member, Member):
            d.update({
                'name': self.member.display_name,
                'display_name': self.member.display_name,
                'roles': RolesModel(self.member.roles).to_dict(),
                'top_role': RoleModel(self.member.top_role).to_dict(),
                'joined_at': self.member.joined_at.isoformat(),
            })
        return d


class BaseEventModel:
    """Base event."""

    def __init__(self):
        pass

    @property
    def event_dict(self):
        return {}

    def save(self):
        """Save to keen"""
        print("please overwrite")


class MemberEventModel(BaseEventModel):
    """Discord member events."""

    def __init__(self, member):
        """Init."""
        self.member = member

    @property
    def event_dict(self):
        """Keen event."""
        return {
            "member": MemberModel(self.member).to_dict()
        }

    def save(self):
        """Save to Keen."""
        pass


class MemberJoinEventModel(MemberEventModel):
    """Discord member joins server."""

    def save(self):
        """Save to Keen."""
        keen.add_event("member_join", self.event_dict)


class MemberRemoveEventModel(MemberEventModel):
    """Discord member leaves server."""

    def save(self):
        """Save to Keen."""
        keen.add_event("member_remove", self.event_dict)


class MemberUpdateEventModel(BaseEventModel):
    """Discord member joins server."""

    def __init__(self, before, after):
        """Init."""
        self.before = before
        self.after = after

    @property
    def event_dict(self):
        """Keen event."""
        return {
            "before": MemberModel(self.before).to_dict(),
            "after": MemberModel(self.after).to_dict()
        }

    def save(self):
        """Save to Keen."""
        keen.add_event("member_update", self.event_dict)


class MessageEventModel(BaseEventModel):
    """Discord Message."""

    def __init__(self, message):
        self.message = message

    @property
    def author(self):
        """Message author."""
        return MemberModel(self.message.author).to_dict()

    @property
    def server(self):
        """Message server."""
        server = self.message.server
        if server is not None:
            return ServerModel(server).to_dict()
        return None

    @property
    def channel(self):
        """Message channel."""
        channel = self.message.channel
        if channel is not None:
            return ChannelModel(channel).to_dict()
        return None

    @property
    def mentions(self):
        """Message mentions."""
        return [MemberModel(m).to_dict() for m in self.message.mentions]

    @property
    def event_dict(self):
        """Keen event dictionary."""
        return {
            "author": self.author,
            "server": self.server,
            "channel": self.channel,
            "mentions": self.mentions,
            "content": self.message.content,
            "id": self.message.id,
            "embeds": self.message.embeds,
            "attachments": self.message.attachments
        }

    def save(self, **kwargs):
        """Save to Keen."""
        keen.add_event("message", self.event_dict)


class MessageDeleteEventModel(MessageEventModel):
    """Discord Message Delete."""

    def save(self, **kwargs):
        """Save to Keen."""
        keen.add_event("message_delete", self.event_dict)


class MessageEditEventModel(BaseEventModel):
    """Discord Message Edit."""

    def __init__(self, before, after):
        self.before = MessageEventModel(before)
        self.after = MessageEventModel(after)

    @property
    def event_dict(self):
        """Keen event dictionary."""
        return {
            "before": self.before.event_dict,
            "after": self.after.event_dict
        }

    def save(self):
        """Save Keen event."""
        keen.add_event("message_edit", self.event_dict)


class ServerStatsModel(BaseEventModel):
    """Discord server stats."""

    def __init__(self, server):
        self.server = server

    @property
    def event_dict(self):
        """Keen event dictionary."""
        d = {
            "server": ServerModel(self.server).to_dict(),
            "roles": {},
            "channels": {},
            "member_count": len(self.server.members),
            "role_count": len(self.server.roles),
            "channel_count": len(self.server.channels)
        }
        for role in self.server.roles:
            rm = RoleModel(role).to_dict()
            rm["count"] = sum([1 for member in self.server.members if role in member.roles])
            d["roles"][role.position] = rm
        for channel in self.server.channels:
            d["channels"][channel.position] = ChannelModel(channel).to_dict()
        return d

    def save(self):
        """Save keen event."""
        keen.add_event("server_stats", self.event_dict)


class KeenLogger:
    """Elastic Search Logging v2.

    Separated into own class to make migration easier.
    """

    def __init__(self):
        pass

    @property
    def now(self):
        """Current time"""
        return dt.datetime.utcnow()

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


class KeenLog:
    """Keen.IO Logging.

    Event interface.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        # TODO: remove KeenLogger
        self.keenlogger = KeenLogger()
        self.view = KeenLogView(bot)
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        keen.project_id = self.settings["keen_project_id"]
        keen.read_key = self.settings["keen_read_key"]
        keen.write_key = self.settings["keen_write_key"]

    @commands.group(pass_context=True)
    async def keenlogset(self, ctx):
        """ES Log settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.is_owner()
    @keenlogset.command(name="api", pass_context=True)
    async def keenlogset_api(self, ctx, project_id=None, read_key=None, write_key=None):
        """API settings.
        
        Set API settings according to the console.
        If no settings are displayed, display settings.
        """
        if project_id is None:
            await self.bot.say(
                'Keen.IO settings:\n'
                'Project ID: {project_id}\n'
                'Read Key: {read_key}\n'
                'Write Key: {write_key}'.format(
                    project_id=self.settings["keen_project_id"],
                    read_key=self.settings["keen_read_key"],
                    write_key=self.settings["keen_write_key"]
                )
            )
            return
        self.settings["keen_project_id"] = project_id
        self.settings["keen_write_key"] = write_key
        self.settings["keen_read_key"] = read_key
        keen.project_id = self.settings["keen_project_id"]
        keen.write_key = self.settings["keen_write_key"]
        keen.read_key = self.settings["keen_read_key"]
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Keen.IO settings updated.")
        await self.bot.delete_message(ctx.message)

    @keenlogset.command(name="test", pass_context=True)
    async def keenlogset_test(self, ctx, a, b):
        """Test keen"""
        keen.add_event("test", {
            "a": a,
            "b": b
        })

    @keenlogset.command(name="logall", pass_context=True, no_pm=True)
    async def keenlogset_logall(self, ctx):
        """Log all gauges."""
        for server in self.bot.servers:
            ServerStatsModel(server).save()

        await self.bot.say("Logged all server stats")

    @checks.serverowner_or_permissions()
    @commands.group(pass_context=True, no_pm=True)
    async def ownerkeenlog(self, ctx):
        """Bot owner level data access.

        Mainly difference is that the bot owner is allowed to see data from another server
        since he/she admins those servers.
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @ownerkeenlog.command(name="users", pass_context=True, no_pm=True)
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
        """Keen.IO Log"""
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

        # mds = self.message_search

        time = p_args.time
        # rank = mds.author_rank(member, time)
        # channels = mds.author_channels(member, time)
        # active_members = mds.active_members(member.server, time)
        # message_count = mds.author_messages_count(member, time)
        # last_seen = mds.author_lastseen(member)

        resp = keen.count(
            "message",
            filters=[
                {
                    "property_name": "author.id",
                    "operator": "eq",
                    "property_value": member.id
                },
                {
                    "property_name": "server.id",
                    "operator": "eq",
                    "property_value": ctx.message.server.id
                }
            ],
            timeframe='this_7_days',
            group_by='channel.id'
        )
        resp = sorted(resp, key=lambda r: r["result"], reverse=True)

        # Embed
        em = discord.Embed(
            title="Member Activity: {}".format(member.display_name),
            description=KeenLogView.description(p_args, show_top=False),
            color=random_discord_color()
        )

        total_message_count = sum([r["result"] for r in resp])

        # em.add_field(
        #     name="Rank",
        #     value="{} / {} (active) / {} (all)".format(
        #         rank, active_members, len(member.server.members)
        #     )
        # )
        em.add_field(name="Messages", value=total_message_count)
        # last_seen_str = last_seen.strftime("%Y-%m-%d %H:%M:%S UTC")
        # em.add_field(name="Last seen", value=last_seen_str)

        max_count = None

        for r in resp[:p_args.count]:
            count = r["result"]
            if max_count is None:
                max_count = count
            print(r)
            channel = member.server.get_channel(r["channel.id"])
            chart = KeenLogView.inline_barchart(count, max_count)
            if channel is not None:
                channel_name = channel.name
            else:
                channel_name = 'None'
            em.add_field(
                name='{}: {} message'.format(channel_name, count),
                value=chart,
                inline=False)

        await self.bot.say(embed=em)

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

        # s = MessageEventModel.search()
        # s = s.filter('match', **{'server.id': server.id})
        #
        # if p_args.time is not None:
        #     s = s.filter('range', timestamp={'gte': 'now-{}/m'.format(p_args.time), 'lte': 'now/m'})
        # if p_args.includechannels is not None:
        #     for channel in p_args.includechannels:
        #         s = s.filter('match', **{'channel.name.keyword': channel})
        # if p_args.excludechannels is not None:
        #     for channel in p_args.excludechannels:
        #         s = s.query('bool', must_not=[Q('match', **{'channel.name.keyword': channel})])
        # if p_args.includeroles is not None:
        #     for role in p_args.includeroles:
        #         s = s.filter('match', **{'author.roles.name.keyword': role})
        # if p_args.excluderoles is not None:
        #     for role in p_args.excluderoles:
        #         s = s.query('bool', must_not=[Q('match', **{'author.roles.name.keyword': role})])
        # if p_args.excludebot:
        #     s = s.filter('match', **{'author.bot': False})

        # s = self.message_search.server_messages(server, p_args)



        resp = keen.count(
            "message",
            filters=[
                {
                    "property_name": "server.id",
                    "operator": "eq",
                    "property_value": server.id
                }
            ],
            timeframe='this_7_days',
            group_by=['author.id']
        )
        resp = sorted(resp, key=lambda r: r["result"], reverse=True)
        # Embed
        em = discord.Embed(
            title="{}: User activity by messages".format(server.name),
            description=KeenLogView.description(p_args),
            color=random_discord_color()
        )

        total_message_count = sum([r["result"] for r in resp])

        # em.add_field(
        #     name="Rank",
        #     value="{} / {} (active) / {} (all)".format(
        #         rank, active_members, len(member.server.members)
        #     )
        # )
        em.add_field(name="Messages", value=total_message_count)
        # last_seen_str = last_seen.strftime("%Y-%m-%d %H:%M:%S UTC")
        # em.add_field(name="Last seen", value=last_seen_str)

        max_count = None

        for r in resp[:p_args.count]:
            count = r["result"]
            if max_count is None:
                max_count = count
            print(r)
            member = server.get_member(r["author.id"])
            chart = KeenLogView.inline_barchart(count, max_count)
            if member is not None:
                member_name = member.display_name
            else:
                member_name = 'User {}'.format(r["author.id"])
            em.add_field(
                name='{}: {} message'.format(member_name, count),
                value=chart,
                inline=False)

        await self.bot.say(embed=em)

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
        MessageEventModel(message).save()

    async def on_message_delete(self, message: Message):
        """Track message deletion."""
        MessageDeleteEventModel(message).save()

    async def on_message_edit(self, before: Message, after: Message):
        """Track message editing."""
        MessageEditEventModel(before, after).save()

    async def on_member_join(self, member: Member):
        """Track members joining server."""
        MemberJoinEventModel(member).save()

    async def on_member_update(self, before: Member, after: Member):
        """Called when a Member updates their profile."""
        MemberUpdateEventModel(before, after).save()

    async def on_member_remove(self, member: Member):
        """Track members leaving server."""
        MemberRemoveEventModel(member).save()



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
