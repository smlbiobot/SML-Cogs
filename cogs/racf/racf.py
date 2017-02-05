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
from __main__ import send_cmd_help
import os
import datetime


rules_url = "https://www.reddit.com/r/CRRedditAlpha/comments/584ba2/reddit_alpha_clan_family_rules/"
roles_url = "https://www.reddit.com/r/CRRedditAlpha/wiki/roles"



class RACF:
    """
    Display RACF specifc info

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def racf(self, ctx):
        """RACF Rules + Roles"""

        server = ctx.message.server

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        data = discord.Embed(
            color=discord.Color(value=color),
            title="Rules + Roles",
            description="Important information for all members. Please read."
            )

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(name=server.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission to send this.")

        out = []
        out.append("**Rules**")
        out.append("<{}>".format(rules_url))
        out.append('')
        out.append("**Roles**")
        out.append("<{}>".format(roles_url))
        await self.bot.say('\n'.join(out))

    @commands.command(pass_context=True)
    async def racfwelcome(self, ctx, member:discord.Member):
        """Welcome people manually via command"""
        # server = ctx.message.server
        # self.member_join(member)
        await self.bot.say("Hi {0.mention}! Are you in the Reddit Alpha Clan Family (RACF) / " \
            "interested in joining our clans / just visiting?".format(member))

    async def member_join(self, member:discord.Member):
        """Greet users when they join the server"""
        server = member.server
        channel = server.default_channel.id

        if (server.name == "Reddit Alpha Clan Family"):
            await self.bot.send_message(channel,
                "Hi {0.mention}! Are you in the Reddit Alpha Clan Family (RACF) / " \
                "interested in joining our clans / just visiting?".format(member))





def setup(bot):
    r = RACF(bot)
    # bot.add_listener(r.member_join, "on_member_join")
    bot.add_cog(r)


