# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2019 SML

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
import itertools
from collections import defaultdict

import argparse
import discord
import os
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context
from random import choice
import datetime as dt

PATH = os.path.join("data", "message_quote")
JSON = os.path.join(PATH, "settings.json")

class MessageQuote:
    """Member Management plugin for Red Discord bot."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot

    @commands.command(name="mq", pass_context=True)
    async def message_quote(self, ctx, channel:discord.Channel, message_id):
        try:
            msg = await self.bot.get_message(channel, message_id)
        except discord.NotFound:
            await self.bot.say("Message not found.")
            return
        except discord.Forbidden:
            await self.bot.say("I do not have permissions to fetch the message")
            return
        except discord.HTTPException:
            await self.bot.say("Retrieving message faild")
            return

        if not msg:
            return

        ts = msg.timestamp

        out = [
            msg.content or '',
            "— {}, {}".format(
                msg.author.mention,
                ts.isoformat(sep=" ")
            )
        ]

        em = discord.Embed(
            description="\n".join(out)
        )

        await self.bot.say(embed=em)




def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = MessageQuote(bot)
    bot.add_cog(n)
