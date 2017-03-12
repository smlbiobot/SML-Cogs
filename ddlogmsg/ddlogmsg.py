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
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks

try:
    import datadog
    from datadog import statsd
except ImportError:
    raise ImportError("Please install the datadog package from pip") from None

PATH_LIST = ['data', 'ddlogmsg']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
HOST = '127.0.0.1'
INTERVAL = 5

class DataDogLogMessage:
    """DataDog Message Logger.

    Uses National Language Toolkit to monitor messages.
    Companion module for DataDogLog
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
        if author is server.me:
            return
        self.dd_log_messages(message)


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
            'bot.msglog',
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
    bot.add_cog(DataDogLogMessage(bot))



