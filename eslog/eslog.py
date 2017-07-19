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

import asyncio
import logging
import itertools
import os
import re
import json
import copy
from collections import defaultdict
from datetime import timedelta

import logstash
from __main__ import send_cmd_help
import discord
import argparse
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
from cogs.utils.chat_formatting import box

import elasticsearch
import elasticsearch_dsl

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from elasticsearch_dsl.query import QueryString
from elasticsearch_dsl.query import Range


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


class BarChart:
    """Plotting bar charts as ASCII.

    Based on https://github.com/mkaz/termgraph
    """

    def __init__(self, labels, data, width):
        """Init."""
        self.tick = '▇'
        self.sm_tick = '░'
        self.labels = labels
        self.data = data
        self.width = width

    def chart(self):
        """Plot chart."""
        # verify data
        m = len(self.labels)
        if m != len(self.data):
            print(">> Error: Label and data array sizes don't match")
            return None

        # massage data
        # normalize for graph
        max_ = 0
        for i in range(m):
            if self.data[i] > max_:
                max_ = self.data[i]

        step = max_ / self.width
        label_width = max([len(label) for label in self.labels])

        out = []
        # display graph
        for i in range(m):
            out.append(
                self.chart_blocks(
                    self.labels[i], self.data[i], step,
                    label_width))

        return '\n'.join(out)

    def chart_blocks(
            self, label, count, step,
            label_width):
        """Plot each block."""
        blocks = int(count / step)
        out = "{0:>16}: ".format(label)
        if count < step:
            out += self.sm_tick
        else:
            for i in range(blocks):
                out += self.tick
        out += '  {}'.format(count)
        return out


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
    def embed_user_rank(hit):
        """User rank display."""


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
        self.search = Search(using=self.es, index="logstash-*")


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

    @eslog.command(name="messagecount", pass_context=True, no_pm=True)
    async def eslog_messagecount(self, ctx, *args):
        """Message count by params.
        
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
          List of channels to include
        --excludebot, -eb
          Exclude bot accounts
        
        Example:
        [p]eslog messagecount --time 2d --count 20 --include general some-channel
        Counts number of messages sent by authors within last 2 days in channels #general and #some-channel
        """
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]eslog messagecount')
        # parser.add_argument('key')
        parser.add_argument(
            '--time',
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

        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            # await self.bot.send_message(ctx.message.channel, box(parser.format_help()))
            await send_cmd_help(ctx)
            return

        time_gte = 'now-{}'.format(p_args.time)

        server = ctx.message.server

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

        # print(query_str)

        qs = QueryString(query=query_str)
        r = Range(**{'@timestamp': {'gte': time_gte, 'lt': 'now'}})

        s = self.search.query(qs).query(r).source(['author.id', 'author.roles'])

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

        # ESLogView.embed_user_rank(hit_counts)

        # group by 25 for embeds
        hit_counts_group = grouper(25, hit_counts)

        title = 'Message count by author'
        descriptions = []
        descriptions.append('Time: {}'.format(p_args.time))
        if p_args.includechannels is not None:
            descriptions.append('Including channels: {}'.format(', '.join(p_args.includechannels)))
        if p_args.excludechannels is not None:
            descriptions.append('Excluding channels: {}'.format(', '.join(p_args.excludechannels)))
        if p_args.excludebot:
            descriptions.append('Excluding bot users')
        descriptions.append('Showing top {} results.'.format(p_args.count))
        description = ', '.join(descriptions)
        footer_text = server.name

        chart = BarChart([''] * len(hit_counts), [h["count"] for h in hit_counts], 30)
        lines = chart.chart().split('\n')

        rank = 1
        max_count = None
        for hit_counts in hit_counts_group:
            em = discord.Embed(title=title, description=description)
            for hit_count in hit_counts:
                if hit_count is not None:
                    count = hit_count["count"]
                    member = server.get_member(hit_count["author_id"])
                    if member is not None:
                        name = member.display_name
                        mention = member.mention
                    else:
                        name = "User ID: {}".format(hit_count["author_id"])
                        mention = ''
                    if max_count is None:
                        max_count = count
                    width = 30
                    chart = '▇' * int(width * (count / max_count))
                    em.add_field(name='{}. {}: {}'.format(rank, name, count), value=box(chart), inline=False)
                    rank += 1
            em.set_footer(text=footer_text)
            await self.bot.say(embed=em)


        # standard view
        # out = []
        # for i, hit_count in enumerate(hit_counts, 1):
        #     member = server.get_member(hit_count["author_id"])
        #     if member is not None:
        #         name = member.display_name
        #     else:
        #         name = "User ID: {}".format(hit_count["author_id"])
        #     out.append('{rank}. {author}: {count}'.format(
        #         rank=i, author=name, count=hit_count["count"]))
        #
        # await self.bot.say('\n'.join(out))


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