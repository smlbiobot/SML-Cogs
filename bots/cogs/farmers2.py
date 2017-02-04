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


settings_path = "data/farmers2/settings.json"
clans = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel']
start_date = datetime.date(2017, 1, 16)

class Farmers2:
    """
    Manage, display and set Clan chest farmers data

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(settings_path)

    @commands.group(pass_context=True, no_pm=True)
    async def farmers2(self, ctx):
        """Display Clan Chest historic records"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @farmers2.command(name="show", pass_context=True, no_pm=True)
    async def _show_farmers2(self, ctx, week:str=None):
        """Display the requirements"""

        server = ctx.message.server

        if server.id not in self.settings:
            self.settings[server.id] = { 
                "ServerName": str(server),
                "ServerID": str(server.id),
                "ClanChests": { }
                }

        #     for c in clans:
        #         self.settings[server.id]["Trophies"][c] = "0"

        # color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        # color = int(color, 16)

        # data = discord.Embed(
        #     color=discord.Color(value=color),
        #     title="Trophy requirements",
        #     description="Minimum farmers2 to join our clans. "
        #                 "Current farmers2 required. "
        #                 "PB is only used within 12 hours after the clan chest has been completed."
        #     )

        # for clan in clans:
        #     name = '{}{}'.format(clan[0].upper(), clan[1:].lower())
        #     value = self.settings[server.id]["Trophies"][clan]

        #     data.add_field(name=str(name), value='{:,}'.format(int(value)))

        # if server.icon_url:
        #     data.set_author(name=server.name, url=server.icon_url)
        #     data.set_thumbnail(url=server.icon_url)
        # else:
        #     data.set_author(name=server.name)

        # await self.bot.say(embed=data)

        
                    
    @farmers2.command(name="set", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def _set_farmers2(self, ctx, clan:str, req:str):
        """(MOD) Set the trophy requirements for clans"""

        # hacking the permission settings
        # mention_everyone=True for all co-leaders and up

        # server = ctx.message.server
        # members = server.members

        # clan = clan.lower()

        # if server.id not in self.settings:
        #     self.settings[server.id] = { 
        #         "ServerName": str(server),
        #         "ServerID": str(server.id),
        #         "Trophies": { }
        #         }

        #     for c in clans:
        #         self.settings[server.id]["Trophies"][c] = "0"

        # if clan not in self.settings[server.id]["Trophies"]:
        #     await self.bot.say("Clan name is not valid.")

        # else:
        #     self.settings[server.id]["Trophies"][clan] = req
        #     await self.bot.say("Trophy requiremnt for {} updated to {}.".format(clan, req))

        # dataIO.save_json(self.file_path, self.settings)



def check_folder():
    if not os.path.exists("data/farmers2"):
        print("Creating data/farmers2 folder...")
        os.makedirs("data/farmers2")


def check_file():
    d = {}

    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default farmers2‘ settings.json...")
        dataIO.save_json(f, d)


def setup(bot):
    check_folder()
    check_file()
    n = Farmers2(bot)
    bot.add_cog(n)

