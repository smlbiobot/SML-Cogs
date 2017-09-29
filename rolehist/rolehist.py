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
from .utils.dataIO import dataIO
from .general import General
from cogs.utils.chat_formatting import pagify
import os
import datetime

settings_path = "data/rolehist/settings.json"

class RoleHistory:
    """
    Edit and store history of user roles.

    """

    def __init__(self, bot):
        """init."""
        self.bot = bot
        self.file_path = settings_path
        self.settings = dataIO.load_json(self.file_path)

    def save_member_data(self, server=None, member=None):
        """Save member data to settings."""
        if server is None:
            return
        if member is None:
            return
        self.settings[server.id]["Members"][member.id] = {
            "MemberID": member.id,
            "History": {
                str(self.server_time()): self.get_member_data(member)
            }
        }
        dataIO.save_json(self.file_path, self.settings)

    @commands.command(pass_context=True, no_pm=True)
    async def rolehist(self, ctx, user: discord.Member=None):
        """Display the role history of a user.

        Examples:
        !rolehist
        !rolehist SML
        """
        author = ctx.message.author
        server = ctx.message.server

        if not user:
            user = author

        if server is None:
            return

        if server.id in self.settings:

            found_member = None

            server_settings = self.settings[server.id]
            for member_key, member_value in server_settings["Members"].items():

                member = server.get_member(member_key)

                if user == member:
                    await self.bot.say("Found Member.")
                    await ctx.invoke(General.userinfo, user=member)
                    out = []

                    hist = sorted(member_value["History"].items())

                    prev_roles = []

                    for time_key, time_value in hist:

                        line = "• {}: ".format(time_key)

                        curr_roles = time_value["Roles"]
                        # display role changes if not the first item
                        if len(prev_roles):
                            prev_roles_set = set(prev_roles)
                            curr_roles_set = set(curr_roles)
                            if prev_roles_set < curr_roles_set:
                                line += 'Added: {}'.format(
                                    list(curr_roles_set - prev_roles_set)[0])
                            elif prev_roles_set > curr_roles_set:
                                line += 'Removed: {}'.format(
                                    list(prev_roles_set - curr_roles_set)[0])

                        out.append(line)

                        prev_roles = curr_roles

                    for page in pagify("\n".join(out)):
                        await self.bot.say(page)

                    found_member = member

            # if no data found, add record
            if found_member is None:

                await self.bot.say("Member not found in database.")

                member = user

                if member is not None:
                    self.save_member_data(server, member)
                    await self.bot.say("Added member to database.")
                else:
                    await self.bot.say(
                        "{} is not a valid user on this server.".format(user))

    @commands.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def rolehistinit(self, ctx):
        """(MOD) Popularize database with current role data."""
        server = ctx.message.server
        members = server.members

        if server.id not in self.settings:
            self.settings[server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "Members": {}
            }

        for member in members:
            if member.id not in self.settings[server.id]["Members"]:
                # init member only if not found
                self.save_member_data(server, member)

        await self.bot.say("Added all member roles to database.")

    async def on_member_join(self, member):
        """Add member records when new user join."""
        server = member.server

        if server.id not in self.settings:
            self.settings[server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "Members": {}
            }

        if member.id not in self.settings[server.id]["Members"]:
            self.save_member_data(server, member)

        dataIO.save_json(self.file_path, self.settings)

    async def on_member_update(self, before, after):
        """Member update event."""
        server = before.server

        # process only on role changes
        if before.roles != after.roles:

            if server.id not in self.settings:
                self.settings[server.id] = {
                    "ServerName": str(server),
                    "ServerID": str(server.id),
                    "Members": {}
                }

            self.settings[server.id]["ServerName"] = str(server)

            # add member settings if it does not exist
            # initialize with before data
            # using server time as unique id for role changes
            if before.id not in self.settings[server.id]["Members"]:
                self.save_member_data(server, before)

            # create values for timestamp as unique key
            history = self.settings[server.id]["Members"][after.id]["History"]
            history[self.server_time()] = self.get_member_data(after)

            # save data
            dataIO.save_json(self.file_path, self.settings)

    def server_time(self):
        """Get UTC time instead of server time so data can be ported."""
        return str(datetime.datetime.utcnow())

    def get_member_data(self, member):
        """Return data to be stored."""
        return {
            "MemberName": member.name,
            "DisplayName": member.display_name,
            "Roles": [r.name for r in member.roles if r.name != "@everyone"]
        }


def check_folder():
    if not os.path.exists("data/rolehist"):
        print("Creating data/rolehist folder...")
        os.makedirs("data/rolehist")


def check_file():
    default = {}
    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default role history’s settings.json...")
        dataIO.save_json(f, default)

def setup(bot):
    check_folder()
    check_file()
    n = RoleHistory(bot)
    bot.add_cog(n)
