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
from discord import Member
from discord.ext import commands
from discord.ext.commands import Context
from random import choice
from .utils.dataIO import dataIO
from __main__ import send_cmd_help

import os
import datetime

PATH_LIST = ['data', 'clanchest']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(PATH, "settings.json")
BOTCOMMANDER_ROLE = ["Bot Commander"]

clans = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel']
start_date = datetime.date(2017, 1, 16)



class ClanChests:
    """
    Manage clan chest data

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(pass_context=True, no_pm=True, aliases=["cc"])
    async def clanchest(self, ctx: Context):
        """Clan Chest Management."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @clanchest.command(name="show", pass_context=True, no_pm=True)
    async def show_clanchest(self, ctx: Context):
        """Display the clan chest historic data."""
        server = ctx.message.server

        if server.id not in self.settings:
            self.settings[server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "ClanChests": {}
            }

            for c in clans:
                self.settings[server.id]["ClanChests"][c] = "0"

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        data = discord.Embed(
            color=discord.Color(value=color),
            title="Trophy requirements",
            description=
                "Minimum clanchest to join our clans. "
                "Current clanchest required. "
                "PB is only used within 12 hours after the clan chest has been completed."
            )

        for clan in clans:
            name = '{}{}'.format(clan[0].upper(), clan[1:].lower())
            value = self.settings[server.id]["ClanChests"][clan]

            data.add_field(name=str(name), value='{:,}'.format(int(value)))

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(name=server.name)

        await self.bot.say(embed=data)

    @clanchest.command(name="set", pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def set_clanchest(self, ctx, member: Member, crowns: int):
        """Set the crown contribution by members"""
        server = ctx.message.server
        clan = clan.lower()

        if server.id not in self.settings:
            self.settings[server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "ClanChests": {}
                }

            for c in clans:
                self.settings[server.id]["ClanChests"][c] = "0"

        if clan not in self.settings[server.id]["ClanChests"]:
            await self.bot.say("Clan name is not valid.")

        else:
            self.settings[server.id]["ClanChests"][clan] = req
            await self.bot.say("Trophy requiremnt for {} updated to {}.".format(clan, req))

        dataIO.save_json(self.file_path, self.settings)



def check_folder():
    if not os.path.exists(PATH):
        print("Creating data/clanchest folder...")
        os.makedirs(PATH)


def check_file():
    d = {}
    if not dataIO.is_valid_json(JSON):
        print("Creating default clanchest‘ settings.json...")
        dataIO.save_json(PATH, d)


def setup(bot):
    check_folder()
    check_file()
    n = ClanChests(bot)
    bot.add_cog(n)

