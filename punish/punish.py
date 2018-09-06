"""
The MIT License (MIT)

Copyright (c) 2018 SML

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

from collections import defaultdict

import asyncio
import discord
import os
import random
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "punish")
JSON = os.path.join(PATH, "settings.json")

TASK_SLEEP = 10
RANDOM_INTERVAL = TASK_SLEEP / 4


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def random_text():
    return random.choice([
        'Stop tagging people for stupid shit.',
        'This is what you get for randomly tagging people.',
        'Don’t do this ever again.',
        'Repeat offenders will be kicked / banned from this server.',
        'I hope that you have learned your lesson.',
        'Plea to a mod to stop this.'
    ])


class Punish:
    """Punish"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def check_settings(self, server):
        if server.id not in self.settings:
            self.settings[server.id] = dict(
                mention={},
                dm={}
            )
        self.save_settings()

    def save_settings(self):
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    async def punish(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @punish.command(name="mention", pass_context=True)
    async def punish_mention(self, ctx, member: discord.Member):
        """Punish users by having the bot randomly mention them."""
        server = ctx.message.server
        channel = ctx.message.channel
        self.check_settings(server)

        if member.id in self.settings[server.id]['mention']:
            self.settings[server.id]['mention'].pop(member.id, None)
            self.save_settings()
            await self.bot.say("Disable mentioning of user.")
        else:
            self.settings[server.id]['mention'][member.id] = channel.id
            self.save_settings()
            await self.bot.say("Added user to random mentions.")

    @checks.mod_or_permissions()
    @punish.command(name="settings", pass_context=True)
    async def punish_settings(self, ctx):
        """Show active punishments."""
        server = ctx.message.server
        s = self.settings.get(server.id)
        if s is not None:
            m = s.get('mention')
            o = []
            o_str = ''
            for member_id, channel_id in m.items():
                member = server.get_member(member_id)
                channel = server.get_channel(channel_id)

                if member is not None and channel is not None:
                    o.append('{channel.mention} {member.mention}'.format(member=member, channel=channel))
            o_str = ' | '.join(o)
            await self.bot.say(o_str)

    async def _loop_tasks(self):
        while self == self.bot.get_cog("Punish"):
            try:
                await self._mention_member_task()
            except Exception as e:
                print(e)
            finally:
                await asyncio.sleep(TASK_SLEEP)

    async def _mention_member_task(self):
        for server_id, s in self.settings.items():
            server = self.bot.get_server(server_id)

            for member_id, channel_id in s.get('mention').items():
                member = server.get_member(member_id)
                content = "{0.mention} {1}".format(member, random_text())
                channel = server.get_channel(channel_id)
                await asyncio.sleep(TASK_SLEEP * 0.5 * random.random())
                await self.bot.send_message(channel, content)


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = Punish(bot)
    bot.add_cog(n)
    bot.loop.create_task(n._loop_tasks())
