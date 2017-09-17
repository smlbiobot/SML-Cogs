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

import asyncio
import datetime as dt
import itertools
import json
import os
from collections import defaultdict
from datetime import timedelta
from random import choice

import aiohttp
import discord
import inflect
from __main__ import send_cmd_help
from discord.ext import commands
from itertools import cycle

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "crprofile")
PATH_PLAYERS = os.path.join(PATH, "players")
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")
CHESTS = dataIO.load_json(os.path.join('data', 'crprofile', 'chests.json'))

DATA_UPDATE_INTERVAL = timedelta(minutes=30).seconds

API_FETCH_TIMEOUT = 5

BOTCOMMANDER_ROLES = ["Bot Commander"]

CREDITS = 'Harmiox + SML'


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


class BotEmoji:
    """Emojis available in bot."""

    def __init__(self, bot):
        self.bot = bot
        self.map = {
            'Silver': 'chestsilver',
            'Gold': 'chestgold',
            'Giant': 'chestgiant',
            'Magic': 'chestmagical',
            'SuperMagical': 'chestsupermagical',
            'Legendary': 'chestlegendary',
            'Epic': 'chestepic'
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


class SCTag:
    """SuperCell tags."""

    TAG_CHARACTERS = list("0289PYLQGRJCUV")

    def __init__(self, tag: str):
        """Init.

        Remove # if found.
        Convert to uppercase.
        Convert Os to 0s if found.
        """
        if tag.startswith('#'):
            tag = tag[1:]
        tag = tag.replace('O', '0')
        tag = tag.upper()
        self._tag = tag

    @property
    def tag(self):
        """Return tag as str."""
        return self._tag

    @property
    def valid(self):
        """Return true if tag is valid."""
        for c in self.tag:
            if c not in self.TAG_CHARACTERS:
                return False
        return True

    @property
    def invalid_chars(self):
        """Return list of invalid characters."""
        invalids = []
        for c in self.tag:
            if c not in self.TAG_CHARACTERS:
                invalids.append(c)
        return invalids

    @property
    def invalid_error_msg(self):
        """Error message to show if invalid."""
        return (
            'The tag you have entered is not valid. \n'
            'List of invalid characters in your tag: {}\n'
            'List of valid characters for tags: {}'.format(
                ', '.join(self.invalid_chars),
                ', '.join(self.TAG_CHARACTERS)
            ))


class CRArenaModel:
    """Clash Royale arenas."""

    def __init__(self, **kwargs):
        """Init.

        Keyword Args:
            Name (str)
            TID (str)
            TIDText (str)
            SubtitleTID (str)
            SubtitleTIDText (str)
            Arena (int)
            ChestArena (str)
            TvArena (str)
            IsInUse (bool)
            TrainingCamp (bool)
            PVEArena (str)
            TrophyLimit (int)
            DemoteTrophyLimit (int)
            SeasonTrophyReset (str)
            ChestRewardMultiplier (int)
            ChestShopPriceMultiplier (int)
            RequestSize (int)
            MaxDonationCountCommon (int)
            MaxDonationCountRare (int)
            MaxDonationCountEpic (int)
            IconSWF (str)
            IconExportName (str)
            MainMenuIconExportName (str)
            SmallIconExportName (str)
            MatchmakingMinTrophyDelta (int)
            MatchmakingMaxTrophyDelta (int)
            MatchmakingMaxSeconds (int)
            PvpLocation (str)
            TeamVsTeamLocation (str)
            DailyDonationCapacityLimit (int)
            BattleRewardGold (str)
            ReleaseDate (str)
        """
        self.__dict__.update(kwargs)


class CRPlayerModel:
    """Clash Royale arenas."""

    def __init__(self, is_cache=False, data=None):
        """Init."""
        self.data = data
        self.is_cache = is_cache

    @property
    def tag(self):
        """Player tag"""
        return self.data.get("tag", None)

    @property
    def name(self):
        """IGN."""
        return self.data.get("name", None)

    @property
    def trophies(self):
        """Trophies."""
        return self.data.get("trophies", None)

    @property
    def experience(self):
        """Experience."""
        return self.data.get("experience", None)

    @property
    def level(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("level", None)
        return None

    @property
    def xp(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("xp", 0)
        return 0

    @property
    def xp_total(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("xpRequiredForLevelUp", None)
        return None

    @property
    def xp_str(self):
        """Experience in current / total format."""
        xp_levels = [
            "0",
            "20",
            "50",
            "100",
            "200",
            "400",
            "1000",
            "2000",
            "5000",
            "10000",
            "30000",
            "40000",
            "80000",
            "MAX"
        ]
        current = 'MAX'
        total = 'MAX'
        if isinstance(self.xp_total, int):
            current = '{:,}'.format(self.xp)
            total = '{:,}'.format(self.xp_total)
        return '{} / {}'.format(current, total)

    @property
    def clan(self):
        """Clan."""
        return self.data.get("clan", None)

    @property
    def clan_name(self):
        """Clan name."""
        if self.clan is not None:
            return self.clan.get("name", None)
        return None

    @property
    def clan_tag(self):
        """Clan tag."""
        if self.clan is not None:
            return self.clan.get("tag", None)
        return None

    @property
    def clan_role(self):
        """Clan role."""
        if self.clan is not None:
            return self.clan.get("role", None)
        return None

    @property
    def clan_name_tag(self):
        """Clan name and tag."""
        return '{} #{}'.format(self.clan_name, self.clan_tag)

    @property
    def clan_badge_url(self):
        """Clan badge url."""
        filename = self.clan.get("badgeUrl", None)
        return 'http://api.cr-api.com{}'.format(filename)
        # if filename is not None:
        #     filename
        # badges = dataIO.load_json(BADGES_JSON)
        # try:
        #     key = str(self.clan["badge_id"] - 1 + 16000000)
        #     return 'https://smlbiobot.github.io/img/emblems/{}.png'.format(badges[key])
        # except KeyError:
        #     return 'https://smlbiobot.github.io/img/emblems/NoClan.png'

    @property
    def stats(self):
        """Stats."""
        return self.data.get("stats", None)

    @property
    def challenge_cards_won(self):
        """Challenge cards won."""
        if self.stats is not None:
            return self.stats.get("challengeCardsWon", 0)
        return 0

    @property
    def tourney_cards_won(self):
        """Challenge cards won."""
        if self.stats is not None:
            return self.stats.get("tournamentCardsWon", 0)
        return 0

    @property
    def total_donations(self):
        """Total donations."""
        if self.stats is not None:
            return self.stats.get("totalDonations", 0)
        return 0

    @property
    def cards_found(self):
        """Cards found."""
        if self.stats is not None:
            return self.stats.get("cardsFound", 0)
        return 0

    @property
    def favorite_card(self):
        """Favorite card"""
        """Cards found."""
        if self.stats is not None:
            return self.stats.get("favoriteCard", "soon")
        return "soon"

    @property
    def trophy_current(self):
        """Current trophies."""
        return self.data.get("trophies", None)

    @property
    def trophy_highest(self):
        """Personal best."""
        if self.stats is not None:
            return self.stats.get("maxTrophies", None)
        return None

    @property
    def trophy_legendary(self):
        """Legendary trophies."""
        if self.stats is not None:
            return self.stats.get("legendaryTrophies", None)
        return None

    def trophy_value(self, emoji):
        """Trophy values.

        Current / Highest (PB)
        """
        return '{} / {} PB {}'.format(
            '{:,}'.format(self.trophy_current),
            '{:,}'.format(self.trophy_highest),
            emoji)

    @property
    def games(self):
        """Game stats."""
        return self.data.get("games", None)

    @property
    def wins(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("wins", None)
        return None

    @property
    def losses(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("losses", None)
        return None

    @property
    def draws(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("draws", None)
        return None

    def win_draw_losses(self, emoji):
        """Win / draw / losses."""
        return '{} / {} / {} {}'.format(
            '{:,}'.format(self.wins),
            '{:,}'.format(self.draws),
            '{:,}'.format(self.losses),
            emoji
        )

    @property
    def three_crown_wins(self):
        """Three crown wins."""
        if self.games is not None:
            return self.stats.get("threeCrownWins", 0)
        return 0

    @property
    def rank(self):
        """Global rank"""
        return self.data.get("globalRank", None)

    def rank_str(self, bot_emoji: BotEmoji):
        """Rank in ordinal format."""
        if self.rank is None:
            return "Unranked"
        p = inflect.engine()
        o = p.ordinal(self.rank)[-2:]
        return '{:,}{} {}'.format(self.rank, o, bot_emoji.name('rank'))

    @property
    def chest_cycle(self):
        """Chest cycle."""
        return self.data.get("chestCycle", None)

    @property
    def chest_cycle_position(self):
        """Chest cycle position."""
        if self.chest_cycle is not None:
            return self.chest_cycle.get("position", None)
        return None

    def chest_by_position(self, pos):
        """Return chest type based on position."""
        if pos == self.chest_cycle.get("superMagicalPos"):
            return "SuperMagical"
        elif pos == self.chest_cycle.get("legendaryPos"):
            return "Legendary"
        elif pos == self.chest_cycle.get("epicPos"):
            return "Epic"
        return CHESTS[pos % len(CHESTS)]

    def chests(self, count):
        """Next n chests."""
        return [self.chest_by_position(self.chest_cycle_position + i) for i in range(count)]

    @property
    def chest_super_magical_index(self):
        """Super magical index."""
        chest_pos = self.chest_cycle.get("superMagicalPos")
        return chest_pos - self.chest_cycle_position

    @property
    def chest_legendary_index(self):
        """Super magical index."""
        chest_pos = self.chest_cycle.get("legendaryPos")
        return chest_pos - self.chest_cycle_position

    @property
    def chest_epic_index(self):
        """Super magical index."""
        chest_pos = self.chest_cycle.get("epicPos")
        return chest_pos - self.chest_cycle_position

    @property
    def chest_magical_index(self):
        """First index of magical chest"""
        pos = self.chest_cycle_position
        start_pos = pos % len(CHESTS)
        chests = CHESTS[start_pos:]
        chests.extend(CHESTS)
        return chests.index('Magic')

    @property
    def chest_giant_index(self):
        """First index of magical chest"""
        pos = self.chest_cycle_position
        start_pos = pos % len(CHESTS)
        chests = CHESTS[start_pos:]
        chests.extend(CHESTS)
        return chests.index('Giant')

    @property
    def chests_opened(self):
        """Number of chests opened."""
        return self.chest_cycle_position

    def chest_list(self, bot_emoji: BotEmoji):
        """List of chests."""
        # chests
        next_chests = [bot_emoji.key(c) for c in self.chests(8)]
        special_chests = [
            ('Magic', self.chest_magical_index),
            ('Giant', self.chest_giant_index),
            ('Epic', self.chest_epic_index),
            ('Legendary', self.chest_legendary_index),
            ('SuperMagical', self.chest_super_magical_index)
        ]
        special_chests = sorted(special_chests, key=lambda c: c[1])

        out = []
        for c in self.chests(8):
            out.append(bot_emoji.key(c))

        # special chests
        for c in special_chests:
            out.append(bot_emoji.key(c[0]))
            out.append('{}'.format(c[1]))

        return ''.join(out)

        # chests
        # special chests
        # key_list = ['super_magical', 'legendary', 'epic']
        # chests = [(k, v) for k, v in self.chests.items() if k in key_list]
        # # giant magical
        # chests.append(('Giant', self.chest_giant_index))
        # chests.append(('Magic', self.chest_magical_index))
        # chests = sorted(chests, key=lambda c: c[1])
        #
        # cycle = [bot_emoji.key(c) for c in self.chests]
        # chest_out = ['{}{}'.format(bot_emoji.key(c[0]), c[1]) for c in chests]
        # chest_str = '{} . {}'.format(''.join(cycle), ' . '.join(chest_out))
        # return '{}{}'.format(
        #     ''.join(next_chests)
        # )

    @property
    def shop_offers_arena(self):
        """Get epic shop offer."""
        if hasattr(self, 'shop_offers'):
            return self.shop_offers.get('arena', -1)
        return -1

    @property
    def shop_offers_epic(self):
        """Get epic shop offer."""
        if hasattr(self, 'shop_offers'):
            return self.shop_offers.get('epic', -1)
        return -1

    @property
    def shop_offers_legendary(self):
        """Get epic shop offer."""
        if hasattr(self, 'shop_offers'):
            return self.shop_offers.get('legendary', -1)
        return -1

    def shop_list(self, bot_emoji: BotEmoji):
        """List of shop offers."""
        offers = [{
            # 'name': 'chestdraft',
            'name': 'shopgoblin',
            'index': self.shop_offers_arena
        }, {
            'name': 'chestepic',
            'index': self.shop_offers_epic
        }, {
            'name': 'chestlegendary',
            'index': self.shop_offers_legendary
        }]
        offers = [offer for offer in offers if offer['index'] > 0]
        offers = sorted(offers, key=lambda o: o['index'])
        out = ['{}{} days'.format(bot_emoji.name(o['name']), o['index']) for o in offers]
        return ' '.join(out)

    @property
    def win_ratio(self):
        """Win ratio."""
        return '{0:.3f}%'.format(
            (self.wins + self.draws * 0.5) / (self.wins + self.draws + self.losses) * 100)

    @property
    def arena(self):
        """League. Can be either Arena or league."""
        arenas = dataIO.load_json(os.path.join(PATH, 'arenas.json'))
        arenas = [CRArenaModel(**a) for a in arenas]
        arenas = sorted(arenas, key=lambda x: x.TrophyLimit, reverse=True)

        result = None
        for arena in arenas:
            if self.trophy_current >= arena.TrophyLimit:
                result = arena
                break

        return result

    @property
    def arena_text(self):
        """Arena text."""
        return self.arena.TIDText

    @property
    def arena_subtitle(self):
        """Arena subtitle"""
        return self.arena.SubtitleTIDText

    @property
    def league(self):
        """League (int)."""
        league = max(self.arena.Arena - 11, 0)
        return league

    def fave_card(self, bot_emoji: BotEmoji):
        """Favorite card in emoji and name."""
        emoji = self.api_cardname_to_emoji(self.favorite_card, bot_emoji)
        return '{} {}'.format(self.favorite_card, emoji)

    def arena_emoji(self, bot_emoji: BotEmoji):
        if self.league > 0:
            name = 'league{}'.format(self.league)
        else:
            name = 'arena{}'.format(self.arena.Arena)
        return bot_emoji.name(name)

    @property
    def arena_url(self):
        """Arena Icon URL."""
        if self.league > 0:
            url = 'http://smlbiobot.github.io/img/leagues/league{}.png'.format(self.league)
        else:
            url = 'http://smlbiobot.github.io/img/arenas/arena-{}.png'.format(self.arena.Arena)
        return url

    def deck_list(self, bot_emoji: BotEmoji):
        """Deck with emoji"""
        cards = [card["name"] for card in self.deck]
        cards = [self.api_cardname_to_emoji(name, bot_emoji) for name in cards]
        levels = [card["level"] for card in self.deck]
        deck = ['{0[0]}{0[1]}'.format(card) for card in zip(cards, levels)]
        return ' '.join(deck)

    def api_cardname_to_emoji(self, name, bot_emoji: BotEmoji):
        """Convert api card id to card emoji."""
        cr = dataIO.load_json(os.path.join(PATH, "clashroyale.json"))
        cards = cr["Cards"]
        result = None
        for crid, o in cards.items():
            if o["api_id"] == name:
                result = crid
                break
        if result is None:
            return None
        result = result.replace('-', '')
        return bot_emoji.name(result)


class Settings:
    """Cog settings.

    Functionally the CRClan cog model.
    """

    DEFAULTS = {
        "profile_api_url": {},
        "servers": {},
    }

    SERVER_DEFAULTS = {
        "show_resources": False,
        "players": {}
    }

    def __init__(self, bot, filepath):
        """Init."""
        self.bot = bot
        self.filepath = filepath
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(filepath))

        # arenas
        arenas = dataIO.load_json(os.path.join(PATH, 'arenas.json'))
        self.arenas = [CRArenaModel(**a) for a in arenas]
        self.arenas = sorted(self.arenas, key=lambda x: x.TrophyLimit, reverse=True)

    def init_server(self, server):
        """Initialized server settings.

        This will wipe all clan data and player data.
        """
        self.settings["servers"][server.id] = self.SERVER_DEFAULTS
        self.save()

    def init_players(self, server):
        """Initialized clan settings."""
        self.settings["servers"][server.id]["players"] = {}
        self.save()

    def check_server(self, server):
        """Make sure server exists in settings."""
        if server.id not in self.settings["servers"]:
            self.settings["servers"][server.id] = self.SERVER_DEFAULTS
        self.save()

    def get_players(self, server):
        """CR Players settings by server."""
        return self.settings["servers"][server.id]["players"]

    def save(self):
        """Save data to disk."""
        dataIO.save_json(self.filepath, self.settings)

    def set_player(self, server, member, tag):
        """Associate player tag with Discord member.

        If tag already exists for member, overwrites it.
        """
        self.check_server(server)
        tag = SCTag(tag).tag
        if "players" not in self.settings["servers"][server.id]:
            self.settings["servers"][server.id]["players"] = {}
        players = self.settings["servers"][server.id]["players"]
        players[member.id] = tag
        self.settings["servers"][server.id]["players"] = players
        self.save()

    def tag2member(self, server, tag):
        """Return Discord member from player tag."""
        try:
            players = self.settings["servers"][server.id]["players"]
            for member_id, player_tag in players.items():
                if player_tag == tag:
                    return server.get_member(member_id)
        except KeyError:
            pass
        return None

    def server_settings(self, server):
        """Return server settings."""
        return self.settings["servers"][server.id]

    async def player_data(self, tag):
        """Return CRPlayerModel by tag."""
        tag = SCTag(tag).tag
        # url = "{}{}".format(self.profile_api_url, tag)
        url = 'http://api.cr-api.com/profile/{}'.format(tag)

        # headers = {'authorization': self.profile_api_token}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=API_FETCH_TIMEOUT) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise
        except asyncio.TimeoutError:
            raise

        file_path = self.cached_filepath(tag)
        dataIO.save_json(file_path, data)

        return CRPlayerModel(data=data)

    def cached_player_data(self, tag):
        """Return cached data by tag."""
        file_path = self.cached_filepath(tag)
        if not os.path.exists(file_path):
            return None
        data = dataIO.load_json(file_path)
        return CRPlayerModel(is_cache=True, data=data)

    def cached_player_data_timestamp(self, tag):
        """Return timestamp in days-since format of cached data."""
        file_path = self.cached_filepath(tag)
        timestamp = dt.datetime.fromtimestamp(os.path.getmtime(file_path))

        passed = dt.datetime.now() - timestamp

        days = passed.days
        hours, remainder = divmod(passed.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        p = inflect.engine()

        days_str = '{} {} '.format(days, p.plural("day", days)) if days > 0 else ''
        passed_str = (
            '{days} {hours} {hr} {minutes} {mn} {seconds} {sec} ago'
        ).format(
            days=days_str,
            hours=hours,
            hr=p.plural("hour", hours),
            minutes=minutes,
            mn=p.plural("minute", minutes),
            seconds=seconds,
            sec=p.plural("second", seconds)
        )

        return passed_str

    @staticmethod
    def cached_filepath(tag):
        """Cached clan data file path"""
        return os.path.join(PATH_PLAYERS, '{}.json'.format(tag))

    def member2tag(self, server, member):
        """Return player tag from member."""
        try:
            players = self.settings["servers"][server.id]["players"]
            for member_id, player_tag in players.items():
                if member_id == member.id:
                    return player_tag
        except KeyError:
            pass
        return None

    def trophy2arena(self, trophy):
        """Convert trophy to league based on Arenas."""
        result = None
        for arena in self.arenas:
            if trophy >= arena.TrophyLimit:
                result = arena
                break

        if result is not None:
            return '{}: {}'.format(result.TIDText, result.SubtitleTIDText)

        return ''

    def emoji(self, name=None, key=None):
        """Chest emojis by api key name or key.

        name is used by this cog.
        key is values returned by the api.
        Use key only if name is not set
        """
        emojis = {
            'Silver': 'chestsilver',
            'Gold': 'chestgold',
            'Giant': 'chestgiant',
            'Magic': 'chestmagical',
            'super_magical': 'chestsupermagical',
            'legendary': 'chestlegendary',
            'epic': 'chestepic'
        }
        if name is None:
            if key in emojis:
                name = emojis[key]
        for server in self.bot.servers:
            for emoji in server.emojis:
                if emoji.name == name:
                    return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    @property
    def profile_api_url(self):
        """Clan API URL."""
        return self.settings["profile_api_url"]

    @profile_api_url.setter
    def profile_api_url(self, value):
        """Set Clan API URL."""
        self.settings["profile_api_url"] = value
        self.save()

    @property
    def profile_api_token(self):
        """Profile API Token."""
        return self.settings.get("profile_api_token", None)

    @profile_api_token.setter
    def profile_api_token(self, value):
        """Set Profile API Token."""
        self.settings["profile_api_token"] = value
        self.save()

    @property
    def badge_url(self):
        """Clan Badge URL."""
        return self.settings.get("badge_url", None)

    @badge_url.setter
    def badge_url(self, value):
        """lan Badge URL"""
        self.settings["badge_url"] = value
        self.save()

    def set_resources(self, server, value):
        """Show gold/gems or not."""
        self.settings[server.id]["show_resources"] = value

    def show_resources(self, server):
        """Show gold/gems or not."""
        try:
            return self.settings[server.id]["show_resources"]
        except KeyError:
            return False


# noinspection PyUnusedLocal
class CRProfile:
    """Clash Royale player profile."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.model = Settings(bot, JSON)
        self.bot_emoji = BotEmoji(bot)

    async def player_data(self, tag):
        """Return CRPlayerModel by tag."""
        data = await self.model.player_data(tag)
        return data

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def crprofileset(self, ctx):
        """Clash Royale clan management API.

        Requires: Clash Royale API access by Selfish.
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crprofileset.command(name="initserver", pass_context=True)
    async def crprofileset_initserver(self, ctx):
        """Init CR Clan: server settings."""
        server = ctx.message.server
        self.model.init_server(server)
        await self.bot.say("Server settings initialized.")

    @crprofileset.command(name="initplayers", pass_context=True)
    async def crprofileset_initplayers(self, ctx):
        """Init CR Clan: players settings."""
        server = ctx.message.server
        self.model.init_players(server)
        await self.bot.say("Clan settings initialized.")

    @crprofileset.command(name="profileapi", pass_context=True)
    async def crprofileset_profileapi(self, ctx, url):
        """CR Clan API URL base.

        Format:
        If path is http://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.model.profile_api_url = url
        await self.bot.say("Profile API URL updated.")

    @crprofileset.command(name="badgeurl", pass_context=True)
    async def crprofileset_badgeurl(self, ctx, url):
        """badge URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.model.badge_url = url
        await self.bot.say("Badge URL updated.")

    @crprofileset.command(name="apitoken", pass_context=True)
    async def crprofileset_apiauth(self, ctx, token):
        """API Authentication token."""
        self.model.profile_api_token = token
        await self.bot.say("API token save.")

    @crprofileset.command(name="resources", pass_context=True)
    async def crprofileset_resources(self, ctx, enable: bool):
        """Show gold/gems in profile."""
        self.model.set_resources(ctx.message.server, enable)
        await self.bot.say(
            "CR profiles {} show resources.".format('will' if enable else 'will not')
        )

    @commands.group(pass_context=True, no_pm=True)
    async def crprofile(self, ctx):
        """Clash Royale Player Profile."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crprofile.command(name="settag", pass_context=True, no_pm=True)
    async def crprofile_settag(
            self, ctx, playertag, member: discord.Member = None):
        """Set playertag to discord member.

        Setting tag for yourself:
        !crprofile settag C0G20PR2

        Setting tag for others (requires Bot Commander role):
        !crprofile settag C0G20PR2 SML
        !crprofile settag C0G20PR2 @SML
        !crprofile settag C0G20PR2 @SML#6443
        """
        server = ctx.message.server
        author = ctx.message.author

        sctag = SCTag(playertag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        allowed = False
        if member is None:
            allowed = True
        elif member.id == author.id:
            allowed = True
        else:
            botcommander_roles = [
                discord.utils.get(
                    server.roles, name=r) for r in BOTCOMMANDER_ROLES]
            botcommander_roles = set(botcommander_roles)
            author_roles = set(author.roles)
            if len(author_roles.intersection(botcommander_roles)):
                allowed = True

        if not allowed:
            await self.bot.say("Only Bot Commanders can set tags for others.")
            return

        if member is None:
            member = ctx.message.author

        self.model.set_player(server, member, sctag.tag)

        await self.bot.say(
            "Associated player tag #{} with Discord Member {}.".format(
                sctag.tag, member.display_name
            ))

    @crprofile.command(name="gettag", pass_context=True, no_pm=True)
    async def crprofile_gettag(self, ctx, member: discord.Member = None):
        """Get playertag from Discord member."""
        server = ctx.message.server
        author = ctx.message.author
        if member is None:
            member = author
        tag = self.model.member2tag(server, member)
        if tag is None:
            await self.bot.say("Cannot find associated player tag.")
            return
        await self.bot.say(
            "Player tag for {} is #{}".format(
                member.display_name, tag))

    @crprofile.command(name="tag", pass_context=True, no_pm=True)
    async def crprofile_tag(self, ctx, tag):
        """Player profile by tag

        Display player info
        """
        await self.bot.type()
        sctag = SCTag(tag)

        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        await self.display_profile(ctx, tag)

    @crprofile.command(name="get", pass_context=True, no_pm=True)
    async def crprofile_get(self, ctx, member: discord.Member = None):
        """Player profile

        if member is not entered, retrieve own profile
        """
        await self.bot.type()
        author = ctx.message.author
        server = ctx.message.server
        resources = False

        if member is None:
            member = author
            if self.model.show_resources(server):
                resources = True

        tag = self.model.member2tag(server, member)

        if tag is None:
            await self.bot.say(
                "{} has not set player tag with the bot yet. "
                "Run `!crsettag [tag]` to set your tag.".format(member.display_name)
            )
            return
        await self.display_profile(ctx, tag, resources=resources)

    async def display_profile(self, ctx, tag, resources=False):
        """Display profile."""
        sctag = SCTag(tag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        try:
            player_data = await self.model.player_data(sctag.tag)
        except json.decoder.JSONDecodeError:
            player_data = self.model.cached_player_data(tag)
        except asyncio.TimeoutError:
            player_data = self.model.cached_player_data(tag)

        if player_data is None:
            await self.bot.say("Unable to load from API.")
            return
        if player_data.is_cache:
            await self.bot.send_message(
                ctx.message.channel,
                (
                    "Unable to load from API. "
                    "Showing cached data from: {}.".format(
                        self.model.cached_player_data_timestamp(tag))
                )
            )

        server = ctx.message.server
        for em in self.embeds_profile(player_data, server=server, resources=resources):
            await self.bot.say(embed=em)
            # await self.bot.send_message(ctx.message.channel, embed=em)

    def embeds_profile(self, player: CRPlayerModel, server=None, resources=False):
        """Return Discord Embed of player profile."""
        embeds = []
        color = random_discord_color()
        bem = self.bot_emoji.name

        # emoji_xp = self.model.emoji(name="experience")
        member = self.model.tag2member(server, player.tag)
        mention = '_'
        if member is not None:
            mention = member.mention

        profile_url = 'http://cr-api.com/profile/{}'.format(player.tag)
        clan_url = 'http://cr-api.com/clan/{}'.format(player.clan_tag)

        # header
        title = player.name
        description = (
            '[{player_tag}]({profile_url})\n'
            '**[{clan_name}]({clan_url})**\n'
            '[{clan_tag}]({clan_url})\n'
            '{clan_role}'
        ).format(
            player_tag=player.tag,
            profile_url=profile_url,
            clan_name=player.clan_name,
            clan_tag=player.clan_tag,
            clan_url=clan_url,
            clan_role=player.clan_role
        )
        em = discord.Embed(title=title, description=description, color=color, url=profile_url)
        em.set_thumbnail(url=player.clan_badge_url)
        header = {
            'Trophies': player.trophy_value(bem('trophy')),
            player.arena_text: '{} {}'.format(player.arena_subtitle, player.arena_emoji(self.bot_emoji)),
            'Rank': player.rank_str(self.bot_emoji),
            'Discord': mention
        }
        for k, v in header.items():
            em.add_field(name=k, value=v)
        embeds.append(em)

        # trophies
        em = discord.Embed(title=" ", color=color)

        def fmt(num, emoji_name):
            emoji = bem(emoji_name)
            return '{:,} {}'.format(num, emoji)

        stats = {
            'Wins / Draws / Losses': player.win_draw_losses(bem('battle')),
            'Win Ratio': '{} {}'.format(player.win_ratio, bem('battle')),
            'Three-Crown Wins': fmt(player.three_crown_wins, 'crownblue'),
            'Challenge Cards Won': fmt(player.challenge_cards_won, 'tournament'),
            'Tourney Cards Won': fmt(player.tourney_cards_won, 'tournament'),
            'Total Donations': fmt(player.total_donations, 'cards'),
            'Level': fmt(player.level, 'experience'),
            'Experience': '{} {}'.format(player.xp_str, bem('experience')),
            'Cards Found': fmt(player.cards_found, 'cards'),
            'Favorite Card': player.fave_card(self.bot_emoji)
        }
        for k, v in stats.items():
            em.add_field(name=k, value=v)

        print("supermagical", player.chest_super_magical_index)
        print("legendary", player.chest_legendary_index)
        print("epic", player.chest_epic_index)
        print("magical", player.chest_magical_index)
        print("giant", player.chest_giant_index)
        print(player.chest_list(self.bot_emoji))
        # print("chests", player.chests('Magic'))

        # # chests
        chest_name = 'Chests ({:,} opened)'.format(player.chests_opened)
        em.add_field(name=chest_name, value=player.chest_list(self.bot_emoji), inline=False)
        #
        # # deck
        # em.add_field(name="Deck", value=player.deck_list(self.bot_emoji), inline=False)
        #
        # # shop offers
        # em.add_field(name="Shop Offers", value=player.shop_list(self.bot_emoji), inline=False)

        # link to cr-api.com
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')

        embeds.append(em)
        return embeds

    @crprofile.command(name="trophy2arena", aliases=['t2a'], pass_context=True, no_pm=True)
    async def crprofile_trophy2arena(self, ctx, trophy: int):
        """Convert trophies to arenas."""
        text = self.model.trophy2arena(trophy)
        await self.bot.say(text)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)
    if not os.path.exists(PATH_PLAYERS):
        os.makedirs(PATH_PLAYERS)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = CRProfile(bot)
    bot.add_cog(n)
