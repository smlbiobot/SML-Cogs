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
from discord import Reaction
from discord import User
from discord.ext import commands
from discord.ext.commands import Context

# check if BeautifulSoup4 is installed
try:
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False

import aiohttp

DATA_URL =\
    "https://app.nuclino.com/p/Clan-Chest-Farmers-kZCL4FSBYPhSTgmIhDxGPD"
NUMBS = {
    "back": "⬅",
    "exit": "❌",
    "next": "➡"
}


class Farmers:
    """Grab Clan Chest Farmers data.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        """Clan chest farmers init."""
        self.bot = bot
        self.listen_to_reaction = False
        self.reaction_messages = {}

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
                color = 'FF0000'
                color = int(color, 16)

                title = "Clan Chest Farmers"
                description = (
                    "Members who have contributed 150+ crowns "
                    "or 25+ 2v2 wins to their clan chests.\n"
                    "{} (Week {})").format(
                        season[week].get_text(), week + 1)

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
            await self.farmers_menu(ctx, embeds, message=None, page=week)

    async def farmers_menu(
            self, ctx: Context, embeds: list, message: Message=None,
            page=0):
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
            self.reaction_messages[message.id] = {
                "id": message.id,
                "message": message,
                "author": ctx.message.author,
                "author_id": ctx.message.author.id,
                "page": page,
                "embeds": embeds,
                "ctx": ctx
            }
            self.listen_to_reaction = True
        else:
            message = await self.bot.edit_message(message, embed=embed)

    async def on_reaction_add(self, reaction: Reaction, user: User):
        """Event: on_reaction_add."""
        if not self.listen_to_reaction:
            return
        await self.handle_reaction(reaction, user)

    async def on_reaction_remove(self, reaction: Reaction, user: User):
        """Event: on_reaction_remove."""
        if not self.listen_to_reaction:
            return
        await self.handle_reaction(reaction, user)

    async def handle_reaction(self, reaction: Reaction, user: User):
        """Handle reaction if on farmers menu."""
        if user == self.bot.user:
            return
        if reaction.message.id not in self.reaction_messages:
            return
        if reaction.emoji not in NUMBS.values():
            return
        msg_settings = self.reaction_messages[reaction.message.id]
        if user != msg_settings["author"]:
            return

        message = reaction.message
        reacts = {v: k for k, v in NUMBS.items()}
        react = reacts[reaction.emoji]

        page = self.reaction_messages[message.id]["page"]
        embeds = self.reaction_messages[message.id]["embeds"]
        ctx = self.reaction_messages[message.id]["ctx"]

        if react == "next":
            next_page = 0
            if page == len(embeds) - 1:
                next_page = 0  # Loop around to the first item
            else:
                next_page = page + 1
            self.reaction_messages[message.id]["page"] = next_page
            await self.farmers_menu(
                ctx, embeds, message=message,
                page=next_page)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(embeds) - 1  # Loop around to the last item
            else:
                next_page = page - 1
            self.reaction_messages[message.id]["page"] = next_page
            await self.farmers_menu(
                ctx, embeds, message=message,
                page=next_page)
        else:
            del self.reaction_messages[message.id]
            await self.bot.clear_reactions(message)
            if not len(self.reaction_messages):
                self.listen_to_reaction = False


def setup(bot):
    """Add cog to bog."""
    if soupAvailable:
        bot.add_cog(Farmers(bot))
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
