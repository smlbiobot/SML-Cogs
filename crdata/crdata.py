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

import asyncio
import datetime as dt
import json
import os
import re
import string
from collections import namedtuple
from datetime import timedelta

from __main__ import send_cmd_help
from discord.ext import commands
from discord.ext.commands import Context

from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

elasticsearch_available = False

try:
    # global ES connection
    HOST = 'localhost'
    PORT = 9200
    from elasticsearch import Elasticsearch
    from elasticsearch_dsl import DocType, Date, Integer, Text
    from elasticsearch_dsl.connections import connections

    connections.create_connection(hosts=[HOST], timeout=20)
    elasticsearch_available = True
except ImportError:
    pass

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


class BotEmoji:
    """Emojis available in bot."""
    def __init__(self, bot):
        self.bot = bot

    def name(self, name):
        """Emoji by name."""
        for server in self.bot.servers:
            for emoji in server.emojis:
                if emoji.name == name:
                    return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    def key(self, key):
        """Chest emojis by api key name or key.

        name is used by this cog.
        key is values returned by the api.
        Use key only if name is not set
        """
        if key in self.map:
            name = self.map[key]
            return self.name(name)
        return ''


class ClashRoyale:
    """Clash Royale Data."""
    instance = None

    class __ClashRoyale:
        """Singleton."""

        def __init__(self, *args, **kwargs):
            """Init."""
            self.data = dataIO.load_json(CLASH_ROYALE_JSON)

    def __init__(self, *args, **kwargs):
        """Init."""
        if not ClashRoyale.instance:
            ClashRoyale.instance = ClashRoyale.__ClashRoyale(*args, **kwargs)
        else:
            pass

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def card_elixir(self, card):
        """"Elixir of a card."""
        try:
            return self.data["Cards"][card]["elixir"]
        except KeyError:
            return 0


class Card():
    """Clash Royale Card."""

    def __init__(self, key=None, level=None):
        """Init.

        Params
        + name (str). Key in the ClashRoyale.json
        """
        self.key = key
        self.level = level

    @property
    def elixir(self):
        """Elixir value."""
        return ClashRoyale().card_elixir(self.key)

    def emoji(self, be: BotEmoji):
        """Emoji representation of the card."""
        if self.key is None:
            return ''
        name = self.key.replace('-', '')
        return be.name(name)


class Deck():
    """Clash Royale Deck.

    Contains 8 cards.
    """

    def __init__(self, card_keys=None, card_levels=None, rank=0, usage=0):
        """Init.

        Params
        + rank (int). Rank on the leaderboard.
        + cards []. List of card ids (keys in ClashRoyale.json).
        + card_levels []. List of card levels.
        """
        self.rank = rank
        self.usage = usage
        self.cards = [Card(key=key) for key in card_keys]
        if card_levels is not None:
            kl_zip = zip(card_keys, card_levels)
            self.cards = [Card(key=k, level=l) for k, l in kl_zip]

    @property
    def avg_elixir(self):
        """Average elixir of the deck."""
        elixirs = [c.elixir for c in self.cards if c.elixir != 0]
        return sum(elixirs) / len(elixirs)

    @property
    def avg_elixir_str(self):
        """Average elixir with format."""
        return 'Average Elixir: {:.3}'.format(self.avg_elixir)

    def emoji_repr(self, be: BotEmoji, show_levels=False):
        """Emoji representaion."""
        out = []
        for card in self.cards:
            emoji = card.emoji(be)
            level = card.level
            level_str = ''
            if show_levels and level is not None:
                level_str = '`{:.<2}`'.format(level)
            out.append('{}{}'.format(emoji, level_str))
        return ''.join(out)

    def __repr__(self):
        return ' '.join([c.key for c in self.cards])


class CRData:
    """Clash Royale Global 200 Decks."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(SETTINGS_JSON)
        self.clashroyale = dataIO.load_json(CLASHROYALE_JSON)

        if elasticsearch_available:
            self.es = Elasticsearch()

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
        await self.eslog_update_data()
        await asyncio.sleep(DATA_UPDATE_INTERVAL)
        if self is self.bot.get_cog('CRData'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def crdataset(self, ctx: Context):
        """Set Clash Royale Data settings.

        Require: Starfire access permission.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdataset.command(name="username", pass_context=True)
    async def crdataset_username(self, ctx: Context, username):
        """Set Starfire username."""
        self.settings["STARFIRE_USERNAME"] = username
        await self.bot.say("Starfire username saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @crdataset.command(name="password", pass_context=True)
    async def crdataset_password(self, ctx: Context, password):
        """Set Starfire password."""
        self.settings["STARFIRE_PASSWORD"] = password
        await self.bot.say("Starfire password saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @crdataset.command(name="url", pass_context=True)
    async def crdataset_url(self, ctx: Context, url):
        """Set Starfire url."""
        self.settings["STARFIRE_URL"] = url
        await self.bot.say("Starfire URL saved.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @crdataset.command(name="update", pass_context=True)
    async def crdataset_update(self, ctx):
        """Grab data from Starfire if does not exist."""
        data = await self.update_data()
        if data is not None:
            await self.bot.say("Data saved.")
        else:
            await self.bot.say("Data already downloaded.")

    @crdataset.command(name="forceupdate", pass_context=True)
    async def crdataset_forceupdate(self, ctx):
        """Update data even if exists."""
        data =  await self.update_data(forceupdate=True)
        if data is None:
            await self.bot.say("Update failed.")
        else:
            await self.bot.say("Data saved.")

    @crdataset.command(name="lastdata", pass_context=True)
    async def crdataset_lastdata(self, ctx):
        """Return last known data filename."""
        time = dt.datetime.utcnow()
        file = time.strftime(CARDPOP_FILE)
        path = os.path.join(PATH, file)
        while not os.path.exists(path):
            time = time - dt.timedelta(hours=1)
            file = time.strftime(CARDPOP_FILE)
            path = os.path.join(PATH, file)
        await self.bot.say("Last known data path: {}".format(path))

    @crdataset.command(name="cleandata", pass_context=True)
    async def crdataset_cleandata(self, ctx):
        """Remove all bad data files.

        Operation for legacy data files.
        Some files were saved when no data can be found.
        This command removes all data json files that are invalid.
        """
        prog = re.compile('cardpop-\d{4}-\d{2}-\d{2}-\d{2}.json')
        for root, dirs, files in os.walk(PATH):
            for file in files:
                result = prog.match(file)
                if result is not None:
                    path = os.path.join(PATH, file)
                    data = dataIO.load_json(path)
                    if "decks" not in data:
                        os.remove(path)
                        await self.bot.say(
                            "Removed invalid JSON: {}".format(path))

    @crdataset.command(name="elasticsearch", pass_context=True)
    async def crdataset_elasticsearch(self, ctx, enable:bool):
        """Enable / disabkle elasticsearch."""
        self.settings["ELASTICSEARCH"] = enable
        if enable:
            await self.bot.say("Elastic Search enabled.")
        else:
            await self.bot.say("ELastic Search disabled.")
        dataIO.save_json(SETTINGS_JSON, self.settings)

    @property
    def elasticsearch_enabled(self):
        """Use elasticsearch or not."""
        if elasticsearch_available \
                and "ELASTICSEARCH" in self.settings \
                and self.settings["ELASTICSEARCH"]:
            return True
        return False

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
                        # data = await resp.text()
                        # when data cannot be decoded,
                        # likely data source is down
                        data = None
        if data is not None:
            dataIO.save_json(now_path, data)

            if self.elasticsearch_enabled:
                self.eslog(data)

        return data

    async def get_now_data(self):
        """Return data at this hour."""
        now = dt.datetime.utcnow()
        data = self.get_data(now)
        if data is None:
            data = await self.update_data()
        return data

    def get_last_data(self):
        """Find and return last known data."""
        time = dt.datetime.utcnow()
        data = None
        while data is None:
            data = self.get_data(time)
            time = time - dt.timedelta(hours=1)
        return data

    def get_data(self, datetime_):
        """Get data as json by date and hour."""
        file = datetime_.strftime(CARDPOP_FILE)
        path = os.path.join(PATH, file)
        data = None
        if os.path.exists(path):
            data = dataIO.load_json(path)
            if "decks" not in data:
                data = None
        return data

    @commands.group(pass_context=True, no_pm=True)
    async def crdata(self, ctx: Context):
        """Clash Royale Global 200 data."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdata.command(name="decks", pass_context=True, no_pm=True)
    async def crdata_decks(self, ctx: Context):
        """List popular decks."""
        data = self.get_last_data()
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
        data = self.get_last_data()
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
        data = self.get_last_data()
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

    @crdata.command(name="cardnames", pass_context=True, no_pm=True)
    async def crdata_cardnames(self, ctx):
        """Display valid card names and abbreviations."""
        out = []
        for card_key, card_value in self.clashroyale["Cards"].items():
            names = [card_key]
            name = string.capwords(card_key.replace('-', ' '))
            for abbrev in card_value["aka"]:
                names.append(abbrev)
            rarity = string.capwords(card_value["rarity"])
            elixir = card_value["elixir"]
            out.append(
                "**{}** ({}, {} elixir): {}".format(
                    name, rarity, elixir, ", ".join(names)))

        for page in pagify("\n".join(out), shorten_by=24):
            await self.bot.say(page)

    @crdata.command(name="search", pass_context=True, no_pm=True)
    async def crdata_search(self, ctx: Context, *cards):
        """Search decks on the Global 200.

        1. Include card(s) to search for
        !crdata search fb log

        2. Exclude card(s) to search for (use - as prefix)
        !crdata search golem -lightning

        3. Elixir range (add elixir=min-max)
        !crdata search hog elixir=0-3.2

        e.g.: Find 3M Hog decks without battle ram under 4 elixir
        !crdata search 3m hog -br elixir=0-4
        """
        if not len(cards):
            await self.bot.say("You must enter at least one card.")
            await send_cmd_help(ctx)
            return

        found_decks = await self.search(ctx, *cards)
        await self.search_results(ctx, found_decks)

    async def search(self, ctx, *cards):
        """Perform the search and return found decks."""
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

        # validate card input is valid
        invalid_cards = []
        invalid_cards.extend(self.get_invalid_cards(include_cards))
        invalid_cards.extend(self.get_invalid_cards(exclude_cards))
        if len(invalid_cards) > 0:
            await self.bot.say(
                'Invalid card names: {}'.format(', '.join(invalid_cards)))
            await self.bot.say(
                'Type `!crdata cardnames` to see a list of valid input.')
            return

        include_cards = self.normalize_deck_data(include_cards)
        include_sfids = [self.id_to_sfid(c) for c in include_cards]
        exclude_cards = self.normalize_deck_data(exclude_cards)
        exclude_sfids = [self.id_to_sfid(c) for c in exclude_cards]

        data = self.get_last_data()
        decks = data["decks"]

        # sort card in decks
        sorted_decks = []
        for deck in decks:
            # when data is not clean, "key" may be missing
            # if this is the case, fix it
            clean_deck = []

            # data not clean = deck is None
            if deck is not None:
                for card in deck.copy():
                    if not "key" in card:
                        card["key"] = "soon"
                        card["level"] = 13
                    clean_deck.append(card)
                deck = clean_deck

                # for unknown reasons deck could sometimes be None in data src
                if deck is not None:
                    sorted_decks.append(
                        sorted(
                            deck.copy(),
                            key=lambda x: x["key"]))
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

        return found_decks

    async def search_results(self, ctx, found_decks):
        """Show search results."""
        await self.bot.say("Found {} decks.".format(len(found_decks)))

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
                len(found_decks),
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

        data = self.get_last_data()
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

        paginate = True
        if (row_id + 1) % RESULTS_MAX == 0 and (row_id + 1) < total_rows:
            await self.bot.say(
                "Would you like to see more results? (y/n)")
            answer = await self.bot.wait_for_message(
                timeout=PAGINATION_TIMEOUT,
                author=ctx.message.author)
            if answer is None:
                paginate = False
            elif not len(answer.content):
                paginate = False
            elif answer.content[0].lower() != 'y':
                paginate = False
        if paginate:
            return True
        else:
            await self.bot.say(
                "Search results aborted.\n{}".format(SF_CREDITS))
            return False

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
            else:
                deck[i] = None

        return deck

    def get_invalid_cards(self, cards):
        """Validate card data.

        Return list of cards which are invalid.
        """
        deck = [c.lower() if c is not None else '' for c in cards]
        invalid_cards = [c for c in deck if c not in self.cards_abbrev.keys()]
        return invalid_cards

    def deck_elixir_by_sfid(self, deck):
        """Return average elixir for a list of sfids."""
        cards_data = self.clashroyale["Cards"]
        cards = [self.sfid_to_id(c) for c in deck]
        elixirs = [cards_data[key]["elixir"] for key in cards]
        # count 1 less card if mirror
        total = 0
        for elixir in elixirs:
            if elixir:
                total += 1
        return sum(elixirs) / total

    async def eslog_update_data(self):
        """Update data for es logging."""
        url = self.settings["STARFIRE_URL"]
        async with aiohttp.ClientSession(
                auth=aiohttp.BasicAuth(
                    login=self.settings["STARFIRE_USERNAME"],
                    password=self.settings["STARFIRE_PASSWORD"])) as session:
            async with session.get(url) as resp:
                try:
                    data = await resp.json()
                except json.decoder.JSONDecodeError:
                    data = None
        if data is not None:
            if self.elasticsearch_enabled:
                self.eslog(data)

    def eslog(self, data):
        """Elasticsearch logging of data"""

        now = dt.datetime.utcnow()
        now_str = now.strftime('%Y.%m.%d')
        index_name = 'crdata-{}'.format(now_str)


        class PopularCard(DocType):
            """ESLog Popular Card"""
            key = Text()
            usage = Integer()
            timestamp = Date()

            def save(self, **kwargs):
                return super(PopularCard, self).save(**kwargs)

        class PopularDeck(DocType):
            """ESLog Popular Deck"""
            deck_name = Text()
            usage = Integer()
            timestamp = Date()
            deck_cards = []

            def save(self, **kwargs):
                return super(PopularDeck, self).save(**kwargs)

        class Leaderboard(DocType):
            """ESLog Leaderboard"""
            rank = Integer()
            deck = []
            timestamp = Date()

            def save(self, **kwargs):
                return super(Leaderboard, self).save(**kwargs)

        # leaderboard
        for rank, deck in enumerate(data["decks"], 1):
            lb = Leaderboard(
                rank=rank,
                deck=deck,
                timestamp=dt.datetime.utcnow()
            )
            lb.save(index=index_name)

        # cards
        for card in data["popularCards"]:
            pcard = PopularCard(
                key=card["key"],
                usage=card["usage"],
                timestamp=dt.datetime.utcnow()
            )
            pcard.save(index=index_name)

        # decks
        for deck in data["popularDecks"]:
            now = dt.datetime.utcnow()
            now_str = now.strftime('%Y.%m.%d')
            index_name = 'crdata-{}'.format(now_str)
            pdeck = PopularDeck(
                deck_name=deck["key"],
                deck_cards=deck["key"].split('|'),
                usage=deck["usage"],
                timestamp=dt.datetime.utcnow()
            )
            pdeck.save(index=index_name)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    defaults = {}
    if not dataIO.is_valid_json(SETTINGS_JSON):
        dataIO.save_json(SETTINGS_JSON, defaults)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    bot.add_cog(CRData(bot))
