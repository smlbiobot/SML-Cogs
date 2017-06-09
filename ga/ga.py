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
import re
import uuid

from discord import Message
from discord import Server
from discord import ChannelType
from discord.ext import commands

from cogs.utils import checks

from __main__ import send_cmd_help

import google_measurement_protocol as gmp

from cogs.utils.dataIO import dataIO

PATH = os.path.join('data', 'ga')
JSON = os.path.join(PATH, 'settings.json')


class GA:
    """Send activity of Discord using Google Analytics."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.serverowner_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def setga(self, ctx):
        """Set Firebase settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setga.command(name="tid", pass_context=True)
    async def setga_tid(self, ctx, tid):
        """Set Google Analaytics TID."""
        self.settings["TID"] = tid
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Google Analaytics TID saved.")
        await self.bot.delete_message(ctx.message)

    async def on_message(self, msg: Message):
        """Track on message."""
        author = msg.author
        server = msg.server
        channel = msg.channel

        # if "USERS" not in self.settings:
        #     self.settings["USERS"] = {}
        # if author.id not in self.settings["USERS"]:
        #     client_id = uuid.uuid4()
        #     self.settings["USERS"][author.id] = str(client_id)
        #     dataIO.save_json(JSON, self.settings)

        if author is None:
            return
        if server is None:
            return
        if not author.id:
            return
        if not server.id:
            return
        if msg.channel is None:
            return
        if "TID" not in self.settings:
            await self.bot.send_message(
                msg.channel,
                "Google Analytics TID must be set.")
            return

        # client_id = uuid.UUID(self.settings["USERS"][author.id])
        client_id = uuid.uuid4()
        tid = self.settings["TID"]

        path = '/server/{}/message/{}'.format(server.id, author.id)
        title = author.display_name
        view = gmp.PageView(path=path, title=title)
        gmp.report(tid, client_id, view)

        path = '/server/{}/channel/{}'.format(server.id, channel.id)
        title = channel.name
        view = gmp.PageView(path=path, title=title)
        gmp.report(tid, client_id, view)

        event = gmp.Event(
            'message', 'send_message', label='author', value=author.id)
        gmp.report(tid, client_id, event)

        pattern = re.compile('\W')
        name = re.sub(pattern, '', author.display_name)
        event = gmp.Event('author', name)
        gmp.report(tid, client_id, event)


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
    n = GA(bot)
    bot.add_cog(n)

