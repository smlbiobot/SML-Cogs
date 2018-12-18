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
import itertools
import math
from collections import OrderedDict, defaultdict

import aiohttp
import datetime as dt
import discord
import inflect
import json
import os
import requests
import socket
import urllib.request
from datetime import timedelta
from discord.ext import commands
from random import choice

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "crprofile")
PATH_PLAYERS = os.path.join(PATH, "players")
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")
CHESTS = dataIO.load_json(os.path.join('data', 'crprofile', 'chests.json'))

DATA_UPDATE_INTERVAL = timedelta(minutes=30).seconds

API_FETCH_TIMEOUT = 10

BOTCOMMANDER_ROLES = ["Bot Commander"]

CREDITS = 'Selfish + SML'

CARDS = None


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


def get_card_rarity(card):
    rarity = card.get('rarity')
    if rarity is not None:
        return rarity
    global CARDS
    if CARDS is None:
        with urllib.request.urlopen("https://royaleapi.github.io/cr-api-data/json/cards.json") as r:
            CARDS = json.loads(r.read().decode())
    for c in CARDS:
        if c.get('name') == card.get('name'):
            return c.get('rarity')
    return None


def normalized_card_level(card):
    """Card common levels (september update)."""
    rarity2level = dict(
        Common=0,
        Rare=2,
        Epic=5,
        Legendary=8
    )
    return card.get('level', 0) + rarity2level.get(get_card_rarity(card), 0)

def inline(s, fmt):
    """Wrap string with inline escape"""
    return "`\u200B{}\u200B`".format(fmt.format(s))


class API:
    """Clash Royale official API."""

    @staticmethod
    def player(tag):
        """Return player URL"""
        return "https://api.royaleapi.com/player/" + tag.upper()


class Constants:
    """API Constants."""

    __instance = None

    def __init__(self):
        if Constants.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Constants.__instance = self
        self._cards = None
        self._alliance_badges = None
        self._rarities = None
        self._arenas = None

    @staticmethod
    def get_instance():
        if Constants.__instance is None:
            Constants()
        return Constants.__instance

    @property
    def cards(self):
        if self._cards is None:
            r = requests.get('https://royaleapi.github.io/cr-api-data/json/cards.json')
            self._cards = r.json()
        return self._cards

    @property
    def rarities(self):
        if self._rarities is None:
            r = requests.get('https://royaleapi.github.io/cr-api-data/json/rarities.json')
            self._rarities = r.json()
        return self._rarities

    @property
    def alliance_badges(self):
        if self._alliance_badges is None:
            r = requests.get('https://royaleapi.github.io/cr-api-data/json/alliance_badges.json')
            self._alliance_badges = r.json()
        return self._alliance_badges

    @property
    def arenas(self):
        if self._arenas is None:
            r = requests.get('https://royaleapi.github.io/cr-api-data/json/arenas.json')
            self._arenas = r.json()
        return self._arenas

    def badge_id_to_url(self, id):
        for badge in self.alliance_badges:
            if badge['badge_id'] == id:
                return "https://royaleapi.github.io/cr-api-assets/badges/{}.png".format(badge['name'])
        return None

    def get_card(self, id=None, name=None):
        for card in self.cards:
            if id is not None:
                if card.get('id') == id:
                    return card
            if name is not None:
                if card.get('name') == name:
                    return card
        return None

    def get_arena(self, id=None):
        for arena in self.arenas:
            if id is not None:
                if arena.get('id') == id:
                    return arena
        return None


class BotEmoji:
    """Emojis available in bot."""

    def __init__(self, bot):
        self.bot = bot
        self.map = {
            'silver': 'chestsilver',
            'gold': 'chestgold',
            'golden': 'chestgold',
            'giant': 'chestgiant',
            'magic': 'chestmagical',
            'magical': 'chestmagical',
            'supermagical': 'chestsupermagical',
            'legendary': 'chestlegendary',
            'epic': 'chestepic',
            'silver chest': 'chestsilver',
            'golden chest': 'chestgold',
            'giant chest': 'chestgiant',
            'magical chest': 'chestmagical',
            'super magical chest': 'chestsupermagical',
            'legendary chest': 'chestlegendary',
            'epic chest': 'chestepic',
            'mega lightning chest': 'chestmegalightning',
        }

    def name(self, name):
        """Emoji by name."""
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    def key(self, key):
        """Chest emojis by api key name or key.

        name is used by this cog.
        key is values returned by the api.
        Use key only if name is not set
        """
        key = key.lower()
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


class CRPlayerModel:
    """Clash Royale player model."""

    def __init__(self, is_cache=False, data=None, error=False, api_provider=None):
        """Init.

        Params:
        data: dict from JSON
        is_cache: True is data is cached (flag)
        CHESTS: chest cycle from apk
        """
        self.data = data
        self.is_cache = is_cache
        self.CHESTS = CHESTS
        self.error = error
        self.info_data = data.get('info')
        self.chests_data = data.get('chests')

        if api_provider is None:
            self.api_provider = 'cr-api'
        else:
            self.api_provider = api_provider

    def prop(self, section, prop, default=0):
        """Return sectional attribute."""
        attr = self.info_data.get(section)
        if attr is not None:
            value = attr.get(prop)
            if value is not None:
                return value
        return default

    @property
    def tag(self):
        """Player tag"""
        t = self.info_data.get("tag", None)
        t = t.upper()
        t = t.replace('#', '')
        return t

    @property
    def name(self):
        """IGN."""
        return self.info_data.get("name", None)

    @property
    def trophies(self):
        """Trophies."""
        return self.info_data.get("trophies", None)

    @property
    def clan(self):
        """Clan."""
        return self.info_data.get("clan", None)

    @property
    def not_in_clan(self):
        """Not in clan flag."""
        return self.clan is None

    @property
    def clan_name(self):
        """Clan name."""
        if self.not_in_clan:
            return "No Clan"
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
        if self.not_in_clan:
            return "N/A"
        if self.api_provider == 'official':
            return self.info_data.get('role')
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
        if self.not_in_clan:
            return "http://smlbiobot.github.io/img/emblems/NoClan.png"
        try:
            return self.clan['badge']['image']
        except KeyError:
            pass
        return ''

    @property
    def stats(self):
        """Stats."""
        return self.info_data.get("stats", None)

    @property
    def challenge_cards_won(self):
        """Challenge cards won."""
        if self.api_provider == 'official':
            return self.info_data.get('challengeCardsWon', 0)
        return self.prop("stats", "challengeCardsWon", 0)

    @property
    def tourney_cards_won(self):
        """Challenge cards won."""
        if self.api_provider == 'official':
            return self.info_data.get('tournamentCardsWon', 0)
        return self.prop("stats", "tournamentCardsWon", 0)

    @property
    def tourney_cards_per_game(self):
        """Number of tournament cards won per game played."""
        if self.tourney_games:
            return self.tourney_cards_won / self.tourney_games
        return None

    @property
    def challenge_max_wins(self):
        """Max challenge wins."""
        if self.api_provider == 'official':
            return self.info_data.get('challengeMaxWins', 0)
        return self.prop("stats", "challengeMaxWins", 0)

    @property
    def total_donations(self):
        """Total donations."""
        if self.api_provider == 'official':
            return self.info_data.get('totalDonations', 0)
        return self.prop("stats", "totalDonations", 0)

    @property
    def cards_found(self):
        """Cards found."""
        if self.api_provider == 'official':
            return len(self.info_data.get('cards'))
        return self.prop("stats", "cardsFound", 0)

    @property
    def favorite_card(self):
        """Favorite card."""
        if self.api_provider == 'official':
            card = self.info_data.get('currentFavouriteCard')
            card = Constants.get_instance().get_card(name=card.get('name'))
            return card
        return self.prop("stats", "favoriteCard", "soon")

    @property
    def trophy_current(self):
        """Current trophies."""
        return self.info_data.get("trophies", 0)

    @property
    def trophy_highest(self):
        """Personal best."""
        if self.api_provider == 'official':
            return self.info_data.get('bestTrophies', 0)
        return self.prop("stats", "maxTrophies", 0)

    @property
    def trophy_legendary(self):
        """Legendary trophies."""
        return self.prop("stats", "legendaryTrophies", 0)

    def trophy_value(self, emoji):
        """Trophy values.

        Current / Highest (PB)
        """
        return '{} / {} PB {}'.format(
            '{:,}'.format(self.trophy_current),
            '{:,}'.format(self.trophy_highest),
            emoji)

    @property
    def level(self):
        """XP Level."""
        if self.api_provider == 'official':
            return self.info_data.get('expLevel')
        return self.prop("stats", "level", 0)

    @property
    def games(self):
        """Game stats."""
        return self.info_data.get("games")

    @property
    def tourney_games(self):
        """Number of tournament games."""
        if self.api_provider == 'official':
            return self.info_data.get('tournamentBattleCount', 0)
        return self.prop("games", "tournamentGames", 0)

    @property
    def wins(self):
        """Games won."""
        if self.api_provider == 'official':
            return self.info_data.get('wins', 0)
        return self.prop("games", "wins", 0)

    @property
    def losses(self):
        """Games won."""
        if self.api_provider == 'official':
            return self.info_data.get('losses', 0)
        return self.prop("games", "losses", 0)

    @property
    def draws(self):
        """Games won."""
        return self.prop("games", "draws", 0)

    def win_losses(self, emoji):
        """Win / losses."""
        return '{} / {} {}'.format(
            '{:,}'.format(self.wins),
            '{:,}'.format(self.losses),
            emoji
        )

    @property
    def total_games(self):
        """Total games played."""
        if self.api_provider == 'official':
            return self.info_data.get('battleCount', 0)
        return self.prop("games", "total", 0)

    @property
    def win_streak(self):
        """Win streak."""
        return max(self.prop("games", "currentWinStreak", 0), 0)

    @property
    def three_crown_wins(self):
        """Three crown wins."""
        if self.api_provider == 'official':
            return self.info_data.get('threeCrownWins')
        return self.prop("stats", "threeCrownWins", 0)

    """
        Rank.
        """

    @property
    def league_statistics(self):
        return self.info_data.get("leagueStatistics")

    @property
    def current_season(self):
        if self.league_statistics:
            return self.league_statistics.get('currentSeason')
        return None

    @property
    def current_season_rank(self):
        if self.current_season:
            return self.current_season.get('rank')
        return None

    @property
    def rank(self):
        """Global rank"""
        return self.current_season_rank

    def rank_ord_str(rank):
        """Rank in ordinal format."""
        if rank is not None:
            p = inflect.engine()
            o = p.ordinal(rank)[-2:]
            return '{:,}{}'.format(rank, o)
        return 'Unranked'

    @property
    def rank_ord(self):
        """Rank in ordinal format."""
        return self.rank_ord_str(self.rank)

    def rank_str(self, bot_emoji: BotEmoji):
        """Rank in ordinal format."""
        if self.rank is None:
            return "Unranked"
        p = inflect.engine()
        o = p.ordinal(self.rank)[-2:]
        return '{:,}{} {}'.format(self.rank, o, bot_emoji.name('rank'))

    """
    Chests.
    """

    def chest_list(self, bot_emoji: BotEmoji):
        """List of chests."""
        # chests
        chest_cycle = self.chests_data

        if chest_cycle is None:
            return ""

        if self.api_provider == 'official':
            out = []
            for c in chest_cycle.get('items'):
                out.append(bot_emoji.key(c.get('name', '').lower()))
                out.append(str(c.get('index', 0) + 1))

            return ' '.join(out)

        else:

            upcoming = chest_cycle.get("upcoming")
            special_chests = [(k, v) for k, v in chest_cycle.items() if k != "upcoming"]
            special_chests = sorted(special_chests, key=lambda x: x[1])

            out = []
            if upcoming is not None:
                for c in upcoming:
                    out.append(bot_emoji.key(c.lower()))

            for k, v in special_chests:
                out.append(bot_emoji.key(k) + str(v + 1))

            return ''.join(out)

    @property
    def win_ratio(self):
        """Win ratio.

        Draws reported by API includes 2v2, so we remove those data
        """
        # return (self.wins + self.draws * 0.5) / (self.wins + self.draws + self.losses)
        return self.wins / (self.wins + self.losses)

    @property
    def arena(self):
        """League. Can be either Arena or league."""
        if self.api_provider == 'official':
            a_id = self.info_data.get('arena', {}).get('id')
            if a_id is None:
                return None
            return Constants.get_instance().get_arena(id=a_id)
        try:
            return self.info_data.get('arena', {}).get('arena')
        except KeyError:
            return None

    @property
    def arena_text(self):
        """Arena text."""
        if self.api_provider == 'official':
            return self.arena.get('title')
        try:
            return self.info_data.get('arena', {}).get('name')
        except KeyError:
            return None

    @property
    def arena_subtitle(self):
        """Arena subtitle"""
        if self.api_provider == 'official':
            return self.arena.get('subtitle')
        try:
            return self.info_data.get('arena', {}).get('arena')
        except KeyError:
            return None

    @property
    def arena_id(self):
        """Arena ID."""
        if self.api_provider == 'official':
            return self.arena.get('arena_id')

        else:
            return self.info_data.get('arena', {}).get('arenaID')

    @property
    def arean_url(self):
        """Arena image URL"""
        return 'https://royaleapi.github.io/cr-api-assets/arenas/arena{}.png'.format(self.arena_arena)

    @property
    def league(self):
        """League (int)."""
        league = max(self.arena_id - 12, 0)
        return league

    def fave_card(self, bot_emoji: BotEmoji):
        """Favorite card in emoji and name."""
        emoji = bot_emoji.name(self.favorite_card['key'].replace('-', ''))
        return '{} {}'.format(self.favorite_card['name'], emoji)

    def arena_emoji(self, bot_emoji: BotEmoji):
        if self.league > 0:
            name = 'league{}'.format(self.league)
        else:
            name = 'arena{}'.format(self.arena_id)
        return bot_emoji.name(name)

    @property
    def arena_arena(self):
        if self.api_provider == 'official':
            return self.arena.get('arena')

        else:
            return self.info_data.get('arena', {}).get('arena')

    @property
    def arena_url(self):
        """Arena Icon URL."""
        if self.api_provider == 'official':
            return 'https://royaleapi.github.io/cr-api-assets/arenas/arena{}.png'.format(self.arena_arena)
        if self.league > 0:
            url = 'https://royaleapi.github.io/cr-api-assets/arenas/league{}.png'.format(self.league)
        else:
            url = 'https://royaleapi.github.io/cr-api-assets/arenas/arena{}.png'.format(self.arena.Arena)
        return url

    def deck_list(self, bot_emoji: BotEmoji):
        """Deck with emoji"""
        if self.api_provider == 'official':
            deck_data = self.info_data.get('currentDeck')
            cards = [Constants.get_instance().get_card(name=c.get('name')).get('key') for c in deck_data]
        else:
            cards = [card.get('key') for card in self.info_data.get("currentDeck")]
        cards = [bot_emoji.name(key.replace('-', '')) for key in cards]
        levels = [normalized_card_level(card) for card in self.info_data.get("currentDeck")]
        deck = ['{0[0]}{0[1]}'.format(card) for card in zip(cards, levels)]
        return ' '.join(deck)

    def trade_list(self, bot_emoji: BotEmoji):
        """Trade list"""
        d = dict(
            Legendary=1,
            Epic=10,
            Rare=50,
            Common=250
        )

        cards = dict(
            Legendary=[],
            Epic=[],
            Rare=[],
            Common=[]
        )

        for card in self.cards:
            for rarity in d.keys():
                limit = d.get(card.get('rarity'), 0)
                if card.get('rarity') == rarity:
                    if limit:
                        trade_count = math.floor(card.get('count', 0) / limit)

                        # First card can’t be traded if level 1
                        if card.get('level') == 1:
                            trade_count -= 1

                        # Trade cards
                        if trade_count > 0:
                            cards[rarity].append(dict(
                                emoji=bot_emoji.name(card.get('key').replace('-', '')),
                                count="x{}".format(trade_count)
                                # count=inline(trade_count, "x{:2}") + " "
                            ))

                        # max cards
                        if card.get('level') == card.get('maxLevel'):
                            cards[rarity].append(dict(
                                emoji=bot_emoji.name(card.get('key').replace('-', '')),
                                count="M"
                                # count=inline(trade_count, " M ") + " "
                            ))
        ret = {}
        groups = {}
        for k, v in cards.items():
            groups[k] = 0

        for k, v in cards.items():
            groups = grouper(5, v)
            ret[k] = []
            for group in groups:
                ret[k].extend(['{0[emoji]}{0[count]}'.format(card) for card in group if card is not None])

        return ret

    @property
    def decklink(self):
        return self.info_data.get('deckLink', '')

    def api_cardname_to_emoji(self, name, bot_emoji: BotEmoji):
        """Convert api card id to card emoji."""
        cr = dataIO.load_json(os.path.join(PATH, "clashroyale.json"))
        cards = cr["Cards"]
        result = None
        for crid, o in cards.items():
            if o["sfid"] == name:
                result = crid
                break
        if result is None:
            return None
        result = result.replace('-', '')
        return bot_emoji.name(result)

    """
    Seasons
    """

    @property
    def seasons(self):
        """Season finishes."""
        s_list = []
        for s in self.info_data.get("previousSeasons"):
            s_list.append({
                "number": s.get("seasonNumber", None),
                "highest": s.get("seasonHighest", None),
                "ending": s.get("seasonEnding", None),
                "rank": s.get("seasonEndGlobalRank", None)
            })
        s_list = sorted(s_list, key=lambda s: s["number"])
        return s_list

    """
    Card Collection
    """

    @property
    def cards(self):
        """Card collection."""
        if self.api_provider == 'official':
            cards_data = self.info_data.get('cards', [])
            for c in cards_data:
                c.update(Constants.get_instance().get_card(name=c.get('name')))
            return cards_data
        return self.info_data.get("cards")

    def card_collection(self, bot_emoji):

        sort_rarities = {
            'common': 1,
            'rare': 2,
            'epic': 3,
            'legendary': 4
        }
        cards = self.cards
        cards = sorted(cards, key=lambda x: (sort_rarities[x.get('rarity', '').lower()] or 0, x.get('elixir', 0)))

        out = []
        for card in cards.copy():
            key = card.get('key')
            key = key.replace('-', '')
            card['emoji'] = bot_emoji.name(key)

            out.append({
                'emoji': bot_emoji.name(key),
                'level': card['level'],
                'count': card['count'],
                'rarity': card['rarity']
            })

        return out

    def upgrades(self, rarity, count, level):
        rarities = Constants.get_instance().rarities
        data = None
        for r in rarities:
            if rarity == r['name']:
                data = r
                break

        is_max = level == data['level_count']

        upgrade_req = data["upgrade_material_count"][level - 1]

        if is_max:
            percent = 100
            progress_color = "red"
            upgrade_str = "{} / MAX".format(count)
        else:
            count_str = "{:,}".format(count)
            percent = min(100, count / upgrade_req * 100)
            if percent == 100:
                progress_color = 'green'
            else:
                progress_color = 'blue'
            upgrade_str = "{} / {:,}".format(count_str, upgrade_req)
        return {
            "upgrade_str": upgrade_str,
            "percent": percent,
            "progress_color": progress_color
        }


class Settings:
    """Cog settings.

    Functionally the CRProfile cog model.
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

    def rm_player_tag(self, server, member=None, tag=None):
        """Remove player tag from settings."""
        self.check_server(server)
        if member is not None:
            try:
                self.settings["servers"][server.id]["players"].pop(member.id, None)
            except KeyError:
                pass
            self.save()
        if tag is not None:
            try:
                players = self.settings["servers"][server.id]["players"].copy()
                for member_id, player_tag in players.items():
                    if player_tag == tag:
                        self.settings["servers"][server.id]["players"].pop(member_id, None)
            except KeyError:
                pass
            self.save()

    def rm_tag(self, server, tag):
        """Remove player tag from settings by tag"""

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

        error = False
        data = {
            'info': {},
            'chests': {}
        }

        if self.api_provider == 'official':
            info_url = 'https://api.clashroyale.com/v1/players/%23{}'.format(tag)
            chest_url = 'https://api.clashroyale.com/v1/players/%23{}/upcomingchests'.format(tag)
            headers = {"Authorization": 'Bearer {}'.format(self.official_auth)}
        else:
            info_url = 'https://api.royaleapi.com/player/{}'.format(tag)
            chest_url = 'https://api.royaleapi.com/player/{}/chests'.format(tag)
            headers = {"Authorization": 'Bearer {}'.format(self.auth)}

        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )

        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                for url in [info_url, chest_url]:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            error = True
                        else:
                            if url == info_url:
                                data['info'] = await resp.json()
                            elif url == chest_url:
                                data['chests'] = await resp.json()

        except json.decoder.JSONDecodeError:
            raise
        except asyncio.TimeoutError:
            raise

        return CRPlayerModel(data=data, error=error, api_provider=self.api_provider)

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
        """Profile API URL."""
        return self.settings["profile_api_url"]

    @profile_api_url.setter
    def profile_api_url(self, value):
        """Set Profile API URL."""
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
        return self.settings.get("badge_url_base", None)

    @badge_url.setter
    def badge_url(self, value):
        """lan Badge URL"""
        self.settings["badge_url_base"] = value
        self.save()

    @property
    def auth(self):
        """Authentication token"""
        return self.settings.get("auth")

    @auth.setter
    def auth(self, value):
        """Set authentication token."""
        self.settings["auth"] = value
        self.save()

    @property
    def official_auth(self):
        """Authentication token"""
        return self.settings.get("official_auth")

    @official_auth.setter
    def official_auth(self, value):
        """Set authentication token."""
        self.settings["official_auth"] = value
        self.save()

    @property
    def api_provider(self):
        """API provider. Can use either cr-api.com or official API.

        Accepted values:
        cr-api
        official
        """
        provider = self.settings.get('api_provider')
        if provider is None:
            provider = 'cr-api'
        return provider

    @api_provider.setter
    def api_provider(self, value):
        self.settings["api_provider"] = value
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
        """Clash Royale profile API."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @crprofileset.command(name="auth", pass_context=True)
    async def crprofileset_auth(self, ctx, token):
        """Set auth header"""
        self.model.auth = token
        await self.bot.say("Auth updated.")
        await self.bot.delete_message(ctx.message)

    @crprofileset.command(name="official_auth", pass_context=True)
    async def crprofileset_official_auth(self, ctx, token):
        """Set auth header"""
        self.model.official_auth = token
        await self.bot.say("Auth updated.")
        await self.bot.delete_message(ctx.message)

    @crprofileset.command(name="initserver", pass_context=True)
    async def crprofileset_initserver(self, ctx):
        """Init CR Profile: server settings."""
        server = ctx.message.server
        self.model.init_server(server)
        await self.bot.say("Server settings initialized.")

    @crprofileset.command(name="initplayers", pass_context=True)
    async def crprofileset_initplayers(self, ctx):
        """Init CR Profile: players settings."""
        server = ctx.message.server
        self.model.init_players(server)
        await self.bot.say("Clan settings initialized.")

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
        await self.bot.say("API token saved.")

    @crprofileset.command(name="api_provider", pass_context=True)
    async def crprofileset_api_provider(self, ctx, value):
        """API Provider.

        Accepted values:
        cr-api
        official
        """
        if value == 'cr-api' or value == 'official':
            self.model.api_provider = value
            await self.bot.say("API provider saved.")
        else:
            await self.bot.say("Not a valid provider.")

    @crprofileset.command(name="rmmembertag", pass_context=True)
    async def crprofileset_rm_member_tag(self, ctx, member: discord.Member):
        """Remove player tag of a user."""
        server = ctx.message.server
        self.model.rm_player_tag(server, member=member)
        await self.bot.say("Removed player tag for {}".format(member))

    @checks.mod_or_permissions()
    @crprofileset.command(name="rmtag", pass_context=True)
    async def crprofileset_rm_tag(self, ctx, tag):
        """Remove player tag of a user."""
        server = ctx.message.server
        self.model.rm_player_tag(server, tag=tag)
        await self.bot.say("Removed player tag {} from associated member".format(tag))

    @commands.group(pass_context=True, no_pm=True)
    async def crprofile(self, ctx):
        """Clash Royale Player Profile."""
        if self.model.auth is None:
            await self.bot.say(
                "You must have a cr-api.com developer key to run this command. "
                "Please visit http://docs.cr-api.com/#/authentication to learn how to obtain one, "
                "then run `!crprofileset auth insert_developer_key` to set it.")
            return
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

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

    async def get_profile(
            self, ctx, member: discord.Member = None,
            **kwargs):
        """Logic for profile"""
        await self.bot.type()
        author = ctx.message.author
        server = ctx.message.server

        if member is None:
            member = author

        tag = self.model.member2tag(server, member)

        if tag is None:
            await self.bot.say(
                "{} has not set player tag with the bot yet. ".format(member.display_name)
            )
            # Tailor support message depending on cogs installed
            racf_cog = self.bot.get_cog("RACF")
            if racf_cog is None:
                await self.bot.say(
                    "Pleaes run `{}crprofile settag` to set your player tag.".format(ctx.prefix)
                )
            else:
                await self.bot.say(
                    "Please run `{}crsettag` to set your player tag.".format(ctx.prefix)
                )
            return
        await self.display_profile(ctx, tag, **kwargs)

    @crprofile.command(name="get", pass_context=True, no_pm=True)
    async def crprofile_get(self, ctx, member: discord.Member = None):
        """Player profile

        if member is not entered, retrieve own profile
        """
        await self.get_profile(ctx, member, sections=['overview', 'stats'])

    @crprofile.command(name="cards", pass_context=True, no_pm=True)
    async def crprofile_cards(self, ctx, member: discord.Member = None):
        """Card collection."""
        await self.get_profile(ctx, member, sections=['cards'])

    @crprofile.command(name="trade", pass_context=True, no_pm=True)
    async def crprofile_trade(self, ctx, member: discord.Member = None):
        """Tradeable cards."""
        await self.get_profile(ctx, member, sections=['trade'])

    @crprofile.command(name="tradetag", pass_context=True, no_pm=True)
    async def crprofile_tradetag(self, ctx, tag):
        """Tradeable cards by tag."""
        tag = clean_tag(tag)
        # await self.display_profile(ctx, tag)
        await self.display_profile(ctx, tag, sections=['trade'])

    @crprofile.command(name="chests", pass_context=True, no_pm=True)
    async def crprofile_chests(self, ctx, member: discord.Member = None):
        """Upcoming chests."""
        await self.get_profile(ctx, member, sections=['chests'])

    @crprofile.command(name="deck", pass_context=True, no_pm=True)
    async def crprofile_deck(self, ctx, member: discord.Member = None):
        """Current deck."""
        await self.get_profile(ctx, member, sections=['deck'])

    @crprofile.command(name="tagdeck", pass_context=True, no_pm=True)
    async def crprofile_tagdeck(self, ctx, tag):
        """Current deck of player tag."""
        await self.display_profile(ctx, tag, sections=['deck'])

    async def display_profile(self, ctx, tag, **kwargs):
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
            await self.bot.send_message(ctx.message.channel, "Unable to load from API.")
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
        for em in self.embeds_profile(player_data, server=server, **kwargs):
            try:
                await self.bot.say(embed=em)
            except:
                await self.bot.say("Unknown error")

    def embed_profile_overview(self, player: CRPlayerModel, server=None, color=None):
        """Discord Embed: profile overview."""
        bem = self.bot_emoji.name
        member = self.model.tag2member(server, player.tag)
        mention = '_'
        if member is not None:
            mention = member.mention

        profile_url = 'http://RoyaleAPI.com/player/{}'.format(player.tag.lstrip('#'))
        clan_url = 'http://RoyaleAPI.com/clan/{}'.format(player.clan_tag.lstrip('#'))

        # header
        title = player.name

        roles = {
            'member': 'Member',
            'elder': 'Elder',
            'coleader': 'Co-Leader',
            'leader': 'Leader',
            'n/a': 'N/A'
        }

        clan_role = player.clan_role

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
            clan_role=roles.get(player.clan_role.lower(), 'N/A')
        )
        em = discord.Embed(title=title, description=description, color=color, url=profile_url)
        # em.set_thumbnail(url=player.clan_badge_url)
        em.set_thumbnail(url=player.arena_url)
        header = {
            'Trophies': player.trophy_value(bem('trophy')),
            player.arena_text: '{} {}'.format(player.arena_subtitle, player.arena_emoji(self.bot_emoji)),
            'Rank': player.rank_str(self.bot_emoji),
            'Discord': mention
        }
        for k, v in header.items():
            em.add_field(name=k, value=v)
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')
        return em

    def embed_profile_stats(self, player: CRPlayerModel, color=None):
        """Discord Embed: profile stats."""
        em = discord.Embed(title=" ", color=color)
        bem = self.bot_emoji.name

        def fmt(num, emoji_name):
            emoji = self.bot_emoji.name(emoji_name)
            if emoji is not None:
                return '{:,} {}'.format(num, emoji)

        if player.tourney_cards_per_game is None:
            tourney_cards_per_game = 'N/A'
        else:
            tourney_cards_per_game = '{:.3f}'.format(player.tourney_cards_per_game)

        stats = OrderedDict([
            ('Ladder Wins / Losses', player.win_losses(bem('battle'))),
            ('Ladder Win Percentage', '{:.3%} {}'.format(player.win_ratio, bem('battle'))),
            ('Total Games', fmt(player.total_games, 'battle')),
            ('Challenge Max Wins', fmt(player.challenge_max_wins, 'tournament')),
            ('Challenge Cards Won', fmt(player.challenge_cards_won, 'tournament')),
            ('Three-Crown Wins', fmt(player.three_crown_wins, 'crownblue')),
            ('Tourney Cards Won', fmt(player.tourney_cards_won, 'tournament')),
            ('Tourney Games', fmt(player.tourney_games, 'tournament')),
            ('Tourney Cards/Game', '{} {}'.format(tourney_cards_per_game, bem('tournament'))),
            ('Cards Found', fmt(player.cards_found, 'cards')),
            ('Total Donations', fmt(player.total_donations, 'cards')),
            ('Level', fmt(player.level, 'experience')),
            ('Favorite Card', player.fave_card(self.bot_emoji)),
        ])
        for k, v in stats.items():
            em.add_field(name=k, value=v)

        # chests
        em.add_field(name="Chests", value=player.chest_list(self.bot_emoji), inline=False)

        # deck
        em.add_field(name="Deck", value=player.deck_list(self.bot_emoji), inline=False)

        return em

    def embed_profile_cards(self, player: CRPlayerModel, color=None):
        """Card Collection."""
        profile_url = 'http://RoyaleAPI.com/player/{}/cards'.format(player.tag.lstrip('#'))
        em = discord.Embed(
            title="{} #{}".format(player.name, player.tag),
            color=color,
            url=profile_url)
        cards = player.card_collection(self.bot_emoji)
        for rarity in ['Common', 'Rare', 'Epic', 'Legendary']:
            value = []
            for card in cards:
                if card is not None:
                    if card['rarity'] == rarity:
                        value.append(
                            "{}{}".format(
                                card['emoji'], normalized_card_level(card)))
            em.add_field(name=rarity, value=' '.join(value))

        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')

        return em

    def embed_profile_chests(self, player: CRPlayerModel, color=None):
        """Upcoming chests"""
        profile_url = 'http://RoyaleAPI.com/player/{}'.format(player.tag.lstrip('#'))
        em = discord.Embed(
            title="{} #{}: Chest Cycle".format(player.name, player.tag),
            color=color,
            url=profile_url)
        em.add_field(name="Chests", value=player.chest_list(self.bot_emoji), inline=False)
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')
        return em

    def embed_profile_deck(self, player: CRPlayerModel, color=None):
        """Current deck."""
        decklink_url = player.decklink
        profile_url = 'http://RoyaleAPI.com/player/{}'.format(player.tag.lstrip('#'))
        em = discord.Embed(
            title="{} #{}".format(player.name, player.tag),
            color=color,
            url=decklink_url)
        # cards = player.card_collection(self.bot_emoji)
        em.add_field(name="Deck", value=player.deck_list(self.bot_emoji), inline=False)
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')
        return em

    def embed_profile_trade(self, player: CRPlayerModel, color=None):
        """Current deck."""
        decklink_url = player.decklink
        profile_url = 'http://RoyaleAPI.com/player/{}'.format(player.tag.lstrip('#'))
        em = discord.Embed(
            title="{} #{}".format(player.name, player.tag),
            color=color,
            url=decklink_url)
        # cards = player.card_collection(self.bot_emoji)
        trade_list = player.trade_list(self.bot_emoji)
        for rarity in ['Legendary', 'Epic', 'Rare', 'Common']:
            em.add_field(
                name="Trade: {}".format(rarity),
                value=' '.join(trade_list[rarity]),
                inline=False
            )
        # em.add_field(name="Trade", value=player.trade_list(self.bot_emoji), inline=False)
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')
        return em

    def embeds_profile(self, player: CRPlayerModel, server=None, sections=('overview', 'stats')):
        """Return Discord Embed of player profile."""
        embeds = []
        color = random_discord_color()

        if 'overview' in sections:
            embeds.append(self.embed_profile_overview(player, server=server, color=color))

        if 'stats' in sections:
            embeds.append(self.embed_profile_stats(player, color=color))

        if 'cards' in sections:
            embeds.append(self.embed_profile_cards(player, color=color))

        if 'chests' in sections:
            embeds.append(self.embed_profile_chests(player, color=color))

        if 'deck' in sections:
            embeds.append(self.embed_profile_deck(player, color=color))

        if 'trade' in sections:
            embeds.append(self.embed_profile_trade(player, color=color))

        return embeds


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
