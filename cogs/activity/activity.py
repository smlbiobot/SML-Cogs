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

from discord.ext import commands
from discord.ext.commands import Context
from discord.ext.commands import Command
from discord import Message
from discord import Server
from cogs.utils.chat_formatting import pagify
from cogs.utils.chat_formatting import box
from __main__ import send_cmd_help
from .utils.dataIO import dataIO
from .utils import checks
from random import choice
import datetime
import asyncio
import aiohttp
import discord
import os

try:
    import psutil
except:
    psutil = False

PATH_LIST = ['data', 'activity']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")

class Activity:
    """
    Activity Logger

    Logs activity of a Discord server.
    Displays:
    - Most active user by message sent
    - Richest user via bank economy module
    - Server Stats
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.handles = {}
        self.lock = False
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.lock = True
        self.session.close()
        for h in self.handles.values():
            h.close()

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def activityset(self, ctx:Context):
        """Change activity logging settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @activityset.command(name="server", pass_context=True, no_pm=True)
    async def activityset_server(self, ctx:Context, on_off:bool):
        """Sets loggig on or off for server events."""
        server = ctx.message.server

        self.check_server_settings(server)

        self.settings[server.id]['on_off'] = on_off

        if on_off:
            await self.bot.say(f"Logging enabled for {server}")
        else:
            await self.bot.say(f"Logging disabled for {server}")
        self.save_json()

    async def on_message(self, message:Message):
        """Logs number of messages sent by an."""
        author = message.author
        server = message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        if server.id in self.settings:
            if author.id not in self.settings[server.id]['messages']:
                self.settings[server.id]['messages'][author.id] = {
                    'name': author.display_name,
                    'id': author.id,
                    'messages': 0
                }
            author_settings = self.settings[server.id]['messages'][author.id]
            author_settings['messages'] += 1

        self.save_json()

    async def on_command(self, command:Command, ctx:Context):
        """Logs command used."""
        server = ctx.message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        if command.name not in self.settings[server.id]['commands']:
            self.settings[server.id]['commands'][command.name] = {
                'name': command.name,
                'cog_name': command.cog_name,
                'count': 0
            }
        self.settings[server.id]['commands'][command.name]['count'] += 1
        self.save_json()

    def check_server_settings(self, server:Server):
        """Verify server settings are available."""

        if server.id not in self.settings:
            self.settings[server.id] = {}

        server_settings = self.settings[server.id]

        if 'server_id' not in server_settings:
            server_settings['server_id'] = server.id
        if 'server_name' not in server_settings:
            server_settings['server_name'] = server.name
        if 'on_off' not in server_settings:
            server_settings['on_off'] = False
        if 'messages' not in server_settings:
            server_settings['messages'] = {}
        if 'commands' not in server_settings:
            server_settings['commands'] = {}

        self.save_json()




    def save_json(self):
        dataIO.save_json(JSON, self.settings)

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

