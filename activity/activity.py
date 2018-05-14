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

import datetime as dt
import os

import aiohttp
import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context
from tinydb import Query
from tinydb import TinyDB
from tinydb.storages import JSONStorage
from tinydb_serialization import SerializationMiddleware
from tinydb_serialization import Serializer

PATH_LIST = ['data', 'activity']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
DB = os.path.join(*PATH_LIST, "db.json")
HOST = '127.0.0.1'
INTERVAL = 5


class DateTimeSerializer(Serializer):
    OBJ_CLASS = dt.datetime  # The class this serializer handles

    def encode(self, obj):
        return obj.strftime('%Y-%m-%dT%H:%M:%S')

    def decode(self, s):
        return dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')


serialization = SerializationMiddleware(JSONStorage)
serialization.register_serializer(DateTimeSerializer(), 'TinyDate')


class Activity:
    """Activity Logger.

    Logs activity of a Discord server.
    Displays:
    - Most active user by message sent
    - Richest user via bank economy module
    - Server Stats

    Settings
    - server_id
      - year, week number
        - messages
        - commands
        - mentions
        - message_time
      - on_off
      - server_id
      - server_name
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.rank_max = 5
        self.db = TinyDB(
            DB, storage=serialization, default_table='messages',
            sort_keys=True, indent=4, separators=(',', ': ')
        )
        self.table_settings = self.db.table('settings')
        self.table_messages = self.db.table('messages')

    def __unload(self):
        self.lock = True
        self.session.close()

    def save_json(self):
        """Save settings."""
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    @checks.mod_or_permissions()
    async def activityset(self, ctx: Context):
        """Change activity logging settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @activityset.command(name="toggle", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def as_toggle(self, ctx):
        """Toggle server monitoring."""
        server_id = ctx.message.server.id

        Settings = Query()
        db = self.db.table('settings')
        results = db.search(Settings.server_id == server_id)

        if len(results) == 0:
            on_off = True
        else:
            r = results[0]
            on_off = not r['on_off']

        db.upsert({'server_id': server_id, 'on_off': on_off}, Settings.server_id == server_id)

        await self.bot.say("Monitor server activity: {}".format(on_off))

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def activity(self, ctx: Context):
        """Activity."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    async def on_message(self, message: discord.Message):
        """Log number of messages."""
        server = message.server
        author = message.author
        channel = message.channel

        Settings = Query()
        db = self.table_settings
        r = db.get(Settings.server_id == server.id)

        if r is not None:
            if not r['on_off']:
                return

        self.table_messages.insert({
            'author_id': author.id,
            'server_id': server.id,
            'channel_id': channel.id,
            'message_content': message.content,
            'timestamp': dt.datetime.utcnow()
        })


def check_folders():
    if not os.path.exists(PATH):
        os.mkdir(PATH)


def check_files():
    if not dataIO.is_valid_json(JSON):
        defaults = {}
        dataIO.save_json(JSON, defaults)


def setup(bot):
    check_folders()
    check_files()
    n = Activity(bot)
    bot.add_cog(n)
