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


TOGGLE_ROLES = ["Trusted", "Visitor"]

TOGGLE_PERM = {
    "Trusted": [
        "Tournaments"
    ],
    "Visitor": [
    ]
}


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
    async def verify(self, ctx, member: discord.Member, *roles):
        """Add trusted and any additional roles to user."""
        # add roles
        mm = self.bot.get_cog("MemberManagement")
        roles = list(roles)
        roles.append("Trusted")
        await ctx.invoke(mm.changerole, member, *roles)

    @commands.has_any_role(*TOGGLE_ROLES)
    @rcs.command(pass_context=True, no_pm=True)
    async def togglerole(self, ctx, role_name):
        """Self-toggle role assignments."""
        author = ctx.message.author
        server = ctx.message.server
        # toggleable_roles = [r.lower() for r in TOGGLEABLE_ROLES]

        member_role = discord.utils.get(server.roles, name="Trusted")
        is_member = member_role in author.roles

        if is_member:
            toggleable_roles = TOGGLE_PERM["Trusted"]
        else:
            toggleable_roles = TOGGLE_PERM["Visitor"]

        toggleable_roles = sorted(toggleable_roles)

        toggleable_roles_lower = [r.lower() for r in toggleable_roles]

        if role_name.lower() in toggleable_roles_lower:
            role = [
                r for r in server.roles
                if r.name.lower() == role_name.lower()]

            if len(role):
                role = role[0]
                if role in author.roles:
                    await self.bot.remove_roles(author, role)
                    await self.bot.say(
                        "Removed {} role from {}.".format(
                            role.name, author.display_name))
                else:
                    await self.bot.add_roles(author, role)
                    await self.bot.say(
                        "Added {} role for {}.".format(
                            role_name, author.display_name))
            else:
                await self.bot.say(
                    "{} is not a valid role on this server.".format(role_name))
        else:
            out = []
            out.append(
                "{} is not a toggleable role for you.".format(role_name))
            out.append(
                "Toggleable roles for you: {}.".format(
                    ", ".join(toggleable_roles)))
            await self.bot.say("\n".join(out))


def setup(bot):
    """Bot setup."""
    r = RCS(bot)
    bot.add_cog(r)


