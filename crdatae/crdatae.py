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

import itertools
import os
from random import choice

import discord
from __main__ import send_cmd_help
from discord.ext import commands

from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "crdatae")
CLASH_ROYALE_JSON = os.path.join(PATH, "clashroyale.json")


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


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


class CRDataEnhanced:
    """Clash Royale Data - Enchanced options.
    
    Requires CRData cog to function.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.be = BotEmoji(bot)
        self.clashroyale = dataIO.load_json(CLASH_ROYALE_JSON)

    @commands.group(pass_context=True, no_pm=True)
    async def crdatae(self, ctx):
        """Clash Royale Data (Enhanced options)."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdatae.command(name="search", pass_context=True, no_pm=True)
    async def crdatae_search(self, ctx, *cards):
        """Search decks on the Global 200 and output as embed using card emojis

        1. Include card(s) to search for
        !crdatae search fb log

        2. Exclude card(s) to search for (use - as prefix)
        !crdatae search golem -lightning

        3. Elixir range (add elixir=min-max)
        !crdatae search hog elixir=0-3.2

        e.g.: Find 3M Hog decks without battle ram under 4 elixir
        !crdatae search 3m hog -br elixir=0-4
        """
        if not len(cards):
            await self.bot.say("You must enter at least one card.")
            await send_cmd_help(ctx)
            return

        crdata = self.bot.get_cog('CRData')

        if crdata is None:
            await self.bot.say("The CRData cog does not appear to be loaded.")
            return

        found_decks = await crdata.search(ctx, *cards)

        if found_decks is None:
            await self.bot.say("Found 0 decks.")
            return
        if not len(found_decks):
            await self.bot.say("Found 0 decks.")
            return

        # embeds
        per_page = 25
        found_decks_group = grouper(per_page, found_decks)
        color = random_discord_color()

        for em_id, fd in enumerate(found_decks_group):

            em = discord.Embed(title="Clash Royale: Global Top 200 Decks", color=color)

            for data in fd:
                # print(data)
                if data is not None:
                    deck = data["deck"]
                    rank = ", ".join(data["ranks"])
                    usage = data["count"]
                    cards = [crdata.sfid_to_id(card["key"]) for card in deck]

                    card_elixirs = [self.card_elixir(c) for c in cards]
                    # Remove from calculation if elixir is 0
                    card_elixirs = [e for e in card_elixirs if e != 0]
                    avg_elixir = sum(card_elixirs) / len(card_elixirs)

                    cards = [c.replace('-', '') for c in cards]
                    levels = [card["level"] for card in deck]

                    field_name = "Rank {}.".format(rank)

                    cards_levels = zip(cards, levels)
                    cards_str = ''.join([
                        '{}`{:.<2}`'.format(self.be.name(cl[0]), cl[1]) for cl in cards_levels])
                    field_value = '{}\nAvg Elixir: {:.3f}'.format(cards_str, avg_elixir)

                    em.add_field(name=field_name, value=field_value, inline=False)

            await self.bot.say(embed=em)

        await self.bot.say("Data provided by <http://starfi.re>")

    def card_elixir(self, card):
        """Return elixir of a card."""
        if card not in self.clashroyale["Cards"].keys():
            return 0
        return self.clashroyale["Cards"][card]["elixir"]


def setup(bot):
    """Setup bot."""
    n = CRDataEnhanced(bot)
    bot.add_cog(n)