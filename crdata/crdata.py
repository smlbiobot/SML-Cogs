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

import os
import datetime as dt
import string
import asyncio
from datetime import timedelta

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

from cogs.deck import Deck
from collections import namedtuple

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

PATH = os.path.join("data", "crdata")
SETTINGS_JSON = os.path.join(PATH, "settings.json")
CLASHROYALE_JSON = os.path.join(PATH, "clashroyale.json")
CARDPOP_FILE = "cardpop-%Y-%m-%d.json"
SF_CREDITS = "Data provided by <http://starfi.re>"

DATA_UPDATE_INTERVAL = timedelta(days=1).seconds

RESULTS_MAX = 3
PAGINATION_TIMEOUT = 20


class BarChart:
    """Plotting bar charts as ASCII.

    Based on https://github.com/mkaz/termgraph
    """

    def __init__(self, labels, data, width):
        """Init."""
        self.tick = '▇'
        self.sm_tick = '░'
        self.labels = labels
        self.data = data
        self.width = width

    def chart(self):
        """Plot chart."""
        # verify data
        m = len(self.labels)
        if m != len(self.data):
            print(">> Error: Label and data array sizes don't match")
            return None

        # massage data
        # normalize for graph
        max_ = 0
        for i in range(m):
            if self.data[i] > max_:
                max_ = self.data[i]

        step = max_ / self.width
        label_width = max([len(label) for label in self.labels])

        out = []
        # display graph
        for i in range(m):
            out.append(
                self.chart_blocks(
                    self.labels[i], self.data[i], step,
                    label_width))

        return '\n'.join(out)

    def chart_blocks(
            self, label, count, step,
            label_width):
        """Plot each block."""
        blocks = int(count / step)
        out = "{0:>16}: ".format(label)
        if count < step:
            out += self.sm_tick
        else:
            for i in range(blocks):
                out += self.tick
        out +='  {}'.format(count)
        return out


class CRData:
    """Clash Royale card popularity using Starfi.re"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(SETTINGS_JSON)
        self.clashroyale = dataIO.load_json(CLASHROYALE_JSON)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        """Loop task: update data daily."""
        await self.bot.wait_until_ready()
        await self.update_data()
        await asyncio.sleep(DATA_UPDATE_INTERVAL)
        if self is self.bot.get_cog('CRData'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setcrdata(self, ctx: Context):
        """Set Clash Royale Data settings.

        Require: Starfire access permission.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcrdata.command(name="username", pass_context=True)
    async def setcrdata_username(self, ctx: Context, username):
        """Set Starfire username."""
        self.settings["STARFIRE_USERNAME"] = username
        await self.bot.say("Starfire username saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="password", pass_context=True)
    async def setcrdata_password(self, ctx: Context, password):
        """Set Starfire password."""
        self.settings["STARFIRE_PASSWORD"] = password
        await self.bot.say("Starfire password saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="url", pass_context=True)
    async def setcrdata_url(self, ctx: Context, url):
        """Set Starfire url."""
        self.settings["STARFIRE_URL"] = url
        await self.bot.say("Starfire URL saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @setcrdata.command(name="update", pass_context=True)
    async def setcrdata_update(self, ctx):
        """Grab data from Starfire if does not exist."""
        file = await self.update_data()
        if file is not None:
            await self.bot.say("Saved {}.".format(file))
        else:
            await self.bot.say("Today’s data already downloaded.")

    @setcrdata.command(name="forceupdate", pass_context=True)
    async def setcrdata_forceupdate(self, ctx):
        """Update data even if exists."""
        today = dt.date.today()
        today_file = today.strftime(CARDPOP_FILE)
        today_path = os.path.join(PATH, today_file)
        url = self.settings["STARFIRE_URL"]
        session = aiohttp.ClientSession(
            auth=aiohttp.BasicAuth(
                login=self.settings["STARFIRE_USERNAME"],
                password=self.settings["STARFIRE_PASSWORD"]))
        resp = await session.get(url)
        data = await resp.json()
        dataIO.save_json(today_path, data)
        await self.bot.say("Saved {}.".format(today_file))

    async def update_data(self):
        """Update data and return filename."""
        today = dt.date.today()
        today_file = today.strftime(CARDPOP_FILE)
        today_path = os.path.join(PATH, today_file)
        if not os.path.exists(today_path):
            url = self.settings["STARFIRE_URL"]
            session = aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(
                    login=self.settings["STARFIRE_USERNAME"],
                    password=self.settings["STARFIRE_PASSWORD"]))
            resp = await session.get(url)
            data = await resp.json()
            dataIO.save_json(today_path, data)
            return today_file
        return None

    def get_today_data(self):
        """Return today’s data."""
        today = dt.date.today()
        return self.get_data(today)

    def get_data(self, date):
        """Get data as json by date."""
        file = date.strftime(CARDPOP_FILE)
        path = os.path.join(PATH, file)
        if os.path.exists(path):
            return dataIO.load_json(path)
        return None

    @commands.group(pass_context=True, no_pm=True)
    async def crdata(self, ctx: Context):
        """Clash Royale data."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdata.command(name="decks", pass_context=True, no_pm=True)
    async def crdata_decks(self, ctx: Context):
        """List decks on global 200 leaderboard."""
        decks = self.get_today_data()["popularDecks"]
        await self.bot.say(
            "**Top 200 Decks**: Found {} results.".format(len(decks)))
        for i, deck in enumerate(decks):
            cards = deck["key"].split('|')
            usage = deck["usage"]
            card_ids = []
            for card in cards:
                card_id = self.sfid_to_id(card)
                card_ids.append(card_id)

            FakeMember = namedtuple("FakeMember", "name")

            await self.bot.get_cog("Deck").deck_get_helper(
                ctx,
                card1=card_ids[0],
                card2=card_ids[1],
                card3=card_ids[2],
                card4=card_ids[3],
                card5=card_ids[4],
                card6=card_ids[5],
                card7=card_ids[6],
                card8=card_ids[7],
                deck_name="Usage: {}".format(usage),
                author=FakeMember(name="Top 200 Decks")
            )

            if (i + 1) % RESULTS_MAX == 0 and (i + 1) < len(decks):
                def pagination_check(m):
                    return m.content.lower() == 'y'
                await self.bot.say(
                    "Would you like to see more results? (y/n)")
                answer = await self.bot.wait_for_message(
                    timeout=PAGINATION_TIMEOUT,
                    author=ctx.message.author,
                    check=pagination_check)
                if answer is None:
                    await self.bot.say(
                        "Search results aborted.\n{}".format(SF_CREDITS))
                    return

    @crdata.command(name="cards", pass_context=True, no_pm=True)
    async def crdata_cards(self, ctx: Context):
        """List popular cards on global 200 leaberboard."""
        await self.bot.send_typing(ctx.message.channel)
        cards = self.get_today_data()["popularCards"]
        await self.bot.say(
            "**Popular Cards** from Top 200 decks.")
        labels = [self.sfid_to_name(card["key"]) for card in cards]
        data = [card["usage"] for card in cards]
        chart = BarChart(labels, data, 30)
        await self.bot.say(box(chart.chart()))
        await self.bot.say("{} on {}.".format(SF_CREDITS, dt.date.today()))

    def sfid_to_id(self, sfid:str):
        """Convert Starfire ID to Card ID"""
        cards = self.clashroyale["Cards"]
        for card_key, card_data in cards.items():
            if card_data["sfid"] == sfid:
                return card_key

    def sfid_to_name(self, sfid:str):
        """Convert Starfire ID to Name"""
        s = sfid.replace('_', ' ')
        s = string.capwords(s)
        return s



def check_folder():
    if not os.path.exists(PATH):
        os.makedirs(PATH)

def check_file():
    defaults = {}
    if not dataIO.is_valid_json(SETTINGS_JSON):
        dataIO.save_json(SETTINGS_JSON, defaults)

def setup(bot):
    check_folder()
    check_file()
    bot.add_cog(CRData(bot))
