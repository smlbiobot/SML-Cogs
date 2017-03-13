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
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify

try:
    import nltk
except ImportError:
    raise ImportError("Please install the nltk package from pip") from None

PATH_LIST = ['data', 'tldr']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
HOST = '127.0.0.1'
INTERVAL = 5

class TLDR:
    """Too Lazy; Didn’t Read.

    Uses National Language Toolkit to process messages.
    """
    def __init__(self, bot):
        self.bot = bot
        self.tags = []
        self.settings = dataIO.load_json(JSON)

    def save(self):
        dataIO.save_json(JSON, self.settings)


    @commands.group(pass_context=True, no_pm=True)
    async def tldr(self, ctx: Context):
        """Too Lazy; Didn’t Read.

        Uses National Language Toolkit to process messages."""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @tldr.command(name="msg", pass_context=True, no_pm=True)
    async def tldr_message(self, ctx: Context, message_id: str):
        """Process messsage by message id."""
        channel = ctx.message.channel
        server = ctx.message.server
        message = await self.bot.get_message(channel, message_id)

        # stopwords = nltk.corpus.stopwords.words('english')
        # content = [w for w in message.content.split() if w.lower() not in stopwords]

        tknzr = nltk.tokenize.casual.TweetTokenizer()
        out = tknzr.tokenize(message.content)

        await self.bot.say("original")
        await self.bot.say(message.content)
        await self.bot.say("transformed")
        for page in pagify(str(out), shorten_by=12):
            await self.bot.say(page)










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
    bot.add_cog(TLDR(bot))



