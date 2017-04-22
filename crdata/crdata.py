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
import re
import datetime as dt
import string
import asyncio
import json
from datetime import timedelta
from collections import Counter

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
CARDPOP_FILE = "cardpop-%Y-%m-%d-%H.json"
SF_CREDITS = "Data provided by <http://starfi.re>"

DATA_UPDATE_INTERVAL = timedelta(minutes=5).seconds

RESULTS_MAX = 3
PAGINATION_TIMEOUT = 20

def jaccard_similarity(x, y):
    intersection_cardinality = len(set.intersection(*[set(x), set(y)]))
    union_cardinality = len(set.union(*[set(x), set(y)]))
    return intersection_cardinality / float(union_cardinality)


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
        out += '  {}'.format(count)
        return out


class CRData:
    """Clash Royale Global 200 Decks."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(SETTINGS_JSON)
        self.clashroyale = dataIO.load_json(CLASHROYALE_JSON)

        # init card data
        self.cards = []
        self.cards_abbrev = {}

        for card_key, card_value in self.clashroyale["Cards"].items():
            self.cards.append(card_key)
            self.cards_abbrev[card_key] = card_key

            if card_key.find('-'):
                self.cards_abbrev[card_key.replace('-', '')] = card_key

            aka_list = card_value["aka"]
            for aka in aka_list:
                self.cards_abbrev[aka] = card_key
                if aka.find('-'):
                    self.cards_abbrev[aka.replace('-', '')] = card_key

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
        data = await self.update_data()
        if data is not None:
            await self.bot.say("Data saved.")
        else:
            await self.bot.say("Data already downloaded.")

    @setcrdata.command(name="forceupdate", pass_context=True)
    async def setcrdata_forceupdate(self, ctx):
        """Update data even if exists."""
        await self.update_data(forceupdate=True)
        await self.bot.say("Data saved.")

    async def update_data(self, forceupdate=False):
        """Update data and return data."""
        now = dt.datetime.utcnow()
        now_file = now.strftime(CARDPOP_FILE)
        now_path = os.path.join(PATH, now_file)
        data = None
        will_update = forceupdate or (not os.path.exists(now_path))
        if will_update:
            url = self.settings["STARFIRE_URL"]
            async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(
                    login=self.settings["STARFIRE_USERNAME"],
                    password=self.settings["STARFIRE_PASSWORD"])) as session:
                async with session.get(url) as resp:
                    # resp = await session.get(url)
                    try:
                        data = await resp.json()
                    except json.decoder.JSONDecodeError:
                        data = await resp.text()
        # if data is None:
        #     print("Data exists already as {}".format(now_path))
        if data is not None:
            dataIO.save_json(now_path, data)
        return data

    async def get_now_data(self):
        """Return data at this hour."""
        now = dt.datetime.utcnow()
        data = self.get_data(now)
        if data is None:
            data = await self.update_data()
        return data

    def get_data(self, datetime_):
        """Get data as json by date and hour."""
        file = datetime_.strftime(CARDPOP_FILE)
        path = os.path.join(PATH, file)
        if os.path.exists(path):
            return dataIO.load_json(path)
        return None

    @commands.group(pass_context=True, no_pm=True)
    async def crdata(self, ctx: Context):
        """Clash Royale Global 200 data."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdata.command(name="decks", pass_context=True, no_pm=True)
    async def crdata_decks(self, ctx: Context):
        """List popular decks."""
        data = await self.get_now_data()
        decks = data["popularDecks"]
        await self.bot.say(
            "**Top 200 Decks**: Found {} results.".format(len(decks)))
        for i, deck in enumerate(decks):
            cards = deck["key"].split('|')
            usage = deck["usage"]
            card_ids = []
            for card in cards:
                card_id = self.sfid_to_id(card)
                card_ids.append(card_id)

            show_next = await self.show_result_row(
                ctx,
                card_ids,
                i,
                len(decks),
                deck_name="Usage: {}".format(usage),
                author="Top 200 Decks")

            if not show_next:
                return

    @crdata.command(name="cards", pass_context=True, no_pm=True)
    async def crdata_cards(self, ctx: Context):
        """List popular cards."""
        await self.bot.send_typing(ctx.message.channel)
        data = await self.get_now_data()
        cards = data["popularCards"]
        await self.bot.say(
            "**Popular Cards** from Top 200 decks.")
        labels = [self.sfid_to_name(card["key"]) for card in cards]
        data = [card["usage"] for card in cards]
        chart = BarChart(labels, data, 30)
        await self.bot.say(box(chart.chart()))
        await self.bot.say("{} on {}.".format(SF_CREDITS, dt.date.today()))

    @crdata.command(
        name="leaderboard", aliases=['lb'], pass_context=True, no_pm=True)
    async def crdata_leaderboard(self, ctx: Context):
        """List decks sorted by rank."""
        await self.bot.say("**Global 200 Leaderboard Decks**")
        data = await self.get_now_data()
        decks = data["decks"]
        for i, deck in enumerate(decks):
            cards = [self.sfid_to_id(card["key"]) for card in deck]
            levels = [card["level"] for card in deck]

            desc = "**Rank {}: **".format(i + 1)
            for j, card in enumerate(cards):
                desc += "{} ".format(self.id_to_name(card))
                desc += "({}), ".format(levels[j])

            show_next = await self.show_result_row(
                ctx,
                cards,
                i,
                len(decks),
                deck_name="Rank {}".format(i + 1),
                author="Top 200 Decks",
                description=desc[:-1])

            if not show_next:
                return

    @crdata.command(name="search", pass_context=True, no_pm=True)
    async def crdata_search(self, ctx: Context, *cards):
        """Search decks with cards.

        !crdata search fb log
        !crdata search golem lightning elixir=2-5
        !crdata search hog elixir=0-3.2
        """
        if not len(cards):
            await self.bot.say("You must neter at least one card.")
            return

        elixir_p = re.compile('elixir=([\d\.]*)-([\d\.]*)')

        elixir_min = 0
        elixir_max = 10
        elixir = [c for c in cards if elixir_p.match(c)]
        if elixir:
            elixir = elixir[0]
            cards = [c for c in cards if not elixir_p.match(c)]
            m = elixir_p.match(elixir)
            if m.group(1):
                elixir_min = float(m.group(1))
            if m.group(2):
                elixir_max = float(m.group(2))

        # break lists out by include and exclude
        include_cards = [c for c in cards if not c.startswith('-')]
        exclude_cards = [c[1:] for c in cards if c.startswith('-')]

        include_cards = self.normalize_deck_data(include_cards)
        include_sfids = [self.id_to_sfid(c) for c in include_cards]
        exclude_cards = self.normalize_deck_data(exclude_cards)
        exclude_sfids = [self.id_to_sfid(c) for c in exclude_cards]

        cards = self.normalize_deck_data(cards)

        data = await self.get_now_data()
        decks = data["decks"]

        # sort card in decks
        sorted_decks = []
        for deck in decks:
            # for unknown reasons deck could sometimes be None in data src
            if deck is not None:
                sorted_decks.append(
                    sorted(deck.copy(), key=lambda x: x["key"]))
        decks = sorted_decks

        found_decks = []
        unique_decks = []

        # debug: to show uniques or not
        unique_only = False

        for rank, deck in enumerate(decks):
            # in unknown instances, starfi.re returns empty rows
            if deck is not None:
                deck_cards = [card["key"] for card in deck]
                deck_elixir = self.deck_elixir_by_sfid(deck_cards)
                if set(include_sfids) <= set(deck_cards):
                    include_deck = True
                    if len(exclude_sfids):
                        for sfid in exclude_sfids:
                            if sfid in deck_cards:
                                include_deck = False
                                break
                    if not elixir_min <= deck_elixir <= elixir_max:
                        include_deck = False
                    if include_deck:
                        found_deck = {
                            "deck": deck,
                            "cards": set([c["key"] for c in deck]),
                            "count": 1,
                            "ranks": [str(rank + 1)]
                        }
                        if found_deck["cards"] in unique_decks:
                            found_deck["count"] += 1
                            found_deck["ranks"].append(str(rank + 1))
                            if not unique_only:
                                unique_decks.append(found_deck["cards"])
                        else:
                            found_decks.append(found_deck)
                            unique_decks.append(found_deck["cards"])

        await self.bot.say("Found {} decks.".format(
            len(found_decks)))

        for i, data in enumerate(found_decks):
            deck = data["deck"]
            rank = ", ".join(data["ranks"])
            usage = data["count"]
            cards = [self.sfid_to_id(card["key"]) for card in deck]
            levels = [card["level"] for card in deck]

            # desc = "**Rank {}: (Usage: {})**".format(rank, usage)
            desc = "**Rank {}: **".format(rank)
            for j, card in enumerate(cards):
                desc += "{} ".format(self.id_to_name(card))
                desc += "({}), ".format(levels[j])
            desc = desc[:-1]

            show_next = await self.show_result_row(
                ctx,
                cards,
                i,
                len(decks),
                deck_name="Rank {}".format(rank),
                author="Top 200 Decks",
                description=desc[:-1])

            if not show_next:
                return

    @crdata.command(name="similar", pass_context=True)
    async def crdata_similar(self, ctx, *cards):
        """Find similar decks with specific deck or rank on leaderboard.

        Find decks similar to the 2nd deck on Global 200:
        !crdata similar 2

        Find decks similar to what is entered:
        !crdata similar hog log barrel gg skarmy princess it knight
        """
        is_rank = len(cards) == 1 and cards[0].isdigit()
        is_card = len(cards) == 8
        if not is_rank and not is_card:
            await send_cmd_help(ctx)
            return

        data = await self.get_now_data()
        decks = data["decks"]

        # sort card in decks
        # extract card keys as list
        sorted_decks = []
        for deck in decks:
            d = sorted(deck.copy(), key=lambda x: x["key"])
            d = [self.sfid_to_id(card["key"]) for card in d]
            sorted_decks.append(d)
        decks = sorted_decks

        if is_rank:
            deck_name = "Rank {}".format(cards[0])
            deck_author = "Top 200 Decks"
            deck = decks[int(cards[0]) - 1]
        else:
            deck_name = "User Deck"
            deck_author = "Similarity Search"
            cards = self.normalize_deck_data(cards)
            deck = [c for c in cards]

        # Entered deck
        await self.bot.say(
            "Listing decks from Global 200 that is most similar to:")
        await self.show_result_row(
            ctx,
            deck,
            0,
            1,
            deck_name=deck_name,
            author=deck_author)

        # Similarity search
        results = []
        uniques = []
        for candidate in decks:
            similarity = jaccard_similarity(deck, candidate)
            if similarity != 1.0:
                result = {
                    "deck": candidate,
                    "similarity": similarity
                }
                if candidate not in uniques:
                    uniques.append(candidate)
                    results.append(result)

        # Sort by similarity
        results = sorted(results, key=lambda x: -x["similarity"])

        # Remove same deck (similarity = 1)
        results = [r for r in results if r["similarity"] != 1.0]

        # Output

        for i, data in enumerate(results):
            deck = data["deck"]
            desc = "Similarity: {:.3f}".format(data["similarity"])

            show_next = await self.show_result_row(
                ctx,
                deck,
                i,
                len(results),
                deck_name=desc,
                author="Top 200 Decks",
                description=desc)

            if not show_next:
                return


    async def show_result_row(
            self, ctx: Context, cards, row_id, total_rows,
            deck_name="", author="", description=None):
        """Display results of deck.

        Return True if continue.
        Return False if abort.
        """
        if description is not None:
            await self.bot.say(description)
        FakeMember = namedtuple("FakeMember", "name")
        await self.bot.get_cog("Deck").deck_get_helper(
            ctx,
            card1=cards[0],
            card2=cards[1],
            card3=cards[2],
            card4=cards[3],
            card5=cards[4],
            card6=cards[5],
            card7=cards[6],
            card8=cards[7],
            deck_name=deck_name,
            author=FakeMember(name=author)
        )

        if (row_id + 1) % RESULTS_MAX == 0 and (row_id + 1) < total_rows:
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
                return False
        return True

    def sfid_to_id(self, sfid: str):
        """Convert Starfire ID to Card ID."""
        cards = self.clashroyale["Cards"]
        for card_key, card_data in cards.items():
            if card_data["sfid"] == sfid:
                return card_key

    def sfid_to_name(self, sfid: str):
        """Convert Starfire ID to Name."""
        s = sfid.replace('_', ' ')
        s = string.capwords(s)
        return s

    def id_to_name(self, id: str):
        """Convert ID to Name."""
        s = id.replace('-', ' ')
        s = string.capwords(s)
        return s

    def id_to_sfid(self, id: str):
        """Convert Card ID to Starfire ID."""
        cards = self.clashroyale["Cards"]
        return cards[id]["sfid"]

    def normalize_deck_data(self, cards):
        """Return a deck list with normalized names."""
        deck = [c.lower() if c is not None else '' for c in cards]

        # replace abbreviations
        for i, card in enumerate(deck):
            if card in self.cards_abbrev.keys():
                deck[i] = self.cards_abbrev[card]

        return deck

    def deck_elixir_by_sfid(self, deck):
        """Return average elixir for a list of sfids."""
        cards_data = self.clashroyale["Cards"]
        cards = [self.sfid_to_id(c) for c in deck]
        elixirs = [cards_data[key]["elixir"] for key in cards]
        return sum(elixirs) / 8


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
