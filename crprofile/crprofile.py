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
from collections import defaultdict, OrderedDict
from datetime import timedelta
from random import choice

import aiohttp
import discord
import inflect
import requests
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "crprofile")
PATH_PLAYERS = os.path.join(PATH, "players")
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")
CHESTS = dataIO.load_json(os.path.join('data', 'crprofile', 'chests.json'))

DATA_UPDATE_INTERVAL = timedelta(minutes=30).seconds

API_FETCH_TIMEOUT = 10

BOTCOMMANDER_ROLES = ["Bot Commander"]

CREDITS = 'Selfish + SML'


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


class API:
    """Clash Royale official API."""

    @staticmethod
    def url_player(tag):
        """Return player URL"""
        return "http://temp-api.cr-api.com/player/" + tag.upper()


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

    @staticmethod
    def get_instance():
        if Constants.__instance is None:
            Constants()
        return Constants.__instance

    @property
    def cards(self):
        if self._cards is None:
            r = requests.get('https://cr-api.github.io/cr-api-data/json/cards.json')
            self._cards = r.json()
        return self._cards

    @property
    def rarities(self):
        if self._rarities is None:
            r = requests.get('https://cr-api.github.io/cr-api-data/json/rarities.json')
            self._rarities = r.json()
        return self._rarities

    @property
    def alliance_badges(self):
        if self._alliance_badges is None:
            r = requests.get('https://cr-api.github.io/cr-api-data/json/alliance_badges.json')
            self._alliance_badges = r.json()
        return self._alliance_badges

    def badge_id_to_url(self, id):
        for badge in self.alliance_badges:
            if badge['badge_id'] == id:
                return "https://cr-api.github.io/cr-api-assets/badge/{}.png".format(badge['name'])
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
            'epic': 'chestepic'
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

    def __init__(self, is_cache=False, data=None, error=False):
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

    def prop(self, section, prop, default=0):
        """Return sectional attribute."""
        attr = self.data.get(section)
        if attr is not None:
            value = attr.get(prop)
            if value is not None:
                return value
        return default

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
    def clan(self):
        """Clan."""
        return self.data.get("clan", None)

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
            url = Constants.get_instance().badge_id_to_url(self.clan['badge'])
        except KeyError:
            pass
        return url

    @property
    def stats(self):
        """Stats."""
        return self.data.get("stats", None)

    @property
    def challenge_cards_won(self):
        """Challenge cards won."""
        return self.prop("stats", "challengeCardsWon", 0)

    @property
    def tourney_cards_won(self):
        """Challenge cards won."""
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
        return self.prop("stats", "challengeMaxWins", 0)

    @property
    def total_donations(self):
        """Total donations."""
        return self.prop("stats", "totalDonations", 0)

    @property
    def cards_found(self):
        """Cards found."""
        return self.prop("stats", "cardsFound", 0)

    @property
    def favorite_card(self):
        """Favorite card."""
        return self.prop("stats", "favoriteCard", "soon")

    @property
    def trophy_current(self):
        """Current trophies."""
        return self.data.get("trophies", None)

    @property
    def trophy_highest(self):
        """Personal best."""
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
        return self.prop("stats", "level", 0)

    @property
    def games(self):
        """Game stats."""
        return self.data.get("games")

    @property
    def tourney_games(self):
        """Number of tournament games."""
        return self.prop("games", "tournamentGames", 0)

    @property
    def wins(self):
        """Games won."""
        return self.prop("games", "wins", 0)

    @property
    def losses(self):
        """Games won."""
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
        return self.prop("games", "total", 0)

    @property
    def win_streak(self):
        """Win streak."""
        return max(self.prop("games", "currentWinStreak", 0), 0)

    @property
    def three_crown_wins(self):
        """Three crown wins."""
        return self.prop("stats", "threeCrownWins", 0)

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

    """
    Chests.
    """

    def chest_list(self, bot_emoji: BotEmoji):
        """List of chests."""
        # chests
        chest_cycle = self.data.get("chestCycle")
        if chest_cycle is None:
            return ""

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
        try:
            return self.data["arena"]["arena"]
        except KeyError:
            return None

    @property
    def arena_text(self):
        """Arena text."""
        try:
            return self.data["arena"]["name"]
        except KeyError:
            return None

    @property
    def arena_subtitle(self):
        """Arena subtitle"""
        try:
            return self.data["arena"]["arena"]
        except KeyError:
            return None

    @property
    def arena_id(self):
        """Arena ID."""
        try:
            return self.data["arena"]["arenaID"]
        except KeyError:
            return None

    @property
    def league(self):
        """League (int)."""
        league = max(self.arena_id - 11, 0)
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
    def arena_url(self):
        """Arena Icon URL."""
        if self.league > 0:
            url = 'http://smlbiobot.github.io/img/leagues/league{}.png'.format(self.league)
        else:
            url = 'http://smlbiobot.github.io/img/arenas/arena-{}.png'.format(self.arena.Arena)
        return url

    def deck_list(self, bot_emoji: BotEmoji):
        """Deck with emoji"""
        cards = [card["key"] for card in self.data.get("currentDeck")]
        cards = [bot_emoji.name(key.replace('-', '')) for key in cards]
        levels = [card["level"] for card in self.data.get("currentDeck")]
        deck = ['{0[0]}{0[1]}'.format(card) for card in zip(cards, levels)]
        return ' '.join(deck)

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
        for s in self.data.get("previousSeasons"):
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
        return self.data.get("cards")

    def card_collection(self, bot_emoji):

        sort_rarities = {
            'Common': 1,
            'Rare': 2,
            'Epic': 3,
            'Legendary': 4
        }
        cards = self.cards
        cards = sorted(cards, key=lambda x: (sort_rarities[x['rarity']], x['elixir']))

        out = []
        for card in cards.copy():
            key = card['key']
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

    def rm_player_tag(self, server, member):
        """Remove player tag from settings."""
        self.check_server(server)
        try:
            self.settings["servers"][server.id]["players"].pop(member.id, None)
        except KeyError:
            pass
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
        url = API.url_player(tag)
        print(url)

        error = False
        data = None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=API_FETCH_TIMEOUT) as resp:
                    if resp.status != 200:
                        error = True
                    else:
                        data = await resp.json()
                        file_path = self.cached_filepath(tag)
                        dataIO.save_json(file_path, data)
        except json.decoder.JSONDecodeError:
            raise
        except asyncio.TimeoutError:
            raise

        return CRPlayerModel(data=data, error=error)

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
        """Authentication bearer token"""
        return self.settings.get("auth")

    @auth.setter
    def auth(self, value):
        """Set authentication bearer token."""
        self.settings["auth"] = value
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
        # TODO Depreciated as cr-api.com Profile API is now public.
        # TODO Keeping this as token might be implemented later.
        self.model.profile_api_token = token
        await self.bot.say("API token save.")

    @crprofileset.command(name="rmplayertag", pass_context=True)
    async def crprofileset_rmplayertag(self, ctx, member: discord.Member):
        """Remove player tag of a user."""
        server = ctx.message.server
        self.model.rm_player_tag(server, member)
        await self.bot.say("Removed player tag for {}".format(member))

    @commands.group(pass_context=True, no_pm=True)
    async def crprofile(self, ctx):
        """Clash Royale Player Profile."""
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
            overview=True, stats=False, cards=False):
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
        await self.display_profile(ctx, tag, overview=overview, stats=stats, cards=cards)

    @crprofile.command(name="get", pass_context=True, no_pm=True)
    async def crprofile_get(self, ctx, member: discord.Member = None):
        """Player profile

        if member is not entered, retrieve own profile
        """
        await self.get_profile(ctx, member, overview=True, stats=True, cards=False)

    @crprofile.command(name="cards", pass_context=True, no_pm=True)
    async def crporifle_cards(self, ctx, member: discord.Member = None):
        """Player profile with cards."""
        await self.get_profile(ctx, member, overview=True, stats=False, cards=True)

    async def display_profile(self, ctx, tag, overview=True, stats=False, cards=False):
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
        for em in self.embeds_profile(player_data, server=server, overview=overview, stats=stats, cards=cards):
            await self.bot.say(embed=em)

    def embeds_profile(self, player: CRPlayerModel, server=None, overview=True, stats=False, cards=False):
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
        em.set_footer(
            text=profile_url,
            icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')
        embeds.append(em)

        if stats:

            # trophies
            em = discord.Embed(title=" ", color=color)

            def fmt(num, emoji_name):
                emoji = bem(emoji_name)
                if emoji is not None:
                    return '{:,} {}'.format(num, emoji)

            if player.tourney_cards_per_game is None:
                tourney_cards_per_game = 'N/A'
            else:
                tourney_cards_per_game = '{:.3f}'.format(player.tourney_cards_per_game)

            stats = OrderedDict([
                ('Wins / Losses (Ladder 1v1)', player.win_losses(bem('battle'))),
                ('Ladder Win Percentage', '{:.3%} {}'.format(player.win_ratio, bem('battle'))),
                ('Total Games (1v1 + 2v2)', fmt(player.total_games, 'battle')),
                ('Three-Crown Wins', fmt(player.three_crown_wins, 'crownblue')),
                ('Win Streak', fmt(player.win_streak, 'crownred')),
                ('Cards Found', fmt(player.cards_found, 'cards')),
                ('Challenge Cards Won', fmt(player.challenge_cards_won, 'tournament')),
                ('Challenge Max Wins', fmt(player.challenge_max_wins, 'tournament')),
                ('Tourney Cards Won', fmt(player.tourney_cards_won, 'tournament')),
                ('Tourney Games', fmt(player.tourney_games, 'tournament')),
                ('Tourney Cards/Game', '{} {}'.format(tourney_cards_per_game, bem('tournament'))),
                ('Total Donations', fmt(player.total_donations, 'cards')),
                ('Level', fmt(player.level, 'experience')),
                ('Favorite Card', player.fave_card(self.bot_emoji))
            ])
            for k, v in stats.items():
                em.add_field(name=k, value=v)

            # chests
            em.add_field(name="Chests", value=player.chest_list(self.bot_emoji), inline=False)

            # deck
            em.add_field(name="Deck", value=player.deck_list(self.bot_emoji), inline=False)

            embeds.append(em)

        if cards:
            # card colllection
            em = discord.Embed(title=" ", color=color)
            cards = player.card_collection(self.bot_emoji)
            for rarity in ['Common', 'Rare', 'Epic', 'Legendary']:
                value = []
                for card in cards:
                    if card is not None:
                        if card['rarity'] == rarity:
                            value.append(
                                "{}{}".format(
                                    card['emoji'], card['level']))
                em.add_field(name=rarity, value=' '.join(value))

            embeds.append(em)

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
