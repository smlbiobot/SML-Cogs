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
from __main__ import send_cmd_help

BOTCOMMANDER_ROLES = ['Bot Commander']


class RCS:
    """Reddit Clan System (RCS) utility."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot

    @commands.group(pass_context=True, no_pm=True)
    async def rcs(self, ctx):
        """Reddit Clan System (RCS)."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @commands.has_any_role(*BOTCOMMANDER_ROLES)
    @rcs.command(pass_context=True, no_pm=True)
    async def member(self, ctx, member: discord.Member, clan, *roles):
        """Convert user to member."""
        # add roles
        racf = self.bot.get_cog("RACF")
        if roles is None:
            roles = []
        else:
            roles = list(roles)
        roles.extend(['Trusted', clan, '-Visitor'])
        await ctx.invoke(racf.changerole, member, *roles)
        # change nick
        try:
            nick = "{} ({})".format(member.display_name, clan)
            await self.bot.change_nickname(member, nick)
        except discord.HTTPException:
            await self.bot.say(
                "I don’t have permission to change "
                "{}’s nickname.".format(member.display_name))
        else:
            await self.bot.say(
                "{} changed to {}.".format(
                    member.mention, nick))


def setup(bot):
    """Bot setup."""
    r = RCS(bot)
    bot.add_cog(r)


