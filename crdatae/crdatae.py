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


class ClashRoyale:
    """Clash Royale Data."""
    instance = None

    class __ClashRoyale:
        """Singleton."""
        def __init__(self, *args, **kwargs):
            """Init."""
            self.data = dataIO.load_json(CLASH_ROYALE_JSON)

    def __init__(self, *args, **kwargs):
        """Init."""
        if not ClashRoyale.instance:
            ClashRoyale.instance = ClashRoyale.__ClashRoyale(*args, **kwargs)
        else:
            pass

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def card_elixir(self, card):
        """"Elixir of a card."""
        try:
            return self.data["Cards"][card]["elixir"]
        except KeyError:
            return 0


class Card():
    """Clash Royale Card."""

    def __init__(self, key=None, level=None):
        """Init.

        Params
        + name (str). Key in the ClashRoyale.json
        """
        self.key = key
        self.level = level

    @property
    def elixir(self):
        """Elixir value."""
        return ClashRoyale().card_elixir(self.key)

    def emoji(self, be: BotEmoji):
        """Emoji representation of the card."""
        if self.key is None:
            return ''
        name = self.key.replace('-', '')
        return be.name(name)


class Deck():
    """Clash Royale Deck.
    
    Contains 8 cards.
    """

    def __init__(self, card_keys=None, card_levels=None, rank=0, usage=0):
        """Init.

        Params
        + rank (int). Rank on the leaderboard.
        + cards []. List of card ids (keys in ClashRoyale.json).
        + card_levels []. List of card levels.
        """
        self.rank = rank
        self.usage = usage
        self.cards = [Card(key=key) for key in card_keys]
        if card_levels is not None:
            kl_zip = zip(card_keys, card_levels)
            self.cards = [Card(key=k, level=l) for k, l in kl_zip]

    @property
    def avg_elixir(self):
        """Average elixir of the deck."""
        elixirs = [c.elixir for c in self.cards if c.elixir != 0]
        return sum(elixirs) / len(elixirs)

    @property
    def avg_elixir_str(self):
        """Average elixir with format."""
        return 'Average Elixir: {:.3}'.format(self.avg_elixir)

    def emoji_repr(self, be: BotEmoji, show_levels=False):
        """Emoji representaion."""
        out = []
        for card in self.cards:
            emoji = card.emoji(be)
            level = card.level
            level_str = ''
            if show_levels and level is not None:
                level_str = '`{:.<2}`'.format(level)
            out.append('{}{}'.format(emoji, level_str))
        return ''.join(out)

    def __repr__(self):
        return ' '.join([c.key for c in self.cards])


class CRDataEnhanced:
    """Clash Royale Data - Enchanced options.
    
    Requires CRData cog to function.
    """

    error_msg = {
        "requires_crdata": (
            "The CRData cog is not installed or loaded. "
            "This cog cannot function without it."
        )
    }

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.be = BotEmoji(bot)
        self.clashroyale = ClashRoyale().data

    @commands.group(pass_context=True, no_pm=True)
    async def crdatae(self, ctx):
        """Clash Royale Real-Time Global 200 Leaderboard."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crdatae.command(name="leaderboard", aliases=['lb'], pass_context=True, no_pm=True)
    async def crdatae_leaderboard(self, ctx):
        """Leaderboard."""
        crdata = self.bot.get_cog('CRData')
        if crdata is None:
            await self.bot.say(self.error_msg["requires_crdata"])
            return

        data = crdata.get_last_data()
        # decks = data["decks"]

        decks = []
        for rank, deck in enumerate(data["decks"], 1):
            cards = [crdata.sfid_to_id(card["key"]) for card in deck]
            levels = [card["level"] for card in deck]
            decks.append(Deck(card_keys=cards, card_levels=levels, rank=rank))

        # embeds
        per_page = 25
        decks_group = list(grouper(per_page, decks))
        color = random_discord_color()

        for em_id, decks in enumerate(decks_group):

            em = self.embed_decks_leaderboard(
                decks,
                page=(em_id + 1),
                title="Clash Royale: Global Top 200 Decks",
                color=color,
                footer_text="Data provided by http://starfi.re"
            )

            await self.bot.say(embed=em)

            if em_id < len(decks_group) - 1:
                show_next = await self.show_next_page(ctx)
                if not show_next:
                    await self.bot.say("Search results aborted.")
                    break

    def embed_decks_leaderboard(self, decks, **kwargs):
        """Show embed decks.

        Params:
        + page. Current page.
        + per_page. Number of results per page.
        + All parameters supported by Discord Embeds.
        """
        em = discord.Embed(**kwargs)

        page = kwargs.get('page', 1)
        per_page = kwargs.get('per_page', 25)
        show_usage = kwargs.get('show_usage', False)
        footer_text = kwargs.get('footer_text', '')

        for deck_id, deck in enumerate(decks):
            if deck is not None:
                usage_str = ''
                if deck.usage and show_usage:
                    usage_str = '(Usage: {})'.format(deck.usage)
                field_name = "Rank {} {}".format(deck.rank, usage_str)
                field_value = '{}\n{}'.format(
                    deck.emoji_repr(self.be, show_levels=True),
                    deck.avg_elixir_str)
                em.add_field(name=field_name, value=field_value)

        em.set_footer(text=footer_text)
        return em

    @crdatae.command(name="search", pass_context=True, no_pm=True)
    async def crdatae_search(self, ctx, *cards):
        """Search decks.

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
            await self.bot.say(self.error_msg["requires_crdata"])
            return

        found_decks = await crdata.search(ctx, *cards)

        if found_decks is None:
            await self.bot.say("Found 0 decks.")
            return
        if not len(found_decks):
            await self.bot.say("Found 0 decks.")
            return

        decks = []
        for fd in found_decks:
            card_keys = [crdata.sfid_to_id(card["key"]) for card in fd["deck"]]
            card_levels = [card["level"] for card in fd["deck"]]
            deck = Deck(card_keys=card_keys, card_levels=card_levels, rank=fd["ranks"][0], usage=fd["count"])
            decks.append(deck)

        per_page = 25
        decks_group = list(grouper(per_page, decks))
        color = random_discord_color()

        for page, decks_page in enumerate(decks_group):

            em = self.embed_decks_search(
                decks_page,
                page=(page + 1),
                title="Clash Royale: Global Top 200 Decks",
                description="Found {} decks.".format(len(decks)),
                color=color,
                footer_text="Data provided by http://starfi.re",
                show_usage=False
            )

            await self.bot.say(embed=em)

            if page < len(decks_group) - 1:
                show_next = await self.show_next_page(ctx)
                if not show_next:
                    await self.bot.say("Search results aborted.")
                    break

    def embed_decks_search(self, decks, **kwargs):
        """Show embed decks.

        Params:
        + page. Current page.
        + per_page. Number of results per page.
        + All parameters supported by Discord Embeds.
        """
        em = discord.Embed(**kwargs)

        page = kwargs.get('page', 1)
        per_page = kwargs.get('per_page', 25)
        show_usage = kwargs.get('show_usage', False)
        footer_text = kwargs.get('footer_text', '')

        for deck_id, deck in enumerate(decks):
            if deck is not None:
                result_number = per_page * (page - 1) + (deck_id + 1)

                usage_str = ''
                if deck.usage and show_usage:
                    usage_str = '(Usage: {})'.format(deck.usage)
                field_name = "{}: Rank {} {}".format(result_number, deck.rank, usage_str)
                field_value = '{}\n{}'.format(
                    deck.emoji_repr(self.be, show_levels=True),
                    deck.avg_elixir_str)
                em.add_field(name=field_name, value=field_value)

        em.set_footer(text=footer_text)
        return em

    async def show_next_page(self, ctx):
        """Results pagination."""
        timeout = 30
        await self.bot.say(
            "Would you like to see more results? (y/n)")
        answer = await self.bot.wait_for_message(
            timeout=timeout,
            author=ctx.message.author)
        if answer is None:
            return False
        elif not len(answer.content):
            return False
        elif answer.content[0].lower() != 'y':
            return False
        return True

    def card_elixir(self, card):
        """Return elixir of a card."""
        elixir = 0
        try:
            elixir = self.clashroyale["Cards"][card]["elixir"]
        except KeyError:
            pass
        return elixir


def setup(bot):
    """Setup bot."""
    n = CRDataEnhanced(bot)
    bot.add_cog(n)
