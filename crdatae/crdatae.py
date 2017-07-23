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
import re

from __main__ import send_cmd_help
from discord.ext import commands
import discord


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


class BotEmoji:
    """Emojis available in bot."""
    def __init__(self, bot):
        self.bot = bot
        self.map = {
            'Silver': 'chestsilver',
            'Gold': 'chestgold',
            'Giant': 'chestgiant',
            'Magic': 'chestmagical',
            'super_magical': 'chestsupermagical',
            'legendary': 'chestlegendary',
            'epic': 'chestepic'
        }

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
        self.crdata = self.bot.get_cog('CRData')
        self.be = BotEmoji(bot)

    @commands.group(pass_context=True, no_pm=True)
    async def crdatae(self, ctx):
        """Clash Royale Data (Enhanced options)."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdatae.command(name="search", pass_context=True, no_pm=True)
    async def crdata_search(self, ctx, *cards):
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
        invalid_cards.extend(self.crdata.get_invalid_cards(include_cards))
        invalid_cards.extend(self.crdata.get_invalid_cards(exclude_cards))
        if len(invalid_cards) > 0:
            await self.bot.say(
                'Invalid card names: {}'.format(', '.join(invalid_cards)))
            await self.bot.say(
                'Type `!crdata cardnames` to see a list of valid input.')
            return

        include_cards = self.crdata.normalize_deck_data(include_cards)
        include_sfids = [self.crdata.id_to_sfid(c) for c in include_cards]
        exclude_cards = self.crdata.normalize_deck_data(exclude_cards)
        exclude_sfids = [self.crdata.id_to_sfid(c) for c in exclude_cards]

        data = self.crdata.get_last_data()
        decks = data["decks"]

        # sort card in decks
        sorted_decks = []
        for deck in decks:
            # when data is not clean, "key" may be missin
            # if this is the case, fix it
            clean_deck = []
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
                deck_elixir = self.crdata.deck_elixir_by_sfid(deck_cards)
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

        await self.bot.say("Found {} decks.".format(
            len(found_decks)))

        # embeds
        found_decks_group = grouper(24, found_decks)

        for fd in found_decks_group:

            em = discord.Embed(title="Top 200 Decks")

            for data in fd:
                print(data)
                if data is not None:
                    deck = data["deck"]
                    rank = ", ".join(data["ranks"])
                    usage = data["count"]
                    cards = [self.crdata.sfid_to_id(card["key"]) for card in deck]
                    cards = [c.replace('-', '') for c in cards]
                    levels = [card["level"] for card in deck]

                    # desc = "**Rank {}: (Usage: {})**".format(rank, usage)
                    desc = "**Rank {}: **".format(rank)
                    for j, card in enumerate(cards):
                        desc += "{} ".format(self.crdata.id_to_name(card))
                        desc += "({}), ".format(levels[j])
                    desc = desc[:-1]

                    deck_name = "Rank {}".format(rank)
                    cards_str = ''.join([self.be.name(c) for c in cards])

                    em.add_field(name=deck_name, value=cards_str, inline=False)

                    # show_next = await self.crdata.show_result_row(
                    #     ctx,
                    #     cards,
                    #     i,
                    #     len(decks),
                    #     deck_name="Rank {}".format(rank),
                    #     author="Top 200 Decks",
                    #     description=desc[:-1])

            await self.bot.say(embed=em)





def setup(bot):
    """Setup bot."""
    n = CRDataEnhanced(bot)
    bot.add_cog(n)