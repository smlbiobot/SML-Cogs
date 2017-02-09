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
import aiohttp
# from .economy import Economy


rules_url = "https://www.reddit.com/r/CRRedditAlpha/comments/584ba2/reddit_alpha_clan_family_rules/"
roles_url = "https://www.reddit.com/r/CRRedditAlpha/wiki/roles"
discord_url = "http://tiny.cc/alphachat"

welcome_msg = "Hi {}! Are you in the Reddit Alpha Clan Family (RACF) / " \
              "interested in joining our clans / just visiting?"



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
        out.append('')
        out.append("**Discord invite**")
        out.append("<{}>".format(discord_url))
        await self.bot.say('\n'.join(out))

    @commands.command(pass_context=True)
    async def racfwelcome(self, ctx, member:discord.Member):
        """Welcome people manually via command"""
        # server = ctx.message.server
        # self.member_join(member)
        await self.bot.say(welcome_msg.format(member.mention))

    @commands.command(pass_context=True)
    async def racfwelcomeall(self, ctx):
        """Find all untagged users and send them the welcome message"""
        server = ctx.message.server
        members = server.members
        online_members = [m for m in members if m.status == discord.Status.online]
        online_untagged_members = [m for m in online_members if len(m.roles) == 1]
        online_untagged_members_names = [m.name for m in online_untagged_members]
        print(', '.join(online_untagged_members_names))

    @commands.command(pass_context=True)
    async def alluntaggedusers(self, ctx):
        """Find all untagged users and send them the welcome message"""
        server = ctx.message.server
        members = server.members
        untagged_members = [m for m in members if len(m.roles) == 1]
        untagged_members_names = [m.name for m in untagged_members]
        untagged_members_mention = [m.mention for m in untagged_members]

        await self.bot.say("All online but untagged users:")
        await self.bot.say(', '.join(untagged_members_names))
        await self.bot.say("Mentions:")
        await self.bot.say("'''{}'''".format(' '.join(untagged_members_mention)))

    @commands.command(pass_context=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def racf_bank_deposit(self, ctx):
        """Hacking the eco system to add points"""

        # bank = self.bot.get_cog("Economy").bank

        # author = ctx.message.author

        # bank.deposit_credits(author, 10)

        pass

    @commands.command(pass_context=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def mentionusers(self, ctx, role:str, *msg):
        """
        Mention users by role

        Example: !mentionusers Delta Anyone who is 4,300+ please move up to Charlie!

        Note: only usable by people with the permission to mention @everyone

        """
        server = ctx.message.server
        server_roles_names = [r.name for r in server.roles]

        if not role in server_roles_names:
            await self.bot.say("{} is not a valid role on this server.".format(role))
        elif not msg:
            await self.bot.say("You have not entered any messages.")
        else:
            out_mentions = []
            for m in server.members:
                if role in [r.name for r in m.roles]:
                    out_mentions.append(m.mention)
            await self.bot.say("{} {}".format(" ".join(out_mentions), " ".join(msg)))




    @commands.command(pass_context=True)
    async def avatar(self, ctx, member:discord.Member=None):
        """Display avatar of the user"""
        author = ctx.message.author

        if member is None:
            member = author
        avatar_url = member.avatar_url
        data = discord.Embed()
        data.set_image(url=avatar_url)
        await self.bot.say(embed=data)

        # image_loaded = False

        # if not simage_loaded:
        #     try:
        #         async with aiohttp.get(self.url) as r:
        #             image = await r.content.read()
        #         with open('data/sadface/sadface.png','wb') as f:
        #             f.write(image)
        #         image_loaded = os.path.exists('data/sadface/sadface.png')
        #         await self.bot.send_file(message.channel,self.image)
        #     except Exception as e:
        #         print(e)
        #         print("Sadface error D: I couldn't download the file, so we're gonna use the url instead")
        #         await self.bot.send_message(message.channel,self.url)
        # else:
        #     await self.bot.send_file(message.channel,self.image)

        








def setup(bot):
    r = RACF(bot)
    # bot.add_listener(r.member_join, "on_member_join")
    bot.add_cog(r)


