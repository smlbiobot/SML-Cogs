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



# from .deck import Deck
from .utils.dataIO import dataIO
from __main__ import send_cmd_help
from cogs.utils.chat_formatting import pagify, box
from collections import namedtuple
from discord.ext import commands
from discord.ext.commands import Context
from itertools import islice
from matplotlib import pyplot as plt
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from random import choice
import asyncio
import datetime
import discord
import io
import itertools
import os
import string

settings_path = "data/clashroyale/settings.json"
crdata_path = "data/clashroyale/clashroyale.json"
cardpop_path = "data/clashroyale/cardpop.json"
crtexts_path = "data/clashroyale/crtexts.json"
dates_path = "data/clashroyale/dates.json"

cardpop_range_min = 8
cardpop_range_max = 24

max_deck_show = 5
max_deck_per_user = 5

discord_ui_bgcolor = discord.Color(value=int('36393e', 16))

help_text = f"""
**ClashRoyale**
The !deck command helps you organize your Clash Royale decks.

**ClashRoyale image**
To get an image of the deck, type:
`!deck get 3M EB MM IG knight IS zap pump`

To optionally add a name to your deck, type:
`!deck get 3M EB MM IG knight IS zap pump "3M Ebarbs"`

**Card Names**
You can type the card names in full or use abbreviations. Common abbreviations have been added. For the full list of available cards and acceptable abbreviations, type `!deck cards`

**Database**
You can save your decks. To add a deck to your personal collection, type:
`!deck add 3M EB MM IG knight IS zap pump "3M Ebarbs"`
You can have up to {max_deck_per_user} decks in your personal collection.

**List**
To see the decks you have added, type `!deck list`
To see the decks that others have added, type `!deck list <username>`

**Rename**
To rename a deck, type `!deck rename [deck_id] [new_name]`
where deck_id is the number on your list, and new_name is the new name, obviously.
Remember to quote the name if you want it to contain spaces.

**Remove**
To remove a deck, type `ClashRoyale remove [deck_id]`
where deck_id is the number on your deck list.

**Search**
To search for decks containing specific card(s) in all saved decks, type
`!deck search [card] [card] [card]`
You can enter as many cards as you like. Or enter one.
Results are paginated and will show 3 at a time. Type Y to page through all results.

**Show**
To show a specifc deck by yourself or another user, type
`!deck show [deck_id] [user]`
where deck_id is the number on your deck list.
e.g. `!deck show 2` shows the second deck in your deck list.

"""


class ClashRoyale:
    """Clash Royale Deck Builder."""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.crdata_path = crdata_path

        self.settings = dataIO.load_json(self.file_path)
        self.crdata = dataIO.load_json(self.crdata_path)

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

        # deck validation hack
        self.deck_is_valid = False

    def grouper(self, n, iterable, fillvalue=None):
        """Helper function to split lists.

        Example:
        grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx
        """
        args = [iter(iterable)] * n
        return ([e for e in t if e is not None]
            for t in itertools.zip_longest(*args))


    @commands.group(pass_context=True, no_pm=True)
    async def deck(self, ctx):
        """Clash Royale deck builder.

        Example usage:
        !deck add 3m mm ig is fs pump horde knight "3M EBarbs"

        Card list
        !deck cards

        Full help
        !deck help
        """

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    async def deck_get_helper(self, ctx,
                              card1=None, card2=None, card3=None, card4=None,
                              card5=None, card6=None, card7=None, card8=None,
                              deck_name=None, author:discord.Member=None):
        """Abstract command to run deck_get for other modules."""
        await ctx.invoke(self.deck_get, card1, card2, card3, card4, card5,
                            card6, card7, card8, deck_name, author)

    @deck.command(name="get", pass_context=True, no_pm=True)
    async def deck_get(self, ctx,
                       card1=None, card2=None, card3=None, card4=None,
                       card5=None, card6=None, card7=None, card8=None,
                       deck_name=None, author:discord.Member=None):
        """Display a deck with cards.

        Enter 8 cards followed by a name.

        Example: !deck get bbd mm loon bt is fs gs lh

        For the full list of acceptable card names, type !deck cards
        """
        if deck_name is None:
            deck_name = 'ClashRoyale'
        if author is None:
            author = ctx.message.author

        member_deck = [card1, card2, card3, card4, card5, card6, card7, card8]
        if not all(member_deck):
            await self.bot.say("Please enter 8 cards.")
            await send_cmd_help(ctx)
        elif len(set(member_deck)) < len(member_deck):
            await self.bot.say("Please enter 8 unique cards.")
        else:
            await self.deck_upload(ctx, member_deck, deck_name, author)

    @deck.command(name="add", pass_context=True, no_pm=True)
    async def deck_add(self, ctx,
                        card1=None, card2=None, card3=None, card4=None,
                        card5=None, card6=None, card7=None, card8=None,
                        deck_name=None):
        """Add a deck to a personal decklist.

        Example: !deck add bbd mm loon bt is fs gs lh

        For the full list of acceptable card names, type !deck cards
        """
        if deck_name is None:
            deck_name = 'ClashRoyale'
        author = ctx.message.author
        server = ctx.message.server

        # convert arguments to deck list and name
        member_deck = [card1, card2, card3, card4, card5, card6, card7, card8]
        member_deck = self.normalize_deck_data(member_deck)

        if not all(member_deck):
            await self.bot.say("Please enter 8 cards.")
            await send_cmd_help(ctx)
        elif len(set(member_deck)) < len(member_deck):
            await self.bot.say("Please enter 8 unique cards.")
        else:

            await self.deck_upload(ctx, member_deck, deck_name)

            decks = self.settings["Servers"][server.id]["Members"][author.id]["ClashRoyales"]

            if self.deck_is_valid:

                # creates sets with decks.values
                # decks_sets = [set(d) for d in decks.values()]

                # if  set(member_deck) in decks_sets:
                #     # existing deck
                #     await self.bot.say("ClashRoyale exists already")
                # else:
                # new deck
                await self.bot.say("ClashRoyale added.")
                deck_key = str(datetime.datetime.utcnow())
                decks[deck_key] = {
                    "ClashRoyale": member_deck,
                    "ClashRoyaleName": deck_name
                }

                # If user has more than allowed by max, remove older decks
                timestamp = decks.keys()
                timestamp = sorted(timestamp)

                while len(decks) > max_deck_per_user:
                    t = timestamp.pop(0)
                    decks.pop(t, None)

                self.save_settings()


    @deck.command(name="list", pass_context=True, no_pm=True)
    async def deck_list(self, ctx, member:discord.Member=None):
        """List the decks of a user."""
        author = ctx.message.author
        server = ctx.message.server

        member_is_author = False

        if not member:
            member = author
            member_is_author = True

        self.check_server_settings(server)
        self.check_member_settings(server, member)

        decks = self.settings["Servers"][server.id]["Members"][member.id]["ClashRoyales"]

        deck_id = 1

        for k, deck in decks.items():
            await self.bot.say("**{}**. {}".format(deck_id, deck["ClashRoyaleName"]))
            await self.upload_deck_image(ctx, deck["ClashRoyale"], deck["ClashRoyaleName"], member)
            deck_id += 1

        if not len(decks):
            if member_is_author:
                await self.bot.say("You don’t have any decks stored.\n"
                                   "Type `!deck add` to add some.")
            else:
                await self.bot.say("{} hasn’t added any decks yet.".format(member.name))

    @deck.command(name="show", pass_context=True, no_pm=True)
    async def deck_show(self, ctx, deck_id=None, member:discord.Member=None):
        """Show the deck of a user by id."""
        author = ctx.message.author
        server = ctx.message.server
        if not member:
            member = author
        self.check_server_settings(server)
        members = self.settings["Servers"][server.id]["Members"]
        if not member.id in members:
            await self.bot.say("You have not added any decks.")
        elif deck_id is None:
            await self.bot.say("You must enter a deck id.")
        elif not deck_id.isdigit():
            await self.bot.say("The deck_id you have entered is not a number.")
        else:
            deck_id = int(deck_id) - 1
            decks = members[member.id]["ClashRoyales"]
            for i, deck in enumerate(decks.values()):
                if i == deck_id:
                    await self.deck_upload(ctx, deck["ClashRoyale"],
                                           deck["ClashRoyaleName"], member)

    @deck.command(name="cards", pass_context=True, no_pm=True)
    async def deck_cards(self, ctx):
        """Display all available cards and acceptable abbreviations."""
        out = []
        for card_key, card_value in self.crdata["Cards"].items():
            names = [card_key]
            name = string.capwords(card_key.replace('-', ' '))
            for abbrev in card_value["aka"]:
                names.append(abbrev)
            rarity = string.capwords(card_value["rarity"])
            elixir = card_value["elixir"]
            out.append(
                "**{}** ({}, {} elixir): {}".format(
                    name, rarity, elixir, ", ".join(names)))

        split_out = self.grouper(25, out)

        for o in split_out:
            await self.bot.say('\n'.join(o))

    @deck.command(name="search", pass_context=True, no_pm=True)
    async def deck_search(self, ctx, *params):
        """Search all decks by cards."""
        server = ctx.message.server
        server_members = self.settings["Servers"][server.id]["Members"]

        if not len(params):
            await self.bot.say("You must enter at least one card to search.")
        else:

            # normalize params
            params = self.normalize_deck_data(params)

            found_decks = []

            for k, server_member in server_members.items():
                member_decks = server_member["ClashRoyales"]
                member_id = server_member["MemberID"]
                member_display_name = server_member["MemberDisplayName"]
                member = server.get_member(member_id)
                for k, member_deck in member_decks.items():
                    cards = member_deck["ClashRoyale"]
                    # await self.bot.say(set(params))
                    if set(params) < set(cards):
                        found_decks.append({
                            "ClashRoyale": member_deck["ClashRoyale"],
                            "ClashRoyaleName": member_deck["ClashRoyaleName"],
                            "Member": member,
                            "MemberDisplayName": member_display_name })

            await self.bot.say("Found {} decks".format(len(found_decks)))

            if len(found_decks):

                results_max = 3

                deck_id = 1

                for deck in found_decks:
                    await self.bot.say(
                        "**{}. {}** by {}".format(
                            deck_id, deck["ClashRoyaleName"],
                            deck["MemberDisplayName"]))
                    await self.upload_deck_image(ctx, deck["ClashRoyale"], deck["ClashRoyaleName"], deck["Member"])

                    deck_id += 1

                    if (deck_id - 1) % results_max == 0:
                        if deck_id < len(found_decks):

                            def pagination_check(m):
                                return m.content.lower() == 'y'

                            await self.bot.say("Would you like to see the next results? (Y/N)")

                            answer = await self.bot.wait_for_message(
                                timeout=10.0,
                                author=ctx.message.author,
                                check=pagination_check)

                            if answer is None:
                                await self.bot.say("Search results aborted.")
                                return



    @deck.command(name="rename", pass_context=True, no_pm=True)
    async def deck_rename(self, ctx, deck_id, new_name):
        """Rename a deck based on deck id.

        Syntax: !deck rename [deck_id] [new_name]
        where deck_id is the number associated with the deck when you run !deck list
        """
        server = ctx.message.server
        author = ctx.message.author

        members = self.settings["Servers"][server.id]["Members"]

        # check member has data
        if author.id not in members:
            self.bot.say("You have not added any decks.")
        elif not deck_id.isdigit():
            await self.bot.say("The deck_id you have entered is not a number.")
        else:
            deck_id = int(deck_id) - 1
            member = members[author.id]
            decks = member["ClashRoyales"]
            if deck_id >= len(decks):
                await self.bot.say("The deck id you have entered is invalid.")
            else:
                for i, deck in enumerate(decks.values()):
                    if deck_id == i:
                        # await self.bot.say(deck["ClashRoyaleName"])
                        deck["ClashRoyaleName"] = new_name
                        await self.bot.say("ClashRoyale renamed to {}.".format(new_name))
                        await self.deck_upload(ctx, deck["ClashRoyale"], new_name, author)
                        self.save_settings()

    @deck.command(name="remove", pass_context=True, no_pm=True)
    async def deck_remove(self, ctx, deck_id):
        """Remove a deck by deck id."""
        server = ctx.message.server
        author = ctx.message.author

        members = self.settings["Servers"][server.id]["Members"]

        if not author.id in members:
            await self.bot.say("You have not added any decks.")
        elif not deck_id.isdigit():
            await self.bot.say("The deck_id you have entered is not a number.")
        else:
            deck_id = int(deck_id) - 1
            member = members[author.id]
            decks = member["ClashRoyales"]
            if deck_id >= len(decks):
                await self.bot.say("The deck id you have entered is invalid.")
            else:
                remove_key = ""
                for i, key in enumerate(decks.keys()):
                    if deck_id == i:
                        remove_key = key
                decks.pop(remove_key)
                await self.bot.say("ClashRoyale {} removed.".format(deck_id + 1))
                self.save_settings()

    @deck.command(name="help", pass_context=True, no_pm=True)
    async def deck_help(self, ctx):
        """Complete help and tutorial."""
        await self.bot.say(help_text)


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
    async def decks(self, ctx:Context, *cards):
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
        cpids = [self.get_card_cpid(c) for c in cards]

        found_decks = []
        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            for k in decks.keys():
                if all(cpid in k for cpid in cpids):
                    found_decks.append(k)

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
                    deck))

                FakeMember = namedtuple("FakeMember", "name")
                m = FakeMember(name="Snapshot #{}".format(snapshot_id))

                # await self.bot.get_cog("Deck").deck_get_helper(ctx,
                #     card1=norm_cards[0],
                #     card2=norm_cards[1],
                #     card3=norm_cards[2],
                #     card4=norm_cards[3],
                #     card5=norm_cards[4],
                #     card6=norm_cards[5],
                #     card7=norm_cards[6],
                #     card8=norm_cards[7],
                #     deck_name="Top Deck: {}".format(i + 1),
                #     author=m)

                await self.deck_get(
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
    async def popdata(self, ctx: Context,
        snapshot_id=str(cardpop_range_max - 1), limit=10):
        """Display raw data of the card popularity snapshot."""
        if not snapshot_id.isdigit():
            await self.bot.say("Please enter a number for the snapshot id.")
            return

        if not cardpop_range_min <= int(snapshot_id) < cardpop_range_max:
            await self.bot.say("Snapshot ID must be between {} and {}.".format(
                cardpop_range_min, cardpop_range_max))
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
                card_key))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(box(page, lang="py"))

        await self.bot.say("**Decks:**")
        out = []
        for deck_key, deck_value in take(limit, decks.items()):
            out.append("**{:4d}**: {}".format(
                deck_value["count"],
                deck_key))
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
        return self.crdata["Cards"][card]["cpid"]

    def get_card_from_cpid(self, cpid=None):
        """Return the card id from cpid."""
        for k, v in self.crdata["Cards"].items():
            if cpid == v["cpid"]:
                return k
        return None

    def get_deckpop_count(self, deck=None, snapshot_id=None):
        """Return the deck popularity by snapshot id."""
        out = 0
        snapshot_id = str(snapshot_id)
        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            if deck in decks:
                out = decks[deck]["count"]
        return out


    async def deck_upload(self, ctx, member_deck, deck_name:str, member=None):
        """Upload deck to Discord.

        Example: !deck set archers arrows baby-dragon balloon barbarian-hut barbarians battle-ram bomb-tower
        """

        author = ctx.message.author
        server = ctx.message.server

        if member is None:
            member = author

        self.check_server_settings(server)
        self.check_member_settings(server, author)

        member_deck = self.normalize_deck_data(member_deck)

        deck_is_valid = True

        # Ensure: exactly 8 cards are entered
        if len(member_deck) != 8:
            await self.bot.say(
                "You have entered {} card{}. "
                "Please enter exactly 8 cards.".format(
                    len(member_deck),
                    's' if len(member_deck) > 1 else ''))
            await send_cmd_help(ctx)
            deck_is_valid = False

        # Ensure: card names are valid
        if not set(member_deck) < set(self.cards):
            for card in member_deck:
                if not card in self.cards:
                    await self.bot.say("**{}** is not a valid card name.".format(card))
            await self.bot.say("\nType `!deck cards` for the full list")
            await send_cmd_help(ctx)
            deck_is_valid = False

        if deck_is_valid:
            await self.upload_deck_image(ctx, member_deck, deck_name, member)

        self.deck_is_valid = deck_is_valid

    async def upload_deck_image(self, ctx, deck, deck_name, author):
        """Upload deck image to the server."""

        deck_image = self.get_deck_image(deck, deck_name, author)

        # construct a filename using first three letters of each card
        filename = "deck-{}.png".format("-".join([card[:3] for card in deck]))

        # Take out hyphnens and capitlize the name of each card
        # card_names = [string.capwords(c.replace('-', ' ')) for c in deck]

        # description = "ClashRoyale: {}".format(', '.join(card_names))
        description = ""

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            await ctx.bot.send_file(ctx.message.channel, f,
                filename=filename, content=description)

    def get_deck_image(self, deck, deck_name=None, deck_author=None):
        """Construct the deck with Pillow and return image."""

        card_w = 302
        card_h = 363
        card_x = 30
        card_y = 30
        font_size = 50
        txt_y_line1 = 430
        txt_y_line2 = 500
        txt_x_name = 50
        txt_x_cards = 503
        txt_x_elixir = 1872

        bg_image = Image.open("data/clashroyale/img/deck-bg-b.png")
        size = bg_image.size

        font_file_regular = "data/clashroyale/fonts/OpenSans-Regular.ttf"
        font_file_bold = "data/clashroyale/fonts/OpenSans-Bold.ttf"

        image = Image.new("RGBA", size)
        image.paste(bg_image)

        if not deck_name:
            deck_name = "ClashRoyale"

        # cards
        for i, card in enumerate(deck):
            card_image_file = "data/clashroyale/img/cards/{}.png".format(card)
            card_image = Image.open(card_image_file)
            # size = (card_w, card_h)
            # card_image.thumbnail(size)
            box = (card_x + card_w * i,
                   card_y,
                   card_x + card_w * (i+1),
                   card_h + card_y)
            image.paste(card_image, box, card_image)

        # elixir
        total_elixir = 0
        for card_key, card_value in self.crdata["Cards"].items():
            if card_key in deck:
                total_elixir += card_value["elixir"]
        average_elixir = "{:.3f}".format(total_elixir / 8)

        # text
        # Take out hyphnens and capitlize the name of each card
        card_names = [string.capwords(c.replace('-', ' ')) for c in deck]

        txt = Image.new("RGBA", size)
        txt_name = Image.new("RGBA", (txt_x_cards-30, size[1]))
        font_regular = ImageFont.truetype(font_file_regular, size=font_size)
        font_bold = ImageFont.truetype(font_file_bold, size=font_size)

        d = ImageDraw.Draw(txt)
        d_name = ImageDraw.Draw(txt_name)

        line1 = ', '.join(card_names[:4])
        line2 = ', '.join(card_names[4:])
        # card_text = '\n'.join([line0, line1])

        deck_author_name = deck_author.name if deck_author else ""

        d_name.text((txt_x_name, txt_y_line1), deck_name, font=font_bold,
                         fill=(0xff, 0xff, 0xff, 255))
        d_name.text((txt_x_name, txt_y_line2), deck_author_name, font=font_regular,
                         fill=(0xff, 0xff, 0xff, 255))
        d.text((txt_x_cards, txt_y_line1), line1, font=font_regular,
                         fill=(0xff, 0xff, 0xff, 255))
        d.text((txt_x_cards, txt_y_line2), line2, font=font_regular,
                         fill=(0xff, 0xff, 0xff, 255))
        d.text((txt_x_elixir, txt_y_line1), "Avg elixir", font=font_bold,
               fill=(0xff, 0xff, 0xff, 200))
        d.text((txt_x_elixir, txt_y_line2), average_elixir, font=font_bold,
               fill=(0xff, 0xff, 0xff, 255))

        image.paste(txt, (0,0), txt)
        image.paste(txt_name, (0,0), txt_name)

        # scale down and return
        scale = 0.5
        scaled_size = tuple([x * scale for x in image.size])
        image.thumbnail(scaled_size)

        return image


    def normalize_deck_data(self, deck):
        """Return a deck list with normalized names."""
        deck = [c.lower() if c is not None else '' for c in deck]

        # replace abbreviations
        for i, card in enumerate(deck):
            if card in self.cards_abbrev.keys():
                deck[i] = self.cards_abbrev[card]

        return deck

    def check_member_settings(self, server, member):
        """Init member section if necessary."""
        if member.id not in self.settings["Servers"][server.id]["Members"]:
            self.settings["Servers"][server.id]["Members"][member.id] = {
                "MemberID": member.id,
                "MemberDisplayName": member.display_name,
                "ClashRoyales": {}}
            self.save_settings()

    def check_server_settings(self, server):
        """Init server data if necessary."""
        if server.id not in self.settings["Servers"]:
            self.settings["Servers"][server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "Members": {} }
            self.save_settings()

    def save_settings(self):
        """Saves data to settings file."""
        dataIO.save_json(self.file_path, self.settings)


def check_folder():
    folders = ["data/clashroyale",
               "data/clashroyale/img",
               "data/clashroyale/img/cards"]
    for f in folders:
        if not os.path.exists(f):
            print("Creating {} folder".format(f))
            os.makedirs(f)

def check_file():
    settings = {
        "Servers": {}
    }
    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default deck settings.json...")
        dataIO.save_json(f, settings)

def setup(bot):
    check_folder()
    check_file()
    n = ClashRoyale(bot)
    bot.add_cog(n)

