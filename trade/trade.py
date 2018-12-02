"""
The MIT License (MIT)

Copyright (c) 2018 SML

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

import asyncio
from collections import Counter
from collections import defaultdict
from collections import namedtuple

import aiohttp
import argparse
import csv
import datetime as dt
import discord
import io
import os
import yaml
from addict import Dict
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.chat_formatting import inline
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "trade")
JSON = os.path.join(PATH, "settings.json")
CARDS_AKA_YML_URL = 'https://raw.githubusercontent.com/smlbiobot/SML-Cogs/master/deck/data/cards_aka.yaml'
CARDS_JSON_URL = 'https://royaleapi.github.io/cr-api-data/json/cards.json'


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    return t


TagValidation = namedtuple("TagValidation", "valid invalid_chars")


def validate_tag(tag) -> TagValidation:
    invalid_chars = []
    for letter in tag:
        if letter not in '0289CGJLPQRUVY':
            invalid_chars.append(letter)

    if len(invalid_chars):
        return TagValidation(False, invalid_chars)
    return TagValidation(True, [])


def get_now_timestamp():
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).timestamp()


def format_timespan(time):
    now = dt.datetime.utcnow()
    delta = now - time
    s = delta.total_seconds()
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '{: >2}h {: >2}m'.format(int(hours), int(minutes))


TradeItem = namedtuple(
    "TradeItem", [
        "server_id",
        "author_id",
        "give_card",
        "get_card",
        "clan_tag",
        "rarity",
        "timestamp"
    ]
)
TradeItem.__new__.__defaults__ = (None,) * len(TradeItem._fields)


class Settings(Dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self):
        dataIO.save_json(JSON, self.to_dict())

    def check_server(self, server_id):
        if not self[server_id].trades:
            self[server_id].trades = dict()

    def reset_server(self, server_id):
        self[server_id].trades = dict()
        self.save()

    def remove_old_trades(self, server_id):
        """Look for trade items that’s older than 24 hours and remove them."""
        now = get_now_timestamp()
        limit = dt.timedelta(days=2).total_seconds()
        for k, v in self[server_id].trades.copy().items():
            if abs(now - v.get('timestamp')) > limit:
                self[server_id].trades.pop(k)
        self.save()

    def add_trade_item(self, item: TradeItem):
        """Add trade item if valid."""
        self.check_server(item.server_id)
        id_ = str(item.timestamp)
        if all([item.give_card, item.get_card, item.rarity]):
            self[item.server_id].trades[id_] = item._asdict()
            self.save()
            return True
        return False

    def remove_trade_item(self, item: TradeItem):
        self.check_server(item.server_id)

        removed = False

        trades = self[item.server_id].trades
        for k, v in trades.copy().items():
            if all([
                v.get('get_card') == item.get_card,
                v.get('give_card') == item.give_card,
                v.get('clan_tag') == item.clan_tag,
            ]):
                trades.pop(k)
                removed = True

        self.save()

        return removed

    def get_trades(self, server_id):
        """Return list of trades"""
        self.check_server(server_id)
        self.remove_old_trades(server_id)
        trades = [TradeItem(**v) for k, v in self[server_id].trades.items()]
        return trades

    def enable_auto(self, server_id, channel_id):
        """Enable auto posting"""
        self.check_server(server_id)
        self[server_id].auto.enabled = True
        self[server_id].auto.channel_id = channel_id
        self.save()

    def disable_auto(self, server_id):
        """Disable auto posting"""
        self.check_server(server_id)
        self[server_id].auto.enabled = False
        self[server_id].auto.channel_id = None
        self.save()


class Trade:
    """Clash Royale Trading"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Settings(dataIO.load_json(JSON))
        self._cards_aka = None
        self._aka_to_card = None
        self._cards_constants = None

    async def get_cards_aka(self):
        if self._cards_aka is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(CARDS_AKA_YML_URL) as resp:
                    data = await resp.read()
                    self._cards_aka = yaml.load(data)
        return self._cards_aka

    async def aka_to_card(self, abbreviation):
        """Go through all abbreviation to find card dict"""
        if self._aka_to_card is None:
            akas = await self.get_cards_aka()
            self._aka_to_card = dict()
            for k, v in akas.items():
                # assign card as card
                self._aka_to_card[k] = k
                # assign card without hyphen
                if '-' in k:
                    self._aka_to_card[k.replace('-', '')] = k
                for item in v:
                    self._aka_to_card[item] = k
        return self._aka_to_card.get(abbreviation)

    async def get_cards_constants(self):
        if self._cards_constants is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(CARDS_JSON_URL) as resp:
                    self._cards_constants = await resp.json()
        return self._cards_constants

    async def check_cards(self, cards=None):
        """Make sure all cards have the same rarity."""
        rarities = []
        for c in await self.get_cards_constants():
            for card in cards:
                if c.get('key') == card:
                    rarities.append(c.get('rarity'))
        if len(set(rarities)) == 1:
            return True
        return False

    async def get_rarity(self, card):
        for c in await self.get_cards_constants():
            if c.get('key') == card:
                return c.get('rarity')
        return None

    def get_emoji(self, name):
        """Return emoji by name."""
        name = name.replace('-', '')
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return '<:{name}:{id}>'.format(name=emoji.name, id=emoji.id)
        return ''

    @commands.group(name="trade", pass_context=True)
    async def trade(self, ctx):
        """Clash Royale trades."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.serverowner_or_permissions(manage_server=True)
    @trade.command(name="reset", pass_context=True)
    async def reset_server_trades(self, ctx):
        """Reset all trades on server."""
        server = ctx.message.server
        self.settings.reset_server(server.id)
        await self.bot.say("Server trades reset: all trades removed.")

    @checks.mod_or_permissions()
    @trade.command(name="auto_on", pass_context=True)
    async def enable_auto_trade_channel(self, ctx, channel: discord.Channel):
        """Set channel for auto trade listings."""
        server = ctx.message.server
        self.settings.enable_auto(server.id, channel.id)
        await self.bot.say("Auto sending trade list.")

    @checks.mod_or_permissions()
    @trade.command(name="auto_off", pass_context=True)
    async def disable_auto_trade_channel(self, ctx):
        """Set channel for auto trade listings."""
        server = ctx.message.server
        self.settings.disable_auto(server.id)
        await self.bot.say("Disabled auto trade list.")

    @trade.command(name="add", aliases=['a'], pass_context=True)
    async def add_trade(self, ctx, give: str, get: str, clan_tag: str):
        """Add a trade. Can use card shorthand"""
        server = ctx.message.server
        author = ctx.message.author

        give_card = await self.aka_to_card(give)
        get_card = await self.aka_to_card(get)
        clan_tag = clean_tag(clan_tag)

        # validate clan tag
        valid = validate_tag(clan_tag)
        if not valid.valid:
            await self.bot.say("Your clan tags include invalid characters: {}".format(', '.join(valid.invalid_chars)))
            return

        # validate cards
        if give_card is None:
            await self.bot.say("Unknown card: {}".format(give))
            return

        if get_card is None:
            await self.bot.say("Unknown card: {}".format(get))
            return

        rarities = []
        for c in [give_card, get_card]:
            rarities.append(await self.get_rarity(c))

        if len(set(rarities)) != 1:
            await self.bot.say("Rarities does not match.")
            return

        rarity = rarities[0]

        self.settings.add_trade_item(TradeItem(server_id=server.id,
                                               author_id=author.id,
                                               give_card=give_card,
                                               get_card=get_card,
                                               clan_tag=clan_tag,
                                               rarity=rarity,
                                               timestamp=get_now_timestamp()))
        self.settings.save()
        await self.bot.say(
            "Give: {give_card}, Get: {get_card}, {clan_tag}, {rarity}".format(
                give_card=give_card,
                get_card=get_card,
                clan_tag=clan_tag,
                rarity=rarity,
            )
        )

    @trade.command(name="remove", aliases=['rm'], pass_context=True)
    async def remove_trade(self, ctx, give: str, get: str, clan_tag: str):
        """Remove a trade. Can use card shorthand"""
        server = ctx.message.server

        give_card = await self.aka_to_card(give)
        get_card = await self.aka_to_card(get)
        clan_tag = clean_tag(clan_tag)

        trade_item = TradeItem(
            server_id=server.id,
            give_card=give_card,
            get_card=get_card,
            clan_tag=clan_tag
        )
        if self.settings.remove_trade_item(trade_item):
            await self.bot.say('Trade removed')
        else:
            await self.bot.say("Cannot find your trade.")

    @trade.command(name="import", aliases=['i'], pass_context=True)
    async def import_trade(self, ctx):
        """Import list of trades from CSV file.

        First row is header:
        give,get,clan_tag
        """
        if len(ctx.message.attachments) == 0:
            await self.bot.say(
                "Please attach CSV with this command. "
            )
            return

        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.text()

        reader = csv.DictReader(io.StringIO(data))

        async def get_field(row, field, is_card=False, is_clan_tag=False):
            s = row.get(field)
            v = None
            if s is None:
                return None
            s = s.strip()
            if is_card:
                s = s.lower().replace(' ', '-')
                v = await self.aka_to_card(s)
            elif is_clan_tag:
                v = clean_tag(s)
            return v

        trade_items = []

        server = ctx.message.server
        author = ctx.message.author

        for row in reader:
            # normalize string
            give_card = await get_field(row, 'give', is_card=True)
            get_card = await get_field(row, 'get', is_card=True)
            clan_tag = await get_field(row, 'clan_tag', is_clan_tag=True)

            # validate rarities
            rarities = []
            for c in [give_card, get_card]:
                rarities.append(await self.get_rarity(c))

            if len(set(rarities)) != 1:
                await self.bot.say("Rarities does not match for {} and {}".format(give_card, get_card))

            else:
                trade_items.append(
                    TradeItem(
                        server_id=server.id,
                        author_id=author.id,
                        give_card=give_card,
                        get_card=get_card,
                        clan_tag=clan_tag,
                        rarity=rarities[0],
                        timestamp=get_now_timestamp()
                    )
                )

        for item in trade_items:
            self.settings.add_trade_item(item)

        self.settings.save()

        o = ["Give: {give_card}, Get: {get_card}, {clan_tag}".format(**item._asdict()) for item in trade_items]
        for page in pagify("\n".join(o)):
            await self.bot.say(page)

    @trade.command(name="list", aliases=['l'], pass_context=True)
    @checks.mod_or_permissions()
    async def list_trades(self, ctx, *args):
        """List trades.

        Optional arguments
        --get,       | get a card, --get nw
        --give,      | give a card --give iwiz
        --rarity, -r | rarity filter -r epic
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("--get", type=str, help="Get a card")
        parser.add_argument("--give", type=str, help="Give a card")
        parser.add_argument("--rarity", "-r", type=str, help="Rarity filter")

        try:
            pa = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        server = ctx.message.server

        included_items = await self.get_filtered_list(
            server=server,
            rarity=pa.rarity[0] if pa.rarity else None,
            give_card=pa.give or None,
            get_card=pa.get or None
        )

        channel = ctx.message.channel
        await self.send_trade_list(channel, included_items)

    async def get_filtered_list(self, server: discord.Server = None, rarity=None, give_card=None, get_card=None,
                                clan_tag=None):
        """Return filtered list items"""
        items = self.settings.get_trades(server.id)

        included_items = []

        for item in items:
            # skip invalid items
            if not all([item.give_card, item.get_card, item.rarity]):
                continue

            # filter rarities
            if rarity is not None:
                if item.rarity[0].lower() != rarity.lower():
                    continue

            # filter give
            if give_card is not None:
                card = await self.aka_to_card(give_card)
                if item.give_card != card:
                    continue

            # filter get
            if get_card is not None:
                card = await self.aka_to_card(get_card)
                if item.get_card != card:
                    continue

            # filter clan_tag
            if clan_tag is not None:
                if item.clan_tag != clan_tag:
                    continue

            included_items.append(item)

        return included_items

    @trade.command(name="get", aliases=['gt'], pass_context=True)
    async def list_get_card(self, ctx, card):
        """Filter trades by cards to get."""
        server = ctx.message.server
        included_items = await self.get_filtered_list(
            server=server,
            get_card=card
        )
        channel = ctx.message.channel
        await self.send_trade_list(channel, included_items)

    @trade.command(name="give", aliases=['gv'], pass_context=True)
    async def list_give_card(self, ctx, card):
        """Filter trades by cards to give."""
        server = ctx.message.server
        included_items = await self.get_filtered_list(
            server=server,
            give_card=card
        )
        channel = ctx.message.channel
        await self.send_trade_list(channel, included_items)

    @trade.command(name="rarity", aliases=['r'], pass_context=True)
    async def list_rarity(self, ctx, rarity):
        """Filter trades by rarity."""
        server = ctx.message.server
        included_items = await self.get_filtered_list(
            server=server,
            rarity=rarity
        )
        channel = ctx.message.channel
        await self.send_trade_list(channel, included_items)

    @trade.command(name="clan", aliases=['c', 'tag'], pass_context=True)
    async def list_clan(self, ctx, clan_tag):
        """Filter trades by rarity."""
        server = ctx.message.server
        clan_tag = clean_tag(clan_tag)
        included_items = await self.get_filtered_list(
            server=server,
            clan_tag=clan_tag
        )
        channel = ctx.message.channel
        await self.send_trade_list(channel, included_items)
        await self.bot.say("https://link.clashroyale.com/?clanInfo?id={}".format(clan_tag))

    @trade.command(name="info", pass_context=True)
    async def trade_info(self, ctx):
        """List DB info."""
        server = ctx.message.server
        items = self.settings.get_trades(server.id)

        author_ids = [item.author_id for item in items]
        o = []
        o.append("Total trades: {}".format(len(items)))
        o.append("Added by:")
        for author_id, count in Counter(author_ids).most_common():
            o.append(
                inline(
                    "{name:<16} {count:>6}".format(
                        name=server.get_member(author_id).name,
                        count=count
                    )
                )
            )

        for page in pagify('\n'.join(o)):
            await self.bot.say(page)

    async def send_trade_list(self, channel, items):
        o = []

        def sort_items(item):
            R = dict(
                Common=1,
                Rare=2,
                Epic=3,
                Legendary=4
            )
            return R.get(item.rarity), item.get_card, item.give_card

        items = sorted(items, key=sort_items)
        for item in items:
            time = dt.datetime.utcfromtimestamp(item.timestamp)
            d = item._asdict()
            d.update(dict(
                give_card_emoji=self.get_emoji(item.give_card),
                get_card_emoji=self.get_emoji(item.get_card),
                r=item.rarity[0].upper(),
                s='\u2800',
                time_span=format_timespan(time)
            ))

            o.append(
                "Give: {give_card_emoji} Get: {get_card_emoji} `{s}{r} #{clan_tag:<9} {time_span}{s}`".format(**d)
            )

        if not len(o):
            await self.bot.send_message(channel, "No items found matching your request.")
            return

        first_message = None

        for page in pagify("\n".join(o)):
            msg = await self.bot.send_message(channel, page)
            if first_message is None:
                first_message = msg

        return first_message

    async def auto_post_trades(self):
        """Post trades to channel."""
        for server_id, v in self.settings.items():
            self.settings.remove_old_trades(server_id)
            if v.auto and v.auto.enabled:
                channel_id = v.auto.channel_id
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    msg = await self.send_trade_list(channel, self.settings.get_trades(server_id))

                    # delete channel messages
                    await self.bot.purge_from(channel, limit=100, before=msg)

    async def auto_post_trades_task(self):
        """Task: post embed to channel."""
        while self == self.bot.get_cog("Trade"):
            try:
                await self.auto_post_trades()
            except Exception:
                pass
            finally:
                interval = int(dt.timedelta(minutes=10).total_seconds())
                await asyncio.sleep(interval)


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = Trade(bot)
    bot.add_cog(n)
    bot.loop.create_task(n.auto_post_trades_task())
