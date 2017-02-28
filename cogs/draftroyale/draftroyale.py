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
from random import shuffle
import datetime
import discord
import string
import os


CRDATA_PATH = "data/draftroyale/clashroyale.json"
SETTINGS_PATH = "data/draftroyale/draftroyale.json"

HELP_TEXT = """
**Draft Royale: Clash Royale draft system**

1. Start a draft
`!draft start`

2. Pick players
`!draft players [username...]`

3. Pick cards
`!draft pick`
"""



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
    - 4 players (10 cards)
    - 8 players (8 cards)
    - This system however will allow any number of players (2-8)
      with number of cards set to card count // players

    Bans:

    Some drafts have bans. For example, if graveyard is picked as a banned
    card, then no one can pick it.pick

    Drafting order:

    Most drafts are snake drafts. They go from first to last then backwards.
    The first and last player gets two picks in a row.
    1 2 3 4 4 3 2 1 1 2 3 4 etc.

    Required files:

    - data/clashroyale.json: card data
    - data/settings.json: technically not needed but good to
                          have a human-readable history log
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

        self.min_players = 2
        self.max_players = 8

        self.prompt_timeout = 60.0

        self.init()
        self.init_card_data()

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

    def init(self):
        """Abort all operations."""
        self.active_draft = None
        self.admin = None
        self.players = []
        self.time_id = datetime.datetime.utcnow().isoformat()
        self.picked_cards = {}
        self.pick_order = []
        self.is_snake_draft = True

    @commands.group(pass_context=True, no_pm=True)
    async def draft(self, ctx: Context):
        """Clash Royale Draft System.

        Full help
        !draft help
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @draft.command(name="help", pass_context=True)
    async def draft_help(self, ctx: Context):
        """Display help for drating."""
        await self.bot.say(HELP_TEXT)

    @draft.command(name="start", pass_context=True, no_pm=True)
    async def draft_start(self, ctx: Context):
        """Initialize a draft.

        The author who type this command will be designated as the
        owner / admin of the draft.
        """
        await self.bot.say("Draft Royale")

        if self.active_draft is not None:
            await self.bot.say("An active draft is going on. "
                               "Please finish the current draft "
                               "before starting another.")
            return

        self.init()

        # server = ctx.message.server
        self.admin = ctx.message.author
        await self.bot.say(f"**Draft Admin** set to "
                           f"{self.admin.display_name}.")

        self.active_draft = {
            "admin_id": self.admin.id,
            "players": []
        }

        if "drafts" not in self.settings:
            self.settings["drafts"] = {}
        self.settings["drafts"][self.time_id] = self.active_draft

        self.save_settings()

        await self.bot.say(f"{self.admin.mention} "
                           f"Run `!draft players` to set the players")

    @draft.command(name="players", pass_context=True, no_pm=True)
    async def draft_players(self, ctx: Context, *players: discord.Member):
        """Set the players playing in the draft."""
        author = ctx.message.author
        server = ctx.message.server

        if author != self.admin:
            await self.bot.say("Players must be set by the draft admin.")
            await self.bot.say(f"Draft admin: {self.admin.mention}")
            return

        if players is None:
            await send_cmd_help(ctx)
            return

        # reset players if already set
        self.players = []
        for player in players:
            if player not in server.members:
                await self.bot.say(f"{player.display_name} "
                                   f"is not on this server.")
            else:
                self.players.append(player)

        await self.list_players()
        self.save_players_settings()

    @draft.command(name="random", pass_context=True, no_pm=True)
    async def draft_random(self, ctx: Context):
        """Randomize the player order."""
        shuffle(self.players)
        self.active_draft["players"] = []

        await self.list_players()
        self.save_players_settings()

    @draft.command(name="snake", pass_context=True, no_pm=True)
    async def draft_snake(self, ctx: Context, on_off: bool):
        """Enable / disable snake draft mode.
        Example:
        !draft snake 1
        !draft snake 0
        """
        self.is_snake_draft = on_off
        if on_off:
            await self.bot.say("Snake draft enabled.")
        else:
            await self.bot.say("Snake draft disabled.")

    @draft.command(name="status", pass_context=True, no_pm=True)
    async def draft_status(self, ctx: Context):
        """Display status of the current draft."""
        data = discord.Embed(
            title="Clash Royale Drafting System",
            description="Current Status")
        data.add_field(name="Admin", value=self.admin.display_name)
        data.add_field(name="Snake Draft", value=self.is_snake_draft)
        data.add_field(
            name="Players",
            value="\n".join([f"+ {player.display_name}"
                             for player in self.players]),
            inline=False)
        data.add_field(
            name="Available Cards",
            value=", ".join(self.get_available_card_names()),
            inline=False)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @draft.command(name="cards", pass_context=True, no_pm=True)
    async def draft_cards(self, ctx: Context, sort: str=None):
        """Display available cards for picking.

        Optionally set sort order.
        """
        out = []
        out.append("**Available cards**")
        card_names = [
            self.card_key_to_name(key)
            for key in self.cards
            if key not in self.picked_cards]
        out.append(", ".join(card_names))

        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @draft.command(name="pick", pass_context=True, no_pm=True)
    async def draft_pick(self, ctx: Context):
        """Player pick cards."""
        pass

    @draft.command(name="abort", pass_context=True, no_pm=True)
    async def draft_abort(self, ctx: Context):
        """Abort an active draft."""
        self.init()
        await self.bot.say("Draft Royale aborted.")

    @draft.command(name="listplayers", pass_context=True, no_pm=True)
    async def draft_listplayers(self, ctx: Context):
        """List players in the play order."""
        await self.list_players()

    async def list_players(self):
        """List the players in the play order."""
        out = []
        out.append("Players for this draft:")
        for player in self.players:
            out.append(f"+ {player.display_name}")
        await self.bot.say("\n".join(out))

    def save_players_settings(self):
        """Save players settings."""
        self.active_draft["players"] = []
        for player in self.players:
            self.active_draft["players"].append({
                "user_id": player.id,
                "user_name": player.display_name})
        self.save_settings()

    def save_settings(self):
        """Save settings to disk."""
        dataIO.save_json(self.settings_path, self.settings)

    def card_key_to_name(self, card_key: str):
        """Return card name from card key."""
        return string.capwords(card_key.replace('-', ' '))

    def get_available_cards(self):
        """Return list of available cards that are not picked yet."""
        return [
            card for card in self.cards
            if card not in self.picked_cards]

    def get_available_card_names(self):
        """Return list of available card names that are not picked yet."""
        return [
            self.card_key_to_name(card)
            for card in self.get_available_cards()]


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



