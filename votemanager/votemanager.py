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
from collections import defaultdict
import datetime as dt

import discord
from __main__ import send_cmd_help
from box import Box, BoxList
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from cogs.utils.chat_formatting import pagify

PATH = os.path.join("data", "votemanager")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class VoteManager:
    """Vote Manager. Voting module"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Box(dataIO.load_json(JSON), default_box=True)

    def save_settings(self):
        """Save settings."""
        dataIO.save_json(JSON, self.settings)

    def add_survey(self, server, title, roles, options):
        """Add a new survey."""
        server_settings = self.settings[server.id]

        if server_settings.surveys == Box():
            server_settings.surveys = BoxList()

        server_settings.surveys.append({
            'title': title,
            'role_ids': [r.id for r in roles],
            'options': options,
            'timestamp': dt.datetime.utcnow().timestamp()
        })

        self.save_settings()

    def get_surveys(self, server):
        """Return list of surveys on the server."""
        server_settings = self.settings[server.id]
        if server_settings.surveys == Box():
            server_settings.surveys = BoxList()
        return server_settings.surveys

    @commands.group(pass_context=True, aliases=['vms'])
    async def votemanagerset(self, ctx):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @votemanagerset.command(name="add", aliases=['a'], pass_context=True, no_pm=True)
    async def votemanagerset_vote(self, ctx):
        """Add vote. Interactive."""
        author = ctx.message.author
        server = ctx.message.server

        await self.bot.say("Add a vote. Continue? (y/n)")
        answer = await self.bot.wait_for_message(author=author)
        if answer.content.lower() != 'y':
            await self.bot.say("Aborted.")
            return

        #: Title
        await self.bot.say("Enter the title of the vote:")
        answer = await self.bot.wait_for_message(author=author)
        title = answer.content
        await self.bot.say("Title: {}".format(title))

        #: Roles
        await self.bot.say("Enter list of roles who can vote for this, separated by `|`:")
        answer = await self.bot.wait_for_message(author=author)
        role_names = [a.strip() for a in answer.content.split('|')]
        roles = [discord.utils.get(server.roles, name=role_name) for role_name in role_names]
        for role in roles:
            if role is None:
                await self.bot.say("Cannot find {} on server. Aborting…".format(role))
                return

        #: Options
        await self.bot.say("Enter a list of options, separated by `|`:")
        answer = await self.bot.wait_for_message(author=author)
        options = [a.strip() for a in answer.content.split('|')]

        self.add_survey(server, title, roles, options)

        await self.bot.say("Title: {}".format(title))
        await self.bot.say("Role(s): {}".format(', '.join(role_names)))
        await self.bot.say("Options: {}".format('\n '.join(options)))

    @votemanagerset.command(name="list", aliases=['l'], pass_context=True, no_pm=True)
    async def votemanagerset_list(self, ctx, number=None):
        """List votes."""
        server = ctx.message.server
        surveys = self.get_surveys(server)

        if number is None:
            out = ["List of surveys on this server:"]
            for i, s in enumerate(surveys, 1):
                out.append("{}. {}".format(i, s.title))

            for page in pagify('\n'.join(out)):
                await self.bot.say(page)

        else:
            s = surveys[int(number) - 1]
            out = ["Survey number " + number]
            out.append(
                "Title: {title}\n"
                "Roles: {roles}\n"
                "Options: \n"
                "{options}".format(
                    title=s.title,
                    roles=', '.join([discord.utils.get(server.roles, id=rid).name for rid in s.role_ids]),
                    options='\n'.join(s.options)
                )
            )
            for page in pagify('\n'.join(out)):
                await self.bot.say(page)


    @commands.group(pass_context=True, aliases=['vm'])
    async def votemanager(self, ctx):
        """Vote Manager."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @votemanager.command(name="vote", pass_context=True, no_pm=True)
    async def votemanager_vote(self, ctx):
        """Vote"""


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
    n = VoteManager(bot)
    bot.add_cog(n)
