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
from .utils.dataIO import dataIO
from __main__ import send_cmd_help
import os
import datetime
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import io
import string
from cogs.utils.chat_formatting import pagify
import requests #for card id

cardinfo_url = 'https://raw.githubusercontent.com/smlbiobot/cr-api-data/master/dst/cards.json'
deckurl = 'https://link.clashroyale.com/deck/en?deck='
settings_path = os.path.join("data", "deck", "settings.json")
crdata_path = os.path.join("data", "deck", "clashroyale.json")
max_deck_per_user = 5

PAGINATION_TIMEOUT = 20.0
HELP_URL = "https://github.com/smlbiobot/SML-Cogs/wiki/Deck#usage"

numbs = {
    "next": "➡",
    "back": "⬅",
    "exit": "❌"
}


class Deck:
    """Clash Royale Deck Builder."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.file_path = settings_path
        self.crdata_path = crdata_path

        self.settings = dataIO.load_json(self.file_path)
        self.cardinfo = requests.get(cardinfo_url).json()
        self.name_to_id = {}
        for card in self.cardinfo:
            self.name_to_id[card['key']] = card['decklink']
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

        # deck validation hack
        self.deck_is_valid = False

        # pagination tracking
        self.track_pagination = None

    def copylink(self, cards): 
        """converts list of cards into ids,
        compiles list of ids into url
        """
        print(self.cards_abbrev)
        print(self.cards)
        cards = list(map(lambda x: self.cards_abbrev[x], cards))
        cardids = list(map(lambda x: self.name_to_id[x], cards))
        url = deckurl + ';'.join(cardids)
        return url


    @commands.group(pass_context=True, no_pm=True)
    async def deck(self, ctx):
        """Clash Royale deck builder.

        Example usage:
        !deck add 3m mm ig is fs pump horde eb "3M EBarbs"

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

        Example: !deck get bbd mm loon bt is fs gs lh "Lava Loon"

        For the full list of acceptable card names, type !deck cards
        """
        if deck_name is None:
            deck_name = 'Deck'
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

        Example: !deck add bbd mm loon bt is fs gs lh "Lava Loon"

        For the full list of acceptable card names, type !deck cards
        """
        if deck_name is None:
            deck_name = 'Deck'
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

            decks = self.settings["Servers"][server.id]["Members"][author.id]["Decks"]

            if self.deck_is_valid:

                # creates sets with decks.values
                # decks_sets = [set(d) for d in decks.values()]

                # if  set(member_deck) in decks_sets:
                #     # existing deck
                #     await self.bot.say("Deck exists already")
                # else:
                # new deck
                await self.bot.say("Deck added.")
                deck_key = str(datetime.datetime.utcnow())
                decks[deck_key] = {
                    "Deck": member_deck,
                    "DeckName": deck_name
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

        decks = self.settings["Servers"][server.id]["Members"][member.id]["Decks"]

        deck_id = 1

        for k, deck in decks.items():
            await self.upload_deck_image(
                ctx, deck["Deck"], deck["DeckName"], member,
                description="**{}**. {}\nCopy Deck{}".format(deck_id, deck["DeckName"], self.copylink(deck["Deck"])))
            deck_id += 1

        if not len(decks):
            if member_is_author:
                await self.bot.say("You don’t have any decks stored.\n"
                                   "Type `!deck add` to add some.")
            else:
                await self.bot.say("{} hasn’t added any decks yet.".format(member.name))

    @deck.command(name="longlist", pass_context=True, no_pm=True)
    async def deck_longlist(self, ctx, member:discord.Member=None):
        """List the decks of a user."""
        author = ctx.message.author
        server = ctx.message.server

        member_is_author = False

        if not member:
            member = author
            member_is_author = True

        self.check_server_settings(server)
        self.check_member_settings(server, member)

        decks = self.settings["Servers"][server.id]["Members"][member.id]["Decks"]

        if not len(decks):
            if member_is_author:
                await self.bot.say("You don’t have any decks stored.\n"
                                   "Type `!deck add` to add some.")
            else:
                await self.bot.say("{} hasn’t added any decks yet.".format(member.name))
            return

        deck_id = 1
        results_max = 3
        for k, deck in decks.items():
            await self.upload_deck_image(
                ctx, deck["Deck"], deck["DeckName"], member,
                description="**{}**. {}".format(deck_id, deck["DeckName"]))
            deck_id += 1

            if (deck_id - 1) % results_max == 0:
                if deck_id < len(decks):
                    def pagination_check(m):
                        return m.content.lower() == 'y'
                    await self.bot.say(
                        'Would you like to see the next results? (y/n)')
                    answer = await self.bot.wait_for_message(
                        timeout=PAGINATION_TIMEOUT,
                        author=ctx.message.author,
                        check=pagination_check)
                    if answer is None:
                        await self.bot.say("Results aborted.")
                        return

    @deck.command(name="pagelist", pass_context=True, no_pm=True)
    async def deck_pagelist(self, ctx, member: discord.Member=None):
        """List decks of a user with pagination."""
        author = ctx.message.author
        server = ctx.message.server
        member_is_author = False
        if not member:
            member = author
            member_is_author = True
        self.check_server_settings(server)
        self.check_member_settings(server, member)
        decks = self.settings["Servers"][server.id]["Members"][member.id]["Decks"]
        if not len(decks):
            if member_is_author:
                await self.bot.say("You don’t have any decks stored.\n"
                                   "Type `!deck add` to add some.")
            else:
                await self.bot.say("{} hasn’t added any decks yet.".format(member.name))
            return
        await self.deck_pagelist_menu(
            ctx, decks, member, message=None, page=0, timeout=30)

    async def deck_pagelist_menu(
            self, ctx, decks, member: discord.Member,
            message: discord.Message=None,
            page=0, timeout: int=30):
        """Menu control logic for this taken from
        https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py
        """
        if isinstance(decks, dict):
            decks = [v for k, v in decks.items()]
        deck = decks[page]
        description = "**{}**. {}".format(page + 1, deck["DeckName"])
        if not message:
            message =\
                await self.upload_deck_image(
                    ctx, deck["Deck"], deck["DeckName"], member, description)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message)
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
            if page == len(decks) - 1:
                next_page = 0
            else:
                next_page = page + 1
            return await self.deck_pagelist_menu(
                ctx, decks, member, message=message,
                page=next_page, timeout=timeout)
        else:
            try:
                return await self.bot.delete_message(message)
            except:
                pass

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
            decks = members[member.id]["Decks"]
            for i, deck in enumerate(decks.values()):
                if i == deck_id:
                    await self.deck_upload(ctx, deck["Deck"],
                            deck["DeckName"], member)

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

        for page in pagify("\n".join(out), shorten_by=24):
            await self.bot.say(page)

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
                member_decks = server_member["Decks"]
                member_id = server_member["MemberID"]
                member_display_name = server_member["MemberDisplayName"]
                member = server.get_member(member_id)
                for k, member_deck in member_decks.items():
                    cards = member_deck["Deck"]
                    # await self.bot.say(set(params))
                    if set(params) < set(cards):
                        found_decks.append({
                            "UTC": k,
                            "Deck": member_deck["Deck"],
                            "DeckName": member_deck["DeckName"],
                            "Member": member,
                            "MemberDisplayName": member_display_name})
            found_decks = sorted(
                found_decks, key=lambda x: x["UTC"], reverse=True)

            await self.bot.say("Found {} decks".format(len(found_decks)))

            if len(found_decks):

                results_max = 3

                deck_id = 1

                for deck in found_decks:
                    timestamp = deck["UTC"][:19]

                    description = "**{}. {}** by {} — {}".format(
                        deck_id, deck["DeckName"],
                        deck["MemberDisplayName"],
                        timestamp)
                    await self.upload_deck_image(
                        ctx, deck["Deck"], deck["DeckName"], deck["Member"],
                        description=description)

                    deck_id += 1

                    if (deck_id - 1) % results_max == 0:
                        if deck_id < len(found_decks):

                            def pagination_check(m):
                                return m.content.lower() == 'y'

                            await self.bot.say(
                                "Would you like to see the next results? (Y/N)")

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
            decks = member["Decks"]
            if deck_id >= len(decks):
                await self.bot.say("The deck id you have entered is invalid.")
            else:
                for i, deck in enumerate(decks.values()):
                    if deck_id == i:
                        # await self.bot.say(deck["DeckName"])
                        deck["DeckName"] = new_name
                        await self.bot.say("Deck renamed to {}.".format(new_name))
                        await self.deck_upload(ctx, deck["Deck"], new_name, author)
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
            decks = member["Decks"]
            if deck_id >= len(decks):
                await self.bot.say("The deck id you have entered is invalid.")
            else:
                remove_key = ""
                for i, key in enumerate(decks.keys()):
                    if deck_id == i:
                        remove_key = key
                decks.pop(remove_key)
                await self.bot.say("Deck {} removed.".format(deck_id + 1))
                self.save_settings()

    @deck.command(name="help", pass_context=True, no_pm=True)
    async def deck_help(self, ctx):
        """Complete help and tutorial."""
        await self.bot.say(
            "Please visit {} for an illustrated guide.".format(HELP_URL))

    async def deck_upload(self, ctx, member_deck, deck_name:str, member=None):
        """Upload deck to Discord."""
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

    async def upload_deck_image(self, ctx, deck, deck_name, author, description=""):
        """Upload deck image to the server."""

        deck_image = self.get_deck_image(deck, deck_name, author)

        # construct a filename using first three letters of each card
        filename = "deck-{}.png".format("-".join([card[:3] for card in deck]))

        # Take out hyphnens and capitlize the name of each card
        # card_names = [string.capwords(c.replace('-', ' ')) for c in deck]

        # description = "Deck: {}".format(', '.join(card_names))
        message = None

        with io.BytesIO() as f:
            deck_image.save(f, "PNG")
            f.seek(0)
            message = await ctx.bot.send_file(
                ctx.message.channel, f,
                filename=filename, content="{}\nCopy deck: {}".format(description, self.copylink(deck)))

        return message

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

        bg_image = Image.open("data/deck/img/deck-bg-b.png")
        size = bg_image.size

        font_file_regular = "data/deck/fonts/OpenSans-Regular.ttf"
        font_file_bold = "data/deck/fonts/OpenSans-Bold.ttf"

        image = Image.new("RGBA", size)
        image.paste(bg_image)

        if not deck_name:
            deck_name = "Deck"

        # cards
        for i, card in enumerate(deck):
            card_image_file = "data/deck/img/cards/{}.png".format(card)
            card_image = Image.open(card_image_file)
            # size = (card_w, card_h)
            # card_image.thumbnail(size)
            box = (card_x + card_w * i,
                   card_y,
                   card_x + card_w * (i + 1),
                   card_h + card_y)
            image.paste(card_image, box, card_image)

        # elixir
        total_elixir = 0
        # total card exclude mirror (0-elixir cards)
        card_count = 0
        for card_key, card_value in self.crdata["Cards"].items():
            if card_key in deck:
                total_elixir += card_value["elixir"]
                if card_value["elixir"]:
                    card_count += 1
        average_elixir = "{:.3f}".format(total_elixir / card_count)

        # text
        # Take out hyphnens and capitlize the name of each card
        card_names = [string.capwords(c.replace('-', ' ')) for c in deck]

        txt = Image.new("RGBA", size)
        txt_name = Image.new("RGBA", (txt_x_cards - 30, size[1]))
        font_regular = ImageFont.truetype(font_file_regular, size=font_size)
        font_bold = ImageFont.truetype(font_file_bold, size=font_size)

        d = ImageDraw.Draw(txt)
        d_name = ImageDraw.Draw(txt_name)

        line1 = ', '.join(card_names[:4])
        line2 = ', '.join(card_names[4:])
        # card_text = '\n'.join([line0, line1])

        deck_author_name = deck_author.name if deck_author else ""

        d_name.text(
            (txt_x_name, txt_y_line1), deck_name, font=font_bold,
            fill=(0xff, 0xff, 0xff, 255))
        d_name.text(
            (txt_x_name, txt_y_line2), deck_author_name, font=font_regular,
            fill=(0xff, 0xff, 0xff, 255))
        d.text(
            (txt_x_cards, txt_y_line1), line1, font=font_regular,
            fill=(0xff, 0xff, 0xff, 255))
        d.text(
            (txt_x_cards, txt_y_line2), line2, font=font_regular,
            fill=(0xff, 0xff, 0xff, 255))
        d.text(
            (txt_x_elixir, txt_y_line1), "Avg elixir", font=font_bold,
            fill=(0xff, 0xff, 0xff, 200))
        d.text(
            (txt_x_elixir, txt_y_line2), average_elixir, font=font_bold,
            fill=(0xff, 0xff, 0xff, 255))

        image.paste(txt, (0, 0), txt)
        image.paste(txt_name, (0, 0), txt_name)

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
                "Decks": {}}
            self.save_settings()

    def check_server_settings(self, server):
        """Init server data if necessary."""
        if server.id not in self.settings["Servers"]:
            self.settings["Servers"][server.id] = {
                "ServerName": str(server),
                "ServerID": str(server.id),
                "Members": {}}
            self.save_settings()

    def save_settings(self):
        """Save data to settings file."""
        dataIO.save_json(self.file_path, self.settings)


def check_folder():
    """Verify folders exist."""
    folders = [
        os.path.join("data", "deck"),
        os.path.join("data", "deck", "img"),
        os.path.join("data", "deck", "img", "cards")]
    for f in folders:
        if not os.path.exists(f):
            print("Creating {} folder".format(f))
            os.makedirs(f)

def check_file():
    """Verify data is valid."""
    settings = {
        "Servers": {}
    }
    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default deck settings.json...")
        dataIO.save_json(f, settings)

def setup(bot):
    """Add cog to Red."""
    check_folder()
    check_file()
    n = Deck(bot)
    bot.add_cog(n)
