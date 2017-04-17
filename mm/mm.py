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

import discord
from discord.ext import commands
from discord.ext.commands import Context
from random import choice
import itertools
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify

BOTCOMMANDER_ROLE = ["Bot Commander"]

class MemberManagement:
    """
    Member Management plugin for Red Discord bot
    """

    def __init__(self, bot):
        self.bot = bot

    def grouper(self, n, iterable, fillvalue=None):
        """
        Helper function to split lists

        Example:
        grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx
        """
        args = [iter(iterable)] * n
        return ([e for e in t if e != None] for t in itertools.zip_longest(*args))

    @commands.command(pass_context=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def mm(self, ctx, *args):
        """
        Member management command.

        Get a list of users that satisfy a list of roles supplied.

        e.g.
        !mm S M -L
        !mm +S +M -L
        fetches a list of users who has the roles S, M but not the role L.
        S is the same as +S. + is an optional prefix for includes.

        Optional arguments
        --output-mentions
            Append a string of user mentions for users displayed.
        --output-mentions-only
            Don’t display the long list and only display the list of member mentions
        --members-without-clan-tag
            RACF specific option. Equivalent to typing Member -Alpha -Bravo -Charlie -Delta -Echo -Foxtrot -Golf -Hotel
        --sort-join
            Sort list by join date on server
        --everyone
            Include everyone
        """

        # Extract optional arguments if exist
        option_output_mentions = "--output-mentions" in args
        option_output_mentions_only = "--output-mentions-only" in args
        option_members_without_clan_tag = "--members-without-clan-tag" in args
        option_sort_join = "--sort-join" in args
        option_everyone = "--everyone" in args

        server = ctx.message.server
        server_roles_names = [r.name for r in server.roles]

        # get list of arguments which are valid server role names
        # as dictionary {flag, name}
        out=["**Member Management**"]

        if option_members_without_clan_tag:
            args = ['Member', '-Alpha', '-Bravo', '-Charlie', '-Delta', '-Echo',
                    '-Foxtrot', '-Golf', '-Hotel', '-Special']

        role_args = []
        flags = ['+','-']
        if args is not None:
            for arg in args:
                has_flag = arg[0] in flags
                flag = arg[0] if has_flag else '+'
                name = arg[1:] if has_flag else arg

                if name in server_roles_names:
                    role_args.append({'flag': flag, 'name': name})

        plus  = set([r['name'] for r in role_args if r['flag'] == '+'])
        minus = set([r['name'] for r in role_args if r['flag'] == '-'])

        # Used for output only, so it won’t mention everyone in chat
        plus_out = plus.copy()

        if option_everyone:
            plus.add('@everyone')
            plus_out.add('everyone')

        help_str = ['Syntax Error: You must include at least one role to display results.',
                    '',
                    '**Usage** ',
                    '```!mm [+include_roles] [-exclude_roles]```',
                    '**Example**',
                    '```!mm +A +B -C```',
                    'will output members who have both role A and B but not C.',
                    '',
                    '**Roles with space**',
                    'For roles with space, surround text with quotes.',
                    'e.g. ```!mm "Role with space"```',
                    '**Flags**',
                    'You may omit the + sign for roles to include.',
                    'e.g. `!mm +A +B -C -D` is equivalent to `!mm A B -C -D`']

        if len(plus) < 1:
            out.append('\n'.join(help_str))
        else:
            out.append("Listing members who have these roles: {}".format(
                ', '.join(plus_out)))
        if len(minus):
            out.append("but not these roles: {}".format(
                ', '.join(minus)))

        await self.bot.say('\n'.join(out))

        # only output if argument is supplied
        if len(plus):
            # include roles with '+' flag
            # exclude roles with '-' flag
            out_members = set()
            for m in server.members:
                roles = set([r.name for r in m.roles])
                if option_everyone:
                    roles.add('@everyone')
                exclude = len(roles & minus)
                if not exclude and roles >= plus:
                    out_members.add(m)

            suffix = 's' if len(out_members) > 1 else ''
            await self.bot.say("**Found {} member{}.**".format(
                len(out_members), suffix))

            # sort join
            out_members = list(out_members)
            out_members.sort(key=lambda x: x.joined_at)

            # embed output
            if not option_output_mentions_only:
                for data in self.get_member_embeds(ctx, out_members):
                    try:
                        await self.bot.say(embed=data)
                    except discord.HTTPException:
                        await self.bot.say(
                            "I need the `Embed links` permission "
                            "to send this")

            # Display a copy-and-pastable list
            if option_output_mentions | option_output_mentions_only:
                mention_list = [m.mention for m in out_members]
                await self.bot.say(
                    "Copy and paste these in message to mention users listed:")

                out = ' '.join(mention_list)
                for page in pagify(out, shorten_by=24):
                    await self.bot.say(box(page))

    def get_member_embeds(self, ctx, members):
        """Discord embed of data display."""
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        embeds = []

        # split embed output to multiples of 25
        # because embed only supports 25 max fields
        out_members_group = self.grouper(25, members)

        for out_members_list in out_members_group:
            data = discord.Embed(
                color=discord.Colour(value=color))
            for m in out_members_list:
                value = []
                roles = [r.name for r in m.roles if r.name != "@everyone"]
                value.append(f"{', '.join(roles)}")

                name = m.display_name
                since_joined = (ctx.message.timestamp - m.joined_at).days

                data.add_field(
                    name=str(name),
                    value=str(
                        ''.join(value) +
                        '\n{} days ago'.format(
                            since_joined)))
            embeds.append(data)
        return embeds


    @commands.command(pass_context=True, no_pm=True)
    async def listroles(self, ctx: Context):
        """List all the roles on the server."""
        server = ctx.message.server
        if server is None:
            return
        out = []
        out.append("__List of roles on {}__".format(server.name))
        roles = {}
        for role in server.roles:
            roles[role.id] = {'role': role, 'count': 0}
        for member in server.members:
            for role in member.roles:
                roles[role.id]['count'] += 1
        for role in server.role_hierarchy:
            out.append("**{}** ({} members)".format(role.name,
                                                    roles[role.id]['count']))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)


def setup(bot):
    bot.add_cog(MemberManagement(bot))
