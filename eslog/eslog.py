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
import os
import re
import json
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
from elasticsearch_dsl import Q

from elasticsearch_dsl.query import QueryString, Range

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
connections.create_connection(hosts=['localhost'], timeout=20)


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


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
        --time TIME    
          Time in ES notation. 7d for 7 days, 1h for 1 hour
        --count COUNT   
          Number of results to show
        --excludechannels EXCLUDECHANNEL [EXCLUDECHANNEL ...]
          List of channels to exclude
        --includechannels INCLUDECHANNEL [INCLUDECHANNEL ...]
          List of channels to include
        --excludebot
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
            '--count',
            type=int,
            default="10",
            help='Number of results')
        parser.add_argument(
            '--excludechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '--includechannels',
            nargs='+',
            help='List of channels to exclude'
        )
        parser.add_argument(
            '--excludebot',
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

        hit_counts = []

        await self.bot.say("Note: This operation may take a few minutes if you are running on a server with many users.")
        status = await self.bot.say("Processed: 0/{} users.".format(len(server.members)))

        # use a copy because if member joins when iterations is going, it will break
        server_members = server.members.copy()

        for i, member in enumerate(server_members, 1):
            query_str = (
                "discord_event:message"
                " AND server.name:\"{server_name}\""
                " AND author.id:{author_id}"
            ).format(server_name=server.name, author_id=member.id)

            if p_args.excludebot:
                query_str += " AND author.bot:false"
            if p_args.excludechannels is not None:
                for channel_name in p_args.excludechannels:
                    query_str += " AND !channel.name:\"{}\"".format(channel_name)
            if p_args.includechannels is not None:
                qs = ""
                add_or = False
                for channel_name in p_args.includechannels:
                    if add_or:
                        qs += " OR"
                    qs += " channel.name:\"{}\"".format(channel_name)
                    add_or = True
                query_str += " AND ({})".format(qs)

            # print(query_str)

            qs = QueryString(query=query_str)
            r = Range(**{'@timestamp': {'gte': time_gte, 'lt': 'now'}})

            s = self.search.query(qs).query(r)

            count = s.count()

            hit_count = {
                "author_id": member.id,
                "count": count
            }

            hit_counts.append(hit_count)

            await self.bot.edit_message(status, new_content="Processed: {}/{} users.".format(i, len(server.members)))

        hit_counts = sorted(hit_counts, key=lambda m: m["count"], reverse=True)

        max_results = p_args.count

        hit_counts = hit_counts[:max_results]

        out = []
        for i, hit_count in enumerate(hit_counts, 1):
            member = server.get_member(hit_count["author_id"])
            out.append('{rank}. {author}: {count}'.format(
                rank=i, author=member.display_name, count=hit_count["count"]))

        await self.bot.say('\n'.join(out))


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