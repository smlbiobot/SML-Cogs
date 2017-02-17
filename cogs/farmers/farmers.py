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
from .utils.dataIO import fileIO
import os

try: # check if BeautifulSoup4 is installed
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False

import aiohttp

default_settings = {"DATA_URL": "https://app.nuclino.com/p/Clan-Chest-Farmers-kZCL4FSBYPhSTgmIhDxGPD"}
settings_path = "data/farmers/settings.json"

class Farmers:
    """
    Grabs Clan Chest Farmers data from Nuclino
    and display in Discord chat.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = fileIO(settings_path, "load")

    @commands.command(pass_context=True)
    async def farmers(self, ctx, week=None):
        """"
        Fetches list of farmers from Nuclino doc
        """

        # Parse Data
        # url = self.settings[server.id]["DATA_URL"]
        url = "https://app.nuclino.com/p/Clan-Chest-Farmers-kZCL4FSBYPhSTgmIhDxGPD"
        async with aiohttp.get(url) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")

        # try:
            root = soup.find(class_="ProseMirror")

            # header = root.find_all('h1')
            season = root.find_all('h2')

            # Parse HTML to find name and trophies
            ul_db = []
            for ul in root.find_all('ul'):
                li_db = []
                for li in ul.find_all('li'):
                    li_db.append(li.get_text())
                ul_db.append(li_db)

            if week is None:
                # no arguments supplied, assume last week
                week = len(ul_db) - 1
            elif int(week) >= len(ul_db):
                # argument larger than supplied, assume last week
                week = len(ul_db) - 1
            else:
                week = int(week) - 1

            # embed output
            color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
            color = int(color, 16)

            title = "Clan Chest Farmers"
            description = f"""Members who have contributed 150+ crowns to their clan chests
                             {season[week].get_text()} (Week {week+1})"""

            data = discord.Embed(
                title=title,
                description=description,
                color=discord.Color(value=color))

            for li in ul_db[week]:
                field_data = li.split(': ')
                name = field_data[0]
                value = field_data[1]

                data.add_field(name=str(name), value=str(value))

             
        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")




def check_folders():
    if not os.path.exists("data/farmers"):
        print("Creating data/farmers folder...")
        os.makedirs("data/farmers")


def check_files():
    f = settings_path
    if not fileIO(f, "check"):
        print("Creating farmers settings.json...")
        fileIO(f, "save", {})
    else:  # consistency check
        current = fileIO(f, "load")
        for k, v in current.items():
            if v.keys() != default_settings.keys():
                for key in default_settings.keys():
                    if key not in v.keys():
                        current[k][key] = default_settings[key]
                        print("Adding " + str(key) +
                              " field to farmers settings.json")
        # upgrade. Before GREETING was 1 string
        for server in current.values():
            if isinstance(server["DATA_URL"], str):
                server["DATA_URL"] = [server["DATA_URL"]]
        fileIO(f, "save", current)

def setup(bot):
    check_folders()
    check_files()
    if soupAvailable:
        bot.add_cog(Farmers(bot))
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
