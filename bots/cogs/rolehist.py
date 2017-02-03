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
from .utils.dataIO import dataIO
from .general import General
from __main__ import send_cmd_help
import os
import datetime

# try: # check if BeautifulSoup4 is installed
#     from bs4 import BeautifulSoup
#     soupAvailable = True
# except:
#     soupAvailable = False

# import aiohttp

settings_path = "data/rolehist/settings.json"

class RoleHistory:
    """
    Edit and store history of user roles.

    Reference: discord.on_member_update

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.settings = dataIO.load_json(self.file_path)
        print("rolehist: __init__")
        # self.remove_old()

    @commands.group(pass_context=True, no_pm=True)
    async def rolehist(self, ctx):
        """Role History Management"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @rolehist.command(name="show", pass_context=True, no_pm=True)
    async def _show_role_hist(self, ctx, username):
        """Display the role history of a user"""

        author = ctx.message.author
        server = ctx.message.server

        if not username:
            username = author


        if server.id in self.settings:
            for member_key, member_value in self.settings[server.id]["Members"].items():
                
                member = server.get_member(member_key)

                if username == member.display_name:
                    await self.bot.say("Found Member")
                    await ctx.invoke(General.userinfo, user=member)
                    out = []

                    hist = sorted(member_value["History"].items())

                    for time_key, time_value in hist:
                        out.append('**{}**'.format(time_key))
                        out.append(', '.join(time_value["Roles"]))
 
                    await self.bot.say("\n".join(out))


    async def member_update(self, before, after):
        server = before.server

        # process only on role changes
        if before.roles != after.roles:
 
            # print('======')
            # print(f"{self.server_time()}")
            # print('Server: {}'.format(str(server)))
            # print('Username: {}'.format(str(before.display_name)))
            # print("Roles: ")
            # print(str(', '.join([r.name for r in after.roles])))
            

            if server.id not in self.settings:
                self.settings[server.id] = { 
                    "ServerName": str(server),
                    "ServerID": str(server.id),
                    "Members": {}
                    }
            # Update server name in settings in case they have changed over time
            self.settings[server.id]["ServerName"] = str(server)

            # add member settings if it does not exist 
            # initialize with before data
            # using server time as unique id for role changes
            if before.id not in self.settings[server.id]["Members"]:
                self.settings[server.id]["Members"][before.id] = { 
                    "MemberID" : before.id,
                    "History": {
                        f"{self.server_time()}" : self.get_member_data(before)
                        }
                    
                    }

            # create values for timestamp as unique key
            self.settings[server.id]["Members"][after.id]["History"][self.server_time()] = self.get_member_data(after)

            # save data
            dataIO.save_json(self.file_path, self.settings)

    def server_time(self):
        """Get UTC time instead of server local time so data can be ported between servers"""
        return str(datetime.datetime.utcnow())

    def get_member_data(self, member):
        """Return data to be stored."""
        return { "MemberName": member.name,
                 "DisplayName": member.display_name,
                 "Roles": [r.name for r in member.roles if r.name != "@everyone"]
                 }

def check_folder():
    if not os.path.exists("data/rolehist"):
        print("Creating data/rolehist folder...")
        os.makedirs("data/rolehist")


def check_file():
    banned = {}

    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default role history’s settings.json...")
        dataIO.save_json(f, banned)


def setup(bot):
    check_folder()
    check_file()
    n = RoleHistory(bot)
    bot.add_listener(n.member_update, "on_member_update")
    bot.add_cog(n)

