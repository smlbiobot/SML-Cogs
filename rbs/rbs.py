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

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
import discord

LOOP_INTERVAL = 5

SERVER_DEFAULTS = {
    'autorole': {
        "role_name": "Guest",
        "role_id": None,
        "timer": 86400
    }
}

PATH = os.path.join('data', 'rbs')
JSON = os.path.join(PATH, 'settings.json')

class RBS:
    """Reddit Band System (RBS) general utility cog.

    Functionality:

    # Autorole
    Automatically convert users with no role-assignements to Guest
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.task = bot.loop.create_task(self.loop_task())

    async def loop_task(self):
        """Loop tasks.

        - auto-role guests.
        """
        await self.bot.wait_until_ready()
        if self is self.bot.get_cog('RBS'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @checks.mod_or_permissions()
    @commands.group(pass_context=True, no_pm=True)
    async def setrbs(self, ctx):
        """Set RBS settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.serverowner_or_permissions(manage_server=True)
    @setrbs.command(name="initserver", pass_context=True, no_pm=True)
    async def setrbs_initserver(self, ctx):
        """Initialize server settings to default values.

        Requires confirmation as this is a destructive process.
        """
        await self.bot.say(
            'This is a destructive operation. '
            'Are you sure that you want to continue? '
            'Type **I agree** to execute.')
        answer = await self.bot.wait_for_message(
            timeout=30,
            author=ctx.message.author)
        if answer == 'I agree':
            self.settings = SERVER_DEFAULTS
            dataIO.save_json(JSON, self.settings)
            await self.bot.say(
                'Settings set to server defaults.')
        else:
            await self.bot.say(
                'Operation aborted.')

    @setrbs.command(name="autorolename", pass_context=True, no_pm=True)
    async def setrbs_autorolename(self, ctx, role_name):
        """Set auto-role’s role name.

        This is the role name automatically assigned to
        users when they have been on the server for x amount of time.
        The exact amount of time to use is also settable.
        """
        if 'autorole' not in self.settings:
            self.settings = SERVER_DEFAULTS
            dataIO.save_json(JSON, self.settings)

        server = ctx.message.server
        role = discord.utils.get(server.roles, name=role_name)

        if role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(
                    role_name))
            return

        self.settings['autorole']['role_name'] = role.name
        self.settings['autorole']['role_id'] = role.id
        await self.bot.say(
            'Auto-role’s role set to {}'.format(
                role.name))
        dataIO.save_json(JSON, self.settings)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, SERVER_DEFAULTS)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = RBS(bot)
    bot.add_cog(n)






