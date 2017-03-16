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
from discord import Message
from discord.ext import commands
from discord.ext.commands import Context
from random import choice
from .utils.dataIO import fileIO
import os

try: # check if BeautifulSoup4 is installed
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False

import aiohttp

DATA_URL =\
    "https://app.nuclino.com/p/Clan-Chest-Farmers-kZCL4FSBYPhSTgmIhDxGPD"
settings_path = "data/farmers/settings.json"

numbs = {
    "back": "⬅",
    "exit": "❌",
    "next": "➡"
}


class Farmers:
    """Grabs Clan Chest Farmers data from Nuclino
    and display in Discord chat.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = fileIO(settings_path, "load")

    async def farmer_embeds(self, ctx: Context):
        """Create list of embeds from data."""
        embeds = []
        async with aiohttp.get(DATA_URL) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")

            root = soup.find(class_="ProseMirror")

            season = root.find_all('h2')

            # Parse HTML to find name and trophies
            ul_db = []
            for ul in root.find_all('ul'):
                li_db = []
                for li in ul.find_all('li'):
                    li_db.append(li.get_text())
                ul_db.append(li_db)

            for week in range(len(ul_db)):
                # embed output
                # color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
                color = 'FF0000'
                color = int(color, 16)

                title = "Clan Chest Farmers"
                description = f"""Members who have contributed 150+ crowns to their clan chests
                                 {season[week].get_text()} (Week {week+1})"""

                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color(value=color))

                for li in ul_db[week]:
                    field_data = li.split(': ')
                    name = field_data[0]
                    value = field_data[1]

                    embed.add_field(name=str(name), value=str(value))

                embeds.append(embed)
        if len(embeds):
            return embeds
        else:
            return None

    @commands.command(pass_context=True)
    async def farmers(self, ctx: Context, week=None):
        """Display historic records of clan chest farmers.

        Optionally include week number.
        !farmers
        !farmers 5
        """
        embeds = await self.farmer_embeds(ctx)

        if embeds is not None:
            if week is None:
                # no arguments supplied, assume last week
                week = len(embeds) - 1
            elif int(week) >= len(embeds):
                # argument larger than supplied, assume last week
                week = len(embeds) - 1
            else:
                week = int(week) - 1
            await self.farmers_menu(
                ctx, embeds, message=None, page=week, timeout=30)

    async def farmers_menu(
            self, ctx: Context, embeds: list, message: Message=None,
            page=0, timeout: int=30):
        """Display data with pagination.

        Menu control logic from
        https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py
        """
        embed = embeds[page]
        if not message:
            message =\
                await self.bot.send_message(ctx.message.channel, embed=embed)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=embed)

        react = await self.bot.wait_for_reaction(
            message=message, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌"])

        if react is None:
            try:
                await self.bot.remove_reaction(message, "⬅", self.bot.user)
                await self.bot.remove_reaction(message, "❌", self.bot.user)
                await self.bot.remove_reaction(message, "➡", self.bot.user)
            except:
                pass
            return None
        reacts = {v: k for k, v in numbs.items()}
        react = reacts[react.reaction.emoji]
        if react == "next":
            next_page = 0
            if page == len(embeds) - 1:
                next_page = 0  # Loop around to the first item
            else:
                next_page = page + 1
            return await self.farmers_menu(
                ctx, embeds, message=message,
                page=next_page, timeout=timeout)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(embeds) - 1  # Loop around to the last item
            else:
                next_page = page - 1
            return await self.farmers_menu(
                ctx, embeds, message=message,
                page=next_page, timeout=timeout)
        else:
            try:
                return await\
                    self.bot.delete_message(message)
            except:
                pass




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
