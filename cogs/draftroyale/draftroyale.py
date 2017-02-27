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
from cogs.utils.chat_formatting import pagify
from discord.ext import commands
from discord.ext.commands import Context
from random import choice
import datetime
import discord
import os


CRDATA_PATH = "data/draftroyale/clashroyale.json"
SETTINGS_PATH = "data/draftroyale/settings.json"


class Draft:
    """Clash Royale drafts."""

    def __init__(self, admin: discord.Member=None):
        """Constructor.

        Args:
          admin (discord.Member): administrator of the draft
        """

        self.admin = admin

class DraftRoyale:
    """Clash Royale drafting bot.

    This cog is written to facilitate draftin in Clash Royale.

    Types of drafts:
    + 4 players (10 cards)
    + 8 players (8 cards)

    Bans
    Some drafts have bans. For example, if graveyard is picked as a banned
    card, then no one can pick it.pick

    Drafting order
    Most drafts are snake drafts. They go from first to last then backwards.
    The first and last player gets two picks in a row.
    1 2 3 4 4 3 2 1 1 2 3 4 etc.
    """

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        self.crdata_path = CRDATA_PATH
        self.settings_path = SETTINGS_PATH

        self.crdata = dataIO.load_json(self.crdata_path)
        self.settings = dataIO.load_json(self.settings_path)

        # init card data
        self.cards = []
        self.cards_abbrev = {}

    def init_card_data(self):
        """Initialize card data and popularize acceptable abbreviations."""
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

    @commands.group(pass_context=True, no_pm=True)
    async def draft(self, ctx: Context):
        """Clash Royale Draft System.

        Full help
        !draft help
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @draft.command(name="init", pass_context=True, no_pm=True)
    async def draft_init(self, ctx:Context):
        """Initialize a draft.

        The author who type this command will be designated as the
        owner / admin of the draft.
        """


def check_folder():
    """Check data folders exist. Create if necessary."""
    folders = ["data/draftroyale",
               "data/draftroyale/img",
               "data/draftroyale/img/cards"]
    for f in folders:
        if not os.path.exists(f):
            os.makedirs(f)

def check_files():
    """Check required data files exists."""
    defaults = {}
    f = SETTINGS_PATH
    if not dataIO.is_valid_json(f):
        dataIO.save_json(f, defaults)

def setup(bot):
    """Add cog to bot."""
    check_folder()
    check_files()
    n = DraftRoyale(bot)
    bot.add_cog(n)



