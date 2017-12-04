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

import discord
from __main__ import send_cmd_help
from box import Box, BoxList
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "votemanager")
JSON = os.path.join(PATH, "settings.json")

class Survey(Box):
    """A survey"""
    def __init__(self, title=None, description=None, role_ids=None, options=None, votes=None, timestamp=None):
        super().__init__()

        if role_ids is None:
            role_ids = BoxList()

        if options is None:
            options = BoxList()

        if votes is None:
            votes = Box()

        self.title = title
        self.description = description
        self.role_ids = role_ids
        self.options = options
        self.votes = votes
        self.timestamp = timestamp



class VoteManager:
    """Vote Manager. Voting module"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Box(dataIO.load_json(JSON), default_box=True)

    def save_settings(self):
        """Save settings."""
        dataIO.save_json(JSON, self.settings)

    def add_survey(self, server, title, description, roles, options):
        """Add a new survey.

        :returns: ID of survey
        """
        server_settings = self.settings[server.id]

        if server_settings.surveys == Box():
            server_settings.surveys = BoxList()

        survey = Survey(
            title=title,
            description=description,
            role_ids=[r.id for r in roles],
            options=options,
            timestamp=dt.datetime.utcnow().timestamp()
        )
        server_settings.surveys.append(survey)

        self.save_settings()

        return len(server_settings.surveys)

    def get_surveys(self, server):
        """Return list of surveys on the server."""
        server_settings = self.settings[server.id]
        if "surveys" not in server_settings:
            server_settings.surveys = BoxList()
        return server_settings.surveys

    def get_survey_by_id(self, server, id):
        """Return survey by ID, where ID is 0-based index of surveys."""
        surveys = self.get_surveys(server)
        if id >= len(surveys):
            return None
        return surveys[id]

    def reset_server(self, server):
        """Reset server settings."""
        self.settings[server.id] = Box()
        self.settings[server.id].surveys = BoxList()
        self.save_settings()

    @commands.group(pass_context=True, aliases=['vm'])
    async def votemanager(self, ctx):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.serverowner()
    @votemanager.command(name="reset", aliases=[], pass_context=True, no_pm=True)
    async def votemanager_reset(self, ctx):
        """Resret server settings"""
        server = ctx.message.server
        self.reset_server(server)
        await self.bot.say("Server settings reset.")

    @checks.mod_or_permissions()
    @votemanager.command(name="add", aliases=['a'], pass_context=True, no_pm=True)
    async def votemanager_add(self, ctx):
        """Add vote. Interactive."""
        author = ctx.message.author
        server = ctx.message.server

        await self.bot.say("Add a new survey. Continue? (y/n)")
        answer = await self.bot.wait_for_message(author=author)
        if answer.content.lower() != 'y':
            await self.bot.say("Aborted.")
            return

        #: Title
        await self.bot.say("Enter the title of the vote:")
        answer = await self.bot.wait_for_message(author=author)
        title = answer.content

        #: Description
        await self.bot.say("Enter the description of the vote:")
        answer = await self.bot.wait_for_message(author=author)
        description = answer.content

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

        survey_id = self.add_survey(server, title, description, roles, options)

        await ctx.invoke(self.votemanager_list, survey_id)

    @votemanager.command(name="list", aliases=['l'], pass_context=True, no_pm=True)
    async def votemanager_list(self, ctx, survey_number=None):
        """List votes."""
        server = ctx.message.server
        surveys = self.get_surveys(server)

        if len(surveys) == 0:
            await self.bot.say("No surveys found.")
            return

        if survey_number is None:
            em = discord.Embed(
                title="Vote Manager",
                description="List of surveys"
            )
            for i, s in enumerate(surveys, 1):
                em.add_field(
                    name=str(i),
                    value=s.title,
                    inline=False
                )
            em.set_footer(
                text='[p]vm list 1 to see details about survey 1'
            )
            await self.bot.say(embed=em)

        else:
            id = int(survey_number) - 1
            survey = self.get_survey_by_id(server, id)
            em = discord.Embed(
                title=survey.title,
                description=survey.description
            )
            em.add_field(
                name='Role(s)',
                value=', '.join([discord.utils.get(server.roles, id=rid).name for rid in survey.role_ids]),
            )
            em.add_field(
                name='Options',
                value='\n'.join(
                    ['`{}. ` {}'.format(number, option) for number, option in enumerate(survey.options, 1)]
                ),
                inline=False
            )
            em.set_footer(
                text='[p]vm vote {} [option_number] to cast your vote.'.format(survey_number)
            )
            await self.bot.say(embed=em)

    @votemanager.command(name="vote", pass_context=True, no_pm=True)
    async def votemanager_vote(self, ctx, survey_number, option_number=None):
        """Vote"""
        server = ctx.message.server
        author = ctx.message.author

        survey_id = int(survey_number) - 1

        survey = self.get_survey_by_id(server, survey_id)
        if survey is None:
            await self.bot.say("Invalid survey id.")
            return

        if option_number is None:
            await self.bot.say("You didn’t enter your option number. Here are the options:")
            await ctx.invoke(self.votemanager_list, survey_number)
            return

        if not option_number.isdigit():
            await self.bot.say("Option number must be a number.")
            return

        option_number = int(option_number)

        if option_number > len(survey.options) or option_number < 1:
            await self.bot.say("That is not a valid options.")
            await ctx.invoke(self.votemanager_list, survey_number)
            return

        roles = [discord.utils.get(server.roles, id=id) for id in survey.role_ids]
        valid_roles = [x for x in roles if x in author.roles]
        if len(valid_roles) == 0:
            await self.bot.say("You do not have the required roles to vote for this survey.")
            return

        if author.id in survey.votes.keys():
            voted_option_id = survey.votes[author.id]
            await self.bot.say(
                "You have previously voted for option {}. {}".format(
                    voted_option_id + 1, survey.options[voted_option_id]
                )
            )

        self.add_vote(server, author, survey_number, option_number)
        await self.bot.say(
            "You have cast a vote for option {}. {}".format(
                option_number, survey.options[int(option_number) - 1]
            )
        )

    def add_vote(self, server, author, survey_number, option_number):
        """Add a vote."""
        survey_id = int(survey_number) - 1
        option_id = int(option_number) - 1
        survey = self.get_survey_by_id(server, survey_id)
        survey.votes[author.id] = option_id
        self.save_settings()



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
