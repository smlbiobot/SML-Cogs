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
from discord.ext.commands import Command
from discord.ext.commands import Context
from cogs.utils.chat_formatting import pagify
from __main__ import send_cmd_help
from .utils.dataIO import dataIO
from .utils import checks
import datetime
import aiohttp
import discord
import re
import os

try:
    import psutil
except:
    psutil = False

PATH_LIST = ['data', 'activity']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")


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
      - on_off
      - server_id
      - server_name
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.handles = {}
        self.lock = False
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.rank_max = 5

    def __unload(self):
        self.lock = True
        self.session.close()
        for h in self.handles.values():
            h.close()

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def activityset(self, ctx: Context):
        """Change activity logging settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @activityset.command(name="server", pass_context=True, no_pm=True)
    async def activityset_server(self, ctx: Context, on_off: bool):
        """Set loggig on or off for server events."""
        server = ctx.message.server

        self.check_server_settings(server)

        self.settings[server.id]['on_off'] = on_off

        if on_off:
            await self.bot.say(f"Logging enabled for {server}")
        else:
            await self.bot.say(f"Logging disabled for {server}")
        self.save_json()

    @commands.command(pass_context=True)
    async def ranks(self, ctx: Context, top_max: int=None):
        """Show the activity for this server."""
        server = ctx.message.server
        self.check_server_settings(server)
        time_id = self.get_time_id()

        out = []

        if top_max is None:
            top_max = self.rank_max
        else:
            top_max = int(top_max)

        out.append("**{}** (this week)".format(server.name))

        # messages
        msg = self.settings[server.id][time_id]["messages"]
        msg = dict(sorted(msg.items(), key=lambda x: -x[1]["messages"]))
        out.append("__Most active members__")
        for i, (k, v) in enumerate(msg.items()):
            if i < top_max:
                out.append("`{:4d}.` {} ({} messages)".format(
                    i + 1,
                    v["name"],
                    str(v["messages"])))
        # economy
        out.append("__Richest members__")
        economy = self.bot.get_cog("Economy")
        if economy is not None:
            bank = economy.bank
            if bank is not None:
                if server.id in bank.accounts:
                    accounts = bank.accounts[server.id]
                    accounts = dict(sorted(accounts.items(),
                                           key=lambda x: -x[1]["balance"]))
                    for i, (k, v) in enumerate(accounts.items()):
                        if i < top_max:
                            out.append("`{:>2}.` {} ({} credits)".format(
                                str(i + 1),
                                server.get_member(k).display_name,
                                str(v["balance"])))
        # commands
        cmd = self.settings[server.id][time_id]["commands"]
        cmd = dict(sorted(cmd.items(), key=lambda x: -x[1]["count"]))
        out.append("__Most used commands__")
        for i, (k, v) in enumerate(cmd.items()):
            if i < top_max:
                out.append("`{:>2}.` {} ({} times)".format(
                    str(i + 1),
                    v["name"],
                    str(v["count"])))
        # mentions
        mentions = self.settings[server.id][time_id]["mentions"]
        mentions = dict(sorted(mentions.items(),
                               key=lambda x: -x[1]["mentions"]))
        out.append("__Most mentioned members__")
        for i, (k, v) in enumerate(mentions.items()):
            if i < top_max:
                out.append("`{:>2}.` {} ({} times)".format(
                    str(i + 1),
                    v["name"],
                    str(v["mentions"])))

        # channels
        channels = self.settings[server.id][time_id]["channels"]
        channels = dict(sorted(channels.items(),
                               key=lambda x: -x[1]["messages"]))
        out.append("__Most active channels__")
        for i, (k, v) in enumerate(channels.items()):
            if i < top_max:
                out.append("`{}.` {} ({} messages)".format(
                    str(i + 1),
                    v["name"],
                    str(v["messages"])))

        # emojis
        emojis = self.settings[server.id][time_id]["emojis"]
        emojis = dict(sorted(emojis.items(), key=lambda x: -x[1]["count"]))
        out.append("__Most used emojis__")
        for i, (k, v) in enumerate(emojis.items()):
            if i < top_max:
                out.append("`{}.` {} ({} times)".format(
                    str(i + 1),
                    "{}".format(v["name"]),
                    str(v["count"])))

        # date on start of week
        dt = datetime.datetime.utcnow()
        start = dt - datetime.timedelta(days=dt.weekday())
        out.append("Data since: {} UTC".format(start.isoformat()))
        out.append("Stats data on {} UTC".format(dt.isoformat()))

        # pagify output
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    async def on_message(self, message: discord.Message):
        """Log number of messages sent by an."""
        author = message.author
        server = message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        # Don’t log bot messages
        if author is server.me:
            return

        time_id = self.get_time_id()

        if server.id in self.settings:
            server_settings = self.settings[server.id][time_id]

            # log message author
            if author.id not in server_settings['messages']:
                server_settings['messages'][author.id] = {
                    'name': author.display_name,
                    'id': author.id,
                    'messages': 0
                }
            author_settings = server_settings['messages'][author.id]
            author_settings['messages'] += 1

            # log message mentions
            for member in message.mentions:
                if member.id not in server_settings['mentions']:
                    server_settings['mentions'][member.id] = {
                        'name': member.display_name,
                        'id': member.id,
                        'mentions': 0
                    }
                server_settings['mentions'][member.id]['mentions'] += 1

            # log channel usage
            channel = message.channel
            if channel is not None:
                if not channel.is_private:
                    if channel.id not in server_settings['channels']:
                        server_settings['channels'][channel.id] = {
                            'name': channel.name,
                            'id': channel.id,
                            'messages': 0
                        }
                    server_settings['channels'][channel.id]['messages'] += 1

            # log emojis usage
            # Discord emojis: <:joyless:230104023305420801>
            emoji_p = re.compile('\<\:.+?\:\d+\>')
            emojis = emoji_p.findall(message.content)
            if len(emojis):
                for emoji in emojis:
                    if emoji not in server_settings['emojis']:
                        server_settings['emojis'][emoji] = {
                            'name': emoji,
                            'count': 0
                        }
                    server_settings['emojis'][emoji]['count'] += 1
            uemoji_p = re.compile(u'['
                                  u'\U0001F300-\U0001F64F'
                                  u'\U0001F680-\U0001F6FF'
                                  u'\uD83C-\uDBFF\uDC00-\uDFFF'
                                  u'\u2600-\u26FF\u2700-\u27BF]+',
                                  re.UNICODE)
            emojis = uemoji_p.findall(message.content)
            if len(emojis):
                for emoji in emojis:
                    if emoji not in server_settings['emojis']:
                        server_settings['emojis'][emoji] = {
                            'name': emoji,
                            'count': 0
                        }
                    server_settings['emojis'][emoji]['count'] += 1

        self.save_json()

    async def on_command(self, command: Command, ctx: Context):
        """Log command used."""
        server = ctx.message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        time_id = self.get_time_id()

        server_commands = self.settings[server.id][time_id]['commands']

        if command.name not in server_commands:
            server_commands[command.name] = {
                'name': command.name,
                'cog_name': command.cog_name,
                'count': 0
            }
        server_commands[command.name]['count'] += 1
        self.save_json()

    def check_server_settings(self, server: discord.Server):
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

        time_id = self.get_time_id()

        if time_id not in server_settings:
            server_settings[time_id] = {}

        if 'messages' not in server_settings[time_id]:
            server_settings[time_id]['messages'] = {}
        if 'commands' not in server_settings[time_id]:
            server_settings[time_id]['commands'] = {}
        if 'mentions' not in server_settings[time_id]:
            server_settings[time_id]['mentions'] = {}
        if 'channels' not in server_settings[time_id]:
            server_settings[time_id]['channels'] = {}
        if 'emojis' not in server_settings[time_id]:
            server_settings[time_id]['emojis'] = {}

        self.save_json()

    def get_time_id(self, date: datetime.date=None):
        """Return current year, week as a tuple."""
        if date is None:
            date = datetime.datetime.utcnow()
        (now_year, now_week, now_day) = date.isocalendar()
        return "{}, {}".format(now_year, now_week)

    def get_server_messages_settings(self, server: discord.Server,
                                     time_id: datetime.date=None):
        """Return the messages dict from settings."""
        if time_id is None:
            time_id = self.get_time_id()
        return self.settings[server.id][time_id]["messages"]

    def get_server_commands_settings(self, server: discord.Server,
                                     time_id: datetime.date=None):
        """Return the messages dict from settings."""
        if time_id is None:
            time_id = self.get_time_id()
        return self.settings[server.id][time_id]["commands"]

    def save_json(self):
        """Save settings."""
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
