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
from .utils import checks
from random import choice
import itertools


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
        # return itertools.zip_longest(*args, fillvalue=fillvalue)
        return ([e for e in t if e != None] for t in itertools.zip_longest(*args))

    @commands.command(pass_context=True)
    async def mm(self, ctx, *args):
        """
        Member management command.

        Get a list of users that satisfy a list of roles supplied.

        e.g.
        !mm S M -L
        !mm +S +M -L
        fetches a list of users who has the roles S, M but not the role L.
        S is the same as +S. + is an optional prefix for includes.

        """

        server = ctx.message.server
        server_roles_names = [r.name for r in server.roles]

        # get list of arguments which are valid server role names
        # as dictionary {flag, name}

        out=["**Member Management**"]

        role_args = []
        flags = ['+','-']
        for arg in args:
            has_flag = arg[0] in flags
            flag = arg[0] if has_flag else '+'
            name = arg[1:] if has_flag else arg

            if name in server_roles_names:
                role_args.append({'flag': flag, 'name': name})

        plus  = set([r['name'] for r in role_args if r['flag'] == '+'])
        minus = set([r['name'] for r in role_args if r['flag'] == '-'])

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
                    'e.g. ```!mm +A +B -C -D``` is equivalent to ```!mm A B -C -D```']

        if len(plus) < 1:
            out.append('\n'.join(help_str))
        else:
            out.append(f"Listing members who have these roles: {', '.join(plus)}")
        if len(minus):
            out.append(f"but not these roles: {', '.join(minus)}")

        await self.bot.say('\n'.join(out))

        # only output if argument is supplied
        if len(plus):
            # include roles with '+' flag
            # exclude roles with '-' flag
            out_members = set()
            for m in server.members:
                roles = set([r.name for r in m.roles])
                exclude = len(roles & minus)
                if not exclude and roles >= plus:
                    out_members.add(m)

            suffix = 's' if len(out_members) > 1 else ''
            await self.bot.say(f"**Found {len(out_members)} member{suffix}.**")
            await self.bot.say("Member name format: Username [Nickname]")


            # embed output
            color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
            color = int(color, 16)

            # split embed output to multiples of 25 
            # because embed only supports 25 max fields

            out_members_group = self.grouper(25, out_members)

            for out_members_list in out_members_group:

                data = discord.Embed(
                    color=discord.Colour(value=color))
                
                for m in out_members_list:
                    value = []
                    roles = [r.name for r in m.roles if r.name != "@everyone"]
                    value.append(f"{', '.join(roles)}")

                    name = m.name
                    if m.nick is not None:
                        name += f" [{m.nick}]"

                    data.add_field(name=str(name), value=str(''.join(value)))
                
                try:
                    await self.bot.say(embed=data)
                except discord.HTTPException:
                    await self.bot.say("I need the `Embed links` permission "
                                       "to send this")


def setup(bot):
    bot.add_cog(MemberManagement(bot))
