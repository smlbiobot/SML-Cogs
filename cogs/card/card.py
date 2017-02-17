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
from discord.ext import commands
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from random import choice
import csv
import datetime
import discord
import io
import itertools
import os
import string

settings_path = "data/card/settings.json"
crdata_path = "data/card/clashroyale.json"
cardpop_path = "data/card/cardpop.json"
crtexts_path = "data/card/crtexts.csv"

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

        # CR Text data
        with open(self.crtexts_path, mode='r') as f:
            reader = csv.reader(f)
            self.crtexts = { row[0]:row[1] for row in reader}




    @commands.group(pass_context=True)
    async def card(self, ctx):
        """
        Clash Royale Decks
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @card.command(name="get", pass_context=True)
    async def card_get(self, ctx, card=None):
        """
        Display statistics about a card
        Example: !card get miner
        """
        if card is None:
            await send_cmd_help(ctx)

        card = self.get_card_name(card)

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        data = discord.Embed(
            title = self.card_to_str(card),
            description = self.get_card_description(card),
            color = discord.Color(value=color))
        data.set_thumbnail(url=self.get_card_image_url(card))

        # await self.bot.say(embed=data)
        # await self.bot.say(self.get_card_image_file(card))
        try:
            await self.bot.type()
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")
        

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




    def check_member_settings(self, server, member):
        """Init member section if necessary"""
        if member.id not in self.settings["Servers"][server.id]["Members"]:
            self.settings["Servers"][server.id]["Members"][member.id] = {
                "MemberID": member.id,
                "MemberDisplayName": member.display_name,
                "Decks": {}}
            self.save_settings()

    def check_server_settings(self, server):
        """Init server data if necessary"""
        if server.id not in self.settings["Servers"]:
            self.settings["Servers"][server.id] = { "ServerName": str(server),
                                                    "ServerID": str(server.id),
                                                    "Members": {} }
            self.save_settings()

    def save_settings(self):
        """Saves data to settings file"""
        dataIO.save_json(self.file_path, self.settings)


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

