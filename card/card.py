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
import matplotlib
matplotlib.use('Agg')

from .utils.dataIO import dataIO
from __main__ import send_cmd_help
from cogs.utils.chat_formatting import pagify, box
from discord.ext import commands
from discord.ext.commands import Context
from itertools import islice
from matplotlib import pyplot as plt
from random import choice
import datetime
import asyncio
import discord
import itertools
import io
import os
import string
import pprint
import statistics

from .deck import Deck
from collections import namedtuple


settings_path = "data/card/settings.json"
crdata_path = "data/card/clashroyale.json"
cardpop_path = "data/card/cardpop.json"
crtexts_path = "data/card/crtexts.json"
dates_path = "data/card/dates.json"

cardpop_range_min = 8
cardpop_range_max = 26

max_deck_show = 5

discord_ui_bgcolor = discord.Color(value=int('36393e', 16))


def take(n, iterable):
    """Return first n items of the iterable as a list."""
    return list(islice(iterable, n))


class Card:
    """Clash Royale Card Popularity snapshots."""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.crdata_path = crdata_path
        self.cardpop_path = cardpop_path
        self.crtexts_path = crtexts_path
        self.dates_path = dates_path

        self.settings = dataIO.load_json(self.file_path)
        self.crdata = dataIO.load_json(self.crdata_path)
        self.cardpop = dataIO.load_json(self.cardpop_path)
        self.crtexts = dataIO.load_json(self.crtexts_path)
        self.dates = dataIO.load_json(self.dates_path)

        # init card data
        self.cards = []
        self.cards_abbrev = {}

        for card_key, card_value in self.crdata["Cards"].items():
            self.cards.append(card_key)
            self.cards_abbrev[card_key] = card_key

            if card_key.find('-'):
                self.cards_abbrev[card_key.replace('-', '')] = card_key

            aka_list = card_value["aka"]
            for aka in aka_list:
                self.cards_abbrev[aka] = card_key
                if aka.find('-'):
                    self.cards_abbrev[aka.replace('-', '')] = card_key

        self.card_w = 302
        self.card_h = 363
        self.card_ratio = self.card_w / self.card_h
        self.card_thumb_scale = 0.5
        self.card_thumb_w = int(self.card_w * self.card_thumb_scale)
        self.card_thumb_h = int(self.card_h * self.card_thumb_scale)

        self.plotfigure = 0
        self.plot_lock = asyncio.Lock()

    @commands.command(pass_context=True)
    async def card(self, ctx, card=None):
        """Display statistics about a card.

        Example: !card miner
        """
        if card is None:
            await send_cmd_help(ctx)

        card = self.get_card_name(card)

        if card is None:
            await self.bot.say("Card name is not valid.")
            return

        data = discord.Embed(
            title=self.card_to_str(card),
            description=self.get_card_description(card),
            color=self.get_random_color())
        data.set_thumbnail(url=self.get_card_image_url(card))
        data.add_field(
            name="Elixir",
            value=self.crdata["Cards"][card]["elixir"])
        data.add_field(
            name="Rarity",
            value=string.capwords(self.crdata["Cards"][card]["rarity"]))

        # for id in range(cardpop_range_min, cardpop_range_max):
        #     data.add_field(
        #         name="Snapshot {}".format(id),
        #         value=self.get_cardpop(card, id))

        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

        # Display card trend of the card
        await ctx.invoke(Card.cardtrend, card)

        # Display top decks
        await ctx.invoke(Card.decks, card)

    @commands.command(pass_context=True)
    async def decks(self, ctx: Context, *cards):
        """Display top deck with specific card in particular snapshot.

        !decks Miner
        displays decks with miner in latest sn.

        !decks princess miner
        displays decks with both miner and pricness in latest snapshot.
        """
        if cards is None or not len(cards):
            await send_cmd_help(ctx)
            return

        # legacy param - will remove in future updates
        snapshot_id = None

        # check last param, if digit, assign as snapshot id
        if cards[-1].isdigit():
            snapshot_id = int(cards[-1])
            cards = cards[:-1]

        if snapshot_id is None:
            snapshot_id = str(cardpop_range_max - 1)

        is_most_recent_snapshot = int(snapshot_id) == cardpop_range_max - 1

        # await self.bot.say("{}: {}".format(snapshot_id, cards))

        card_names_are_valid = True
        for card in cards:
            if self.get_card_name(card) is None:
                await self.bot.say(
                    "**{}** is not valid card name.".format(card))
                card_names_are_valid = False
        if not card_names_are_valid:
            return

        # repopulate cards with normalized data
        cards = [self.get_card_name(c) for c in cards]
        # cpids = [self.get_card_cpid(c) for c in cards]

        found_decks = []
        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            for k in decks.keys():
                deck = decks[k]["deck"]
                if all(card in deck for card in cards):
                    found_decks.append(k)
                # if all(cpid in k for cpid in cpids):
                #     found_decks.append(k)

        await self.bot.say("Found {} decks with {} in Snapshot #{}{}.".format(
            len(found_decks),
            ', '.join([self.card_to_str(card) for card in cards]),
            snapshot_id,
            ' (most recent)' if is_most_recent_snapshot else ''))

        if len(found_decks):
            # await self.bot.say(
            #     "Listing top {} decks:".format(
            #         min([max_deck_show, len(found_decks)])))

            for i, deck in enumerate(found_decks):
                # Show top 5 deck images only
                # if i < max_deck_show:

                results_max = 3

                cards = deck.split(', ')
                norm_cards = [self.get_card_from_cpid(c) for c in cards]

                await self.bot.say("**{}**: {}/100: {}".format(
                    i + 1,
                    self.get_deckpop_count(deck, snapshot_id),
                    self.card_to_str(deck)))

                FakeMember = namedtuple("FakeMember", "name")
                m = FakeMember(name="Snapshot #{}".format(snapshot_id))

                await self.bot.get_cog("Deck").deck_get_helper(
                    ctx,
                    card1=norm_cards[0],
                    card2=norm_cards[1],
                    card3=norm_cards[2],
                    card4=norm_cards[3],
                    card5=norm_cards[4],
                    card6=norm_cards[5],
                    card7=norm_cards[6],
                    card8=norm_cards[7],
                    deck_name="Top Deck: {}".format(i + 1),
                    author=m)

                if (i + 1) % results_max == 0 and (i + 1) < len(found_decks):
                    def pagination_check(m):
                        return m.content.lower() == 'y'
                    await self.bot.say(
                        "Would you like to see more results? (y/n)")
                    answer = await self.bot.wait_for_message(
                        timeout=10.0,
                        author=ctx.message.author,
                        check=pagination_check)
                    if answer is None:
                        await self.bot.say("Search results aborted.")
                        return

    @commands.command(pass_context=True)
    async def cardimage(self, ctx, card=None):
        """Display the card image."""
        card = self.get_card_name(card)
        if card is None:
            await self.bot.say("Card name is not valid.")
            return

        data = discord.Embed(
            # url=self.get_card_image_url(card),
            color=discord_ui_bgcolor)
        data.set_image(url=self.get_card_image_url(card))

        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True, aliases=["cardtrends"])
    async def cardtrend(self, ctx: Context, *cards):
        """Display trends about a card based on popularity snapshot.

        Examples:
        !cardtrend miner
        !cardtrend princess log
        !cardtrend giant xbow 3m
        """
        if not len(cards):
            await send_cmd_help(ctx)
            return

        cards = list(set(cards))

        validated_cards = []

        for card in cards:
            c = card
            card = self.get_card_name(card)
            if card is None:
                await self.bot.say(
                    "**{}** is not a valid card name.".format(c))
            else:
                validated_cards.append(card)

        if len(validated_cards) == len(cards):

            facecolor = '#32363b'
            edgecolor = '#eeeeee'
            spinecolor = '#999999'
            footercolor = '#999999'
            labelcolor = '#cccccc'
            tickcolor = '#999999'
            titlecolor = '#ffffff'

            fig = plt.figure(
                num=1,
                figsize=(8, 6),
                dpi=192,
                facecolor=facecolor,
                edgecolor=edgecolor)
            plt.grid(b=True, alpha=0.3)

            ax = fig.add_subplot(111)

            ax.set_title('Clash Royale Card Trends', color=titlecolor)
            ax.set_xlabel('Snapshots')
            ax.set_ylabel('Usage')

            for spine in ax.spines.values():
                spine.set_edgecolor(spinecolor)

            ax.xaxis.label.set_color(labelcolor)
            ax.yaxis.label.set_color(labelcolor)
            ax.tick_params(axis='x', colors=tickcolor)
            ax.tick_params(axis='y', colors=tickcolor)

            # create labels using snapshot dates
            labels = []
            for id in range(cardpop_range_min, cardpop_range_max):
                dt = datetime.datetime.strptime(
                    self.dates[str(id)], '%Y-%m-%d')
                dtstr = dt.strftime('%b %d, %y')
                labels.append("{}\n   {}".format(id, dtstr))

            # process plot only when all the cards are valid
            for card in validated_cards:

                x = range(cardpop_range_min, cardpop_range_max)
                y = [int(self.get_cardpop_count(card, id)) for id in x]
                ax.plot(x, y, 'o-', label=self.card_to_str(card))
                plt.xticks(x, labels, rotation=70, fontsize=8, ha='right')

            # make tick label font size smaller
            # for tick in ax.xaxis.get_major_ticks():
            #     tick.label.set_fontsize(8)

            leg = ax.legend(facecolor=facecolor, edgecolor=spinecolor)
            for text in leg.get_texts():
                text.set_color(labelcolor)

            ax.annotate(
                'Compiled with data from Woody’s popularity snapshots',

                # The point that we'll place the text in relation to
                xy=(0, 0),
                # Interpret the x as axes coords, and the y as figure
                # coords
                xycoords=('figure fraction'),

                # The distance from the point that the text will be at
                xytext=(15, 10),
                # Interpret `xytext` as an offset in points...
                textcoords='offset points',

                # Any other text parameters we'd like
                size=8, ha='left', va='bottom', color=footercolor)

            plt.subplots_adjust(left=0.1, right=0.96, top=0.9, bottom=0.2)

            plot_filename = "{}-plot.png".format("-".join(cards))
            # plot_name = "Card Trends: {}".format(
            #     ", ".join([self.card_to_str(c) for c in validated_cards]))
            plot_name = ""

            with io.BytesIO() as f:
                plt.savefig(f, format="png", facecolor=facecolor,
                            edgecolor=edgecolor, transparent=True)
                f.seek(0)
                await ctx.bot.send_file(
                    ctx.message.channel, f,
                    filename=plot_filename,
                    content=plot_name)

            fig.clf()

        plt.clf()
        plt.cla()

    @commands.command(pass_context=True)
    async def elixirlist(self, ctx: Context):
        """Display average elixir over time."""
        trend = {}

        for snapshot_id, snapshot in self.cardpop.items():
            decks = snapshot["decks"]
            deck_count = 0
            elixir_all = 0
            for deck_id, deck_v in decks.items():
                deck_count += deck_v["count"]
                elixir_all += deck_v["count"] * deck_v["elixir"]
            trend[snapshot_id] = elixir_all / deck_count

        out = []
        for id in range(cardpop_range_min, cardpop_range_max):
            out.append(
                "Snapshot {:2}: {}"
                "".format(id, trend[str(id)]))

        await self.bot.say(
            "```python\n" +
            "\n".join(out) +
            "```")

    @commands.command(pass_context=True)
    async def elixirtrend(self, ctx: Context):
        """Plot elixir trend over time."""
        # sorted by snapshot id
        trend = {}
        # unsorted as list of dict
        trendall = []
        stats = []

        for snapshot_id, snapshot in self.cardpop.items():
            decks = snapshot["decks"]
            # deck_id = 0

            if snapshot_id not in trend:
                trend[snapshot_id] = []

            for deck_key, deck_v in decks.items():
                trend[snapshot_id].append({
                    "elixir": deck_v["elixir"],
                    "count": deck_v["count"]
                })
                trendall.append({
                    "id": snapshot_id,
                    "elixir": deck_v["elixir"],
                    "count": deck_v["count"]
                })

            # expand count to list for statistics
            trendstat = []
            for t in trend[snapshot_id]:
                trendstat.extend([t["elixir"]] * t["count"])
            stats.append({
                "id": snapshot_id,
                "trend": trendstat,
                "median": statistics.median(trendstat),
                "mean": statistics.mean(trendstat)
            })
            # print (str(trendstat))

        # Colors
        facecolor = '#32363b'
        edgecolor = '#333333'
        spinecolor = '#666666'
        footercolor = '#999999'
        labelcolor = '#cccccc'
        tickcolor = '#999999'
        titlecolor = '#ffffff'

        fig = plt.figure(
            num=1,
            figsize=(8, 6),
            dpi=192,
            facecolor=facecolor,
            edgecolor=edgecolor)
        # plt.grid(b=True, alpha=1)

        ax = fig.add_subplot(111)

        ax.set_title(
            'Clash Royale Decks: Average Elixir Trends', color=titlecolor)
        ax.set_xlabel('Snapshots')
        ax.set_ylabel('Elixir')

        for spine in ax.spines.values():
            spine.set_edgecolor(spinecolor)

        ax.xaxis.label.set_color(labelcolor)
        ax.yaxis.label.set_color(labelcolor)
        ax.tick_params(axis='x', colors=tickcolor)
        ax.tick_params(axis='y', colors=tickcolor)

        # create labels using snapshot dates
        labels = []
        # for id in range(cardpop_range_min, cardpop_range_max):
        for t in trendall:
            dt = datetime.datetime.strptime(
                self.dates[str(t["id"])], '%Y-%m-%d')
            dtstr = dt.strftime('%b %d, %y')
            labels.append("{}\n   {}".format(t["id"], dtstr))

        # cmap=plt.get_cmap(name)
        # scatter plot datapoints
        x = [int(t["id"]) for t in trendall]
        y = [t["elixir"] for t in trendall]
        area = [t["count"] * 2 for t in trendall]
        # ax.scatter(x, y, s=area, c="np.arange(100)", cmap="plasma")
        ax.scatter(x, y, s=area, c="yellow")
        plt.xticks(x, labels, rotation=70, fontsize=8, ha='right')

        # plot mean and median
        for p in ["mean", "median"]:
            x = [s["id"] for s in stats]
            y = [s[p] for s in stats]
            ax.plot(x, y, 'o-', label=string.capwords(p))

        leg = ax.legend(facecolor=facecolor, edgecolor=spinecolor)
        for text in leg.get_texts():
            text.set_color(labelcolor)

        ax.annotate(
            'Compiled with data from Woody’s popularity snapshots',
            xy=(0, 0),
            xycoords=('figure fraction'),
            xytext=(15, 10),
            textcoords='offset points',
            size=8, ha='left', va='bottom', color=footercolor)

        plt.subplots_adjust(left=0.1, right=0.96, top=0.9, bottom=0.2)

        plot_filename = "elixir-trend-plot.png"
        # plot_name = "Card Trends: {}".format(
        #     ", ".join([self.card_to_str(c) for c in validated_cards]))
        plot_name = ""

        with io.BytesIO() as f:
            plt.savefig(f, format="png", facecolor=facecolor,
                        edgecolor=edgecolor, transparent=True)
            f.seek(0)
            await ctx.bot.send_file(
                ctx.message.channel, f,
                filename=plot_filename,
                content=plot_name)

        fig.clf()
        plt.clf()
        plt.cla()


        # print(pprint.pformat(trend))

        # for page in pagify(pprint.pformat(trend["8"]), shorten_by=24):
        #     await self.bot.say(page)






    @commands.command(pass_context=True)
    async def popdata(self, ctx: Context,
        snapshot_id=str(cardpop_range_max - 1), limit=10):
        """Display raw data of the card popularity snapshot."""
        if not snapshot_id.isdigit():
            await self.bot.say("Please enter a number for the snapshot id.")
            return

        if not cardpop_range_min <= int(snapshot_id) < cardpop_range_max:
            await self.bot.say("Snapshot ID must be between {} and {}.".format(
                cardpop_range_min, cardpop_range_max - 1))
            return

        limit = int(limit)
        if limit <= 0:
            limit = 10000

        snapshot = self.cardpop[snapshot_id]
        cards = snapshot["cardpop"]
        decks = snapshot["decks"]

        dt = datetime.datetime.strptime(
            self.dates[str(snapshot_id)], '%Y-%m-%d')
        dtstr = dt.strftime('%b %d, %Y')

        await self.bot.say("**Woody’s Popularity Snapshot #{}** ({})".format(
            snapshot_id, dtstr))

        await self.bot.say("**Cards:**")
        out = []
        for card_key, card_value in take(limit, cards.items()):
            out.append("{:4d} ({:3d}) {}".format(
                card_value["count"],
                card_value["change"],
                self.card_to_str(card_key)))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(box(page, lang="py"))

        await self.bot.say("**Decks:**")
        out = []
        for deck_key, deck_value in take(limit, decks.items()):
            out.append("**{:4d}**: {}".format(
                deck_value["count"],
                self.card_to_str(deck_key)))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @commands.command(pass_content=True)
    async def popdataall(self, ctx: Context,
        snapshot_id=str(cardpop_range_max - 1)):
        """Display raw data of card popularity snapshot without limits."""
        pass

    def get_random_color(self):
        """Return a discord.Color instance of a random color."""
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        return discord.Color(value=color)

    def card_to_str(self, card=None):
        """Return name in title case."""
        if card is None:
            return None
        return string.capwords(card.replace('-', ' '))

    def get_card_name(self, card=None):
        """Return standard name used in data files."""
        if card is None:
            return None
        if card.lower() in self.cards_abbrev:
            return self.cards_abbrev[card.lower()]
        return None

    def get_card_description(self, card=None):
        """Return the description of a card."""
        if card is None:
            return ""
        tid = self.crdata["Cards"][card]["tid"]
        return self.crtexts[tid]

    def get_card_image_file(self, card=None):
        """Construct an image of the card."""
        if card is None:
            return None
        return "data/card/img/cards/{}.png".format(card)

    def get_card_image_url(self, card=None):
        """Return the card image url hosted by smlbiobot."""
        if card is None:
            return None
        return "https://smlbiobot.github.io/img/cards/{}.png".format(card)

    def get_cardpop_count(self, card=None, snapshot_id=None):
        """Return card popularity count by snapshot id."""
        out = 0
        snapshot_id = str(snapshot_id)
        if card is not None and snapshot_id is not None:
            if snapshot_id in self.cardpop:
                cardpop = self.cardpop[snapshot_id]["cardpop"]
                cpid = self.get_card_cpid(card)
                if cpid in cardpop:
                    out = cardpop[cpid]["count"]
        return out

    def get_cardpop(self, card=None, snapshot_id=None):
        """Return card popularity by snapshot id.

        Format: Count (Change)
        """
        out = "---"
        snapshot_id = str(snapshot_id)

        if card is not None and snapshot_id is not None:
            if snapshot_id in self.cardpop:
                cardpop = self.cardpop[snapshot_id]["cardpop"]
                cpid = self.get_card_cpid(card)
                if cpid in cardpop:
                    out = "**{}** ({})".format(
                        cardpop[cpid]["count"],
                        cardpop[cpid]["change"])
        return out

    def get_card_cpid(self, card=None):
        """Return the card populairty ID used in data."""
        # return self.crdata["Cards"][card]["cpid"]
        return card

    def get_card_from_cpid(self, cpid=None):
        """Return the card id from cpid."""
        # for k, v in self.crdata["Cards"].items():
        #     if cpid == v["cpid"]:
        #         return k
        # return None
        return cpid

    def get_deckpop_count(self, deck=None, snapshot_id=None):
        """Return the deck popularity by snapshot id."""
        out = 0
        snapshot_id = str(snapshot_id)
        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            if deck in decks:
                out = decks[deck]["count"]
        return out


def check_folder():
    """Check data folders exist. Create if they’re not."""
    folders = ["data/card",
               "data/card/img",
               "data/card/img/cards"]
    for f in folders:
        if not os.path.exists(f):
            print("Creating {} folder".format(f))
            os.makedirs(f)


def check_file():
    """Check settings file exists."""
    settings = {
        "Servers": {}
    }
    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default card settings.json...")
        dataIO.save_json(f, settings)


def setup(bot):
    """Add cog to bot."""
    check_folder()
    check_file()
    n = Card(bot)
    bot.add_cog(n)
