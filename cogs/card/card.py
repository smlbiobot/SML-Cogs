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

from .utils.dataIO import dataIO
from __main__ import send_cmd_help
from asyncio_extras import threadpool
from discord.ext import commands
from discord.ext.commands import Context
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from random import choice
import asyncio
import discord
import itertools
# import matplotlib
# matplotlib.use('Agg')
import io
import matplotlib.pyplot as plt
import os
import string

"""
buf = BytesIO()
                plt.savefig(buf, format="png")

                # Don't send 0-byte files
                buf.seek(0)
                """

settings_path = "data/card/settings.json"
crdata_path = "data/card/clashroyale.json"
cardpop_path = "data/card/cardpop.json"
crtexts_path = "data/card/crtexts.json"

cardpop_range_min = 8
cardpop_range_max = 24

discord_ui_bgcolor = discord.Color(value=int('36393e', 16))

def grouper(self, n, iterable, fillvalue=None):
    """
    Helper function to split lists

    Example:
    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx
    """
    args = [iter(iterable)] * n
    return ([e for e in t if e != None] for t in itertools.zip_longest(*args))


class Card:
    """
    Clash Royale Card Popularity snapshot util
    """

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.crdata_path = crdata_path
        self.cardpop_path = cardpop_path
        self.crtexts_path = crtexts_path

        self.settings = dataIO.load_json(self.file_path)
        self.crdata = dataIO.load_json(self.crdata_path)
        self.cardpop = dataIO.load_json(self.cardpop_path)
        self.crtexts = dataIO.load_json(self.crtexts_path)

        # init card data
        self.cards = []
        self.cards_abbrev = {}

        for card_key, card_value in self.crdata["Cards"].items():
            self.cards.append(card_key)

            aka_list = card_value["aka"]
            for aka in aka_list:
                self.cards_abbrev[aka] = card_key


        self.card_w = 302
        self.card_h = 363
        self.card_ratio = self.card_w / self.card_h
        self.card_thumb_scale = 0.5
        self.card_thumb_w = int(self.card_w * self.card_thumb_scale)
        self.card_thumb_h = int(self.card_h * self.card_thumb_scale)

        self.plotfigure = 0
        self.plot_lock = asyncio.Lock()


    # @commands.group(pass_context=True)
    # async def card(self, ctx):
    #     """
    #     Clash Royale Decks
    #     """
    #     if ctx.invoked_subcommand is None:
    #         await send_cmd_help(ctx)

    @commands.command(pass_context=True)
    async def card(self, ctx, card=None):
        """
        Display statistics about a card
        Example: !card get miner
        """
        if card is None:
            await send_cmd_help(ctx)

        card = self.get_card_name(card)

        if card is None:
            await self.bot.say("Card name is not valid.")
            return


        data = discord.Embed(
            title = self.card_to_str(card),
            description = self.get_card_description(card),
            color = self.get_random_color())
        data.set_thumbnail(url=self.get_card_image_url(card))
        data.add_field(
            name="Elixir",
            value=self.crdata["Cards"][card]["elixir"])
        data.add_field(
            name="Rarity",
            value=string.capwords(self.crdata["Cards"][card]["rarity"]))

        for id in range(cardpop_range_min, cardpop_range_max):
            data.add_field(
                name="Snapshot {}".format(id),
                value=self.get_cardpop(card, id))

        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True)
    async def decks(self, ctx, card=None, snapshot_id=None):
        """
        Display decks which uses a particular card in a specific snapshot
        Syntax: !card decks Miner 23
        """
        if card is None:
            await send_cmd_help(ctx)
            return

        if snapshot_id is None:
            snapshot_id = str(cardpop_range_max - 1)

        card = self.get_card_name(card)  
        if card is None:
            await self.bot.say("Card name is not valid.")
            return

        cpid = self.get_card_cpid(card)

        found_decks = []


        if snapshot_id in self.cardpop:
            decks = self.cardpop[snapshot_id]["decks"]
            for k in decks.keys():
                if cpid in k:
                    found_decks.append(k)

        norm_found_decks = []

        for deck in found_decks:
            cards = deck.split(', ')
            norm_cards = [self.get_card_from_cpid(c) for c in cards]
            print(cards)
            print(norm_cards)
            norm_found_decks.append(', '.join(norm_cards))



        if len(norm_found_decks):
            await self.bot.say("\n".join(norm_found_decks))

    @commands.command(pass_context=True)
    async def cardimage(self, ctx, card=None):
        """Display the card image"""

        card = self.get_card_name(card)  
        if card is None:
            await self.bot.say("Card name is not valid.")
            return

        data = discord.Embed(
            # url=self.get_card_image_url(card),
            color = discord_ui_bgcolor)
        data.set_image(url=self.get_card_image_url(card))
       
        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True)
    async def cardtrend(self, ctx:Context, card=None):
        """
        Display trends about a card based on popularity snapshot
        Example: !cardtrend miner
        """
        if card is None:
            await send_cmd_help(ctx)

        card = self.get_card_name(card)

        if card is None:
            await self.bot.say("Card name is not valid.")
            return

        x = range(cardpop_range_min, cardpop_range_max)
        y = [int(self.get_cardpop_count(card, id)) for id in x]
        plt.plot(x, y)

        with io.BytesIO() as f:
            plt.savefig(f, format="png")
            f.seek(0)
            await ctx.bot.send_file(
                ctx.message.channel, f,
                filename="plot.png",
                content="{}-plot".format(card))

            plt.clf()
            plt.cla()

    def get_random_color(self):
        """
        Return a discord.Color instance of a random color
        """
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        return discord.Color(value=color)

      

    def card_to_str(self, card=None):
        """
        Return name in title case
        """
        if card is None:
            return None
        return string.capwords(card.replace('-', ' '))


    def get_card_name(self, card=None):
        """
        Replace abbreviations of card names and return standard name used in data files
        """
        if card is None:
            return None
        card = card.lower()
        if card in self.cards_abbrev.keys():
            card = self.cards_abbrev[card]
        return card

    def get_card_description(self, card=None):
        """
        Return the description of a card
        """
        if card is None:
            return ""
        tid = self.crdata["Cards"][card]["tid"]
        return self.crtexts[tid]

    def get_card_image_file(self, card=None):
        """
        Construct an image of the card
        """
        if card is None:
            return None
        return "data/card/img/cards/{}.png".format(card) 

    def get_card_image_url(self, card=None):
        """
        Return the card image url hosted by smlbiobot
        """
        if card is None:
            return None
        return "https://smlbiobot.github.io/img/cards/{}.png".format(card)

    def get_cardpop_count(self, card=None, snapshot_id=None):
        """
        Return card popularity count by snapshot id
        """
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
        """
        Return card popularity by snapshot id
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
        """
        Return the card populairty ID used in data
        """
        return self.crdata["Cards"][card]["cpid"]

    def get_card_from_cpid(self, cpid=None):
        """
        Return the card id from cpid
        """
        for k, v in self.crdata["Cards"].items():
            if cpid == v["cpid"]:
                return k
        return None


    def get_deck_image(self, deck, deck_name=None, deck_author=None):
        """Construct the deck with Pillow and return image"""

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




def check_folder():
    folders = ["data/card",
               "data/card/img",
               "data/card/img/cards"]
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
        print("Creating default card settings.json...")
        dataIO.save_json(f, settings)

def setup(bot):
    check_folder()
    check_file()
    n = Card(bot)
    bot.add_cog(n)

