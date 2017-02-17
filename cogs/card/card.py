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
import itertools

settings_path = "data/card/settings.json"
crdata_path = "data/card/clashroyale.json"
cardpop_path = "data/card/cardpop.json"

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

