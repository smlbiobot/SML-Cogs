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
from random import choice
from .utils.dataIO import dataIO
from __main__ import send_cmd_help
import os

settings_path = "data/banned/settings.json"
admin_role = "Bot Commander"

class Banned:
    """
    Manage people who are banned from the RACF

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.banned_members = dataIO.load_json(self.file_path)
        # self.remove_old()

    @commands.group(pass_context=True, no_pm=True, invoke_without_command=False)
    async def banned(self, ctx):
        """Manage per-server banned list"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @banned.command(name="add", pass_context=True, no_pm=True)
    @commands.has_role(admin_role)
    async def _add_banned(self, ctx, member_name=None, member_tag="#", reason="---"):
        """Add a member to the ban list. 

           Example: !banned add PlayerA #098UGYE "Being Toxic"
           """
        server = ctx.message.server

        if server.id not in self.banned_members:
            self.banned_members[server.id] = {}

        if member_name is None:
            await self.bot.say("You must enter a member name.")
        else:
            member_data = {
                "Name"   : member_name,
                "Tag"    : member_tag,
                "Reason" : reason
            }

            self.banned_members[server.id][member_name] = member_data
            dataIO.save_json(self.file_path, self.banned_members)

            await self.bot.say("**{}** ({}) added to the list of banned members."
                               "\n**Reason:** {}".format(member_name, member_tag, reason))

    @banned.command(name="remove", pass_context=True, no_pm=True)
    @commands.has_role(admin_role)
    async def _remove_banned(self, ctx, member_name=None):
        """Remove a member from the ban list by name.
        Example: !banned remove PlayerA"""
        server = ctx.message.server

        if server.id in self.banned_members:
            if member_name in self.banned_members[server.id]:
                self.banned_members[server.id].pop(member_name)
                await self.bot.say("**{}** removed from the list of banned members.".format(member_name))
                dataIO.save_json(self.file_path, self.banned_members)


    @banned.command(name="show", pass_context=True, no_pm=True)
    async def _show_banned(self, ctx):
        """Display list of members who are banned from the RACF"""

        server = ctx.message.server
        if server.id in self.banned_members:
            members = self.banned_members[server.id]
            # embed output
            color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
            color = int(color, 16)

            title = "Banned Members"
            description = "List of players who have been banned from the RACF"

            data = discord.Embed(
                title=title,
                description=description,
                color=discord.Color(value=color))

            for member_key, member in members.items():
                name = "{} ({})".format(member["Name"], member["Tag"])
                value = member["Reason"]
                data.add_field(
                    name=str(name), 
                    value=str(value)
                    )

            try:
                await self.bot.type()
                await self.bot.say(embed=data)

            except discord.HTTPException:
                await self.bot.say("I need the `Embed links` permission "
                                   "to send this")

    @banned.command(name="debug", pass_context=True)
    async def _debug_banned(self, ctx):
        data = discord.Embed(
            title="DEBUG")

        await self.bot.say(embed=data)

def check_folder():
    if not os.path.exists("data/banned"):
        print("Creating data/banned folder...")
        os.makedirs("data/banned")


def check_file():
    banned = {}

    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default banned's banned.json...")
        dataIO.save_json(f, banned)


def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(Banned(bot))

