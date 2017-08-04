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

import argparse
import asyncio
import datetime as dt
import itertools
import json
import os
from collections import defaultdict
from datetime import timedelta
from enum import Enum
from random import choice

import aiohttp
import discord
from __main__ import send_cmd_help
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.chat_formatting import inline
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "crclan")
PATH_CLANS = os.path.join(PATH, "clans")
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")

DATA_UPDATE_INTERVAL = timedelta(minutes=10).seconds

API_FETCH_TIMEOUT = 5

BOT_COMMANDER_ROLES = ["Bot Commander"]

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


class SCTag:
    """SuperCell tags."""

    TAG_CHARACTERS = list("0289PYLQGRJCUV")

    def __init__(self, tag):
        """Init.

        Remove # if found.
        Convert to uppercase.
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


class CRClanType(Enum):
    """Clash Royale clan type."""

    OPEN = 1
    INVITE_ONLY = 2
    CLOSED = 3

    def __init__(self, clan_type):
        """Init."""
        self.type = clan_type

    @property
    def typename(self):
        """Convert type to name"""
        names = {
            self.OPEN: "Open",
            self.INVITE_ONLY: "Invite Only",
            self.CLOSED: "Closed",
        }
        for k, v in names.items():
            if k == self.type:
                return v
        return None


class CRClanModel:
    """Clash Royale Clan data."""

    def __init__(self, is_cache=False, timestamp=None, loaded=True, **kwargs):
        """Init.

        Expected list of keywords:
        From API:
            badge
            badge_url
            currentRank
            description
            donations
            members
            name
            numberOfMembers
            region
            requiredScore
            score
            tag
            type
            typeName
        From cog:
            key
            role
        """
        self.__dict__.update(kwargs)
        self.is_cache = is_cache
        self.timestamp = timestamp
        self.loaded = loaded

    @property
    def member_count_str(self):
        """Member count in #/50 format."""
        count = None
        if hasattr(self, 'numberOfMembers'):
            count = self.numberOfMembers
        if count is None:
            count = 0
        return '{}/50'.format(count)

    @property
    def valid(self):
        """Return True if it has expected properties."""
        return hasattr(self, 'name')

    @property
    def cache_message(self):
        """Cache message."""
        passed = dt.datetime.utcnow() - self.timestamp

        days = passed.days
        hours, remainder = divmod(passed.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        days_str = '{} days '.format(days) if days > 0 else ''
        passed_str = '{} {} hours {} minutes {} seconds ago'.format(days_str, hours, minutes, seconds)
        return (
            "Warning: Unable to access API. Returning cached data. "
            "Real-time data in CR may be different. \n"
            "Displaying data from {}.".format(passed_str)
        )


class CRClanMemberModel:
    """Clash Royale Member data."""

    def __init__(self, **kwargs):
        """Init.

        Expected list of keywords:
        From API:
            arena
            avatarId
                high
                low
                unsigned
            clanChestCrowns
            currentRank
            donations
            expLevel
            homeID
                high
                low
                unsigned
            league
            name
            previousRank
            role
            roleName
            score
            tag
        """
        self.__dict__.update(kwargs)
        self._discord_member = None

    @property
    def discord_member_id(self):
        """Discord user id."""
        return self._discord_member

    @discord_member_id.setter
    def discord_member_id(self, value):
        """Discord user id."""
        self._discord_member = value

    @property
    def mention(self):
        """Discord mention."""
        # return self.discord_member.mention
        return ""

    @property
    def role_name(self):
        """Properly formatted role name."""
        if self.role == 1:
            return "Member"
        elif self.role == 2:
            return "Leader"
        elif self.role == 3:
            return "Elder"
        elif self.role == 4:
            return "Co-Leader"
        return ""

    @property
    def currentRank(self):
        """API has typo."""
        return self.currenRank

    @property
    def rank(self):
        """Rank in clan with trend.

        Rank diffis in reverse because lower is better.
        Previous rank is 0 when user is new to the clan.

        \u00A0 is a non-breaking space.

        """
        rank_str = '--'
        if self.previousRank != 0:
            rank_diff = self.currentRank - self.previousRank
            if rank_diff > 0:
                rank_str = "↓ {}".format(rank_diff)
            elif rank_diff < 0:
                rank_str = "↑ {}".format(-rank_diff)
        return "`{0:\u00A0>8} {1:\u00A0<16}`".format(self.currentRank, rank_str)

    @property
    def rankdelta(self):
        """Difference in rank.

        Return None if previous rank is 0
        """
        if self.previousRank == 0:
            return None
        else:
            return self.currentRank - self.previousRank

    @property
    def league_icon_url(self):
        """League Icon URL."""
        return (
            'http://smlbiobot.github.io/img/leagues/'
            'league{}.png'
        ).format(self.league)

    def league_emoji(self, bot):
        """League emoji.

        Goes through all servers the bot is on to find the emoji.
        """
        name = 'league{}'.format(self.league)
        for server in bot.servers:
            for emoji in server.emojis:
                if emoji.name == name:
                    return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

#
# class CRClanMemberDoc(DocType):
#     """CR Clan Member Document."""
#     arena = Text(fields={'raw': Keyword()})
#     clan = Nested()
#     clan_chest_crowns = Integer()
#     current_rank = Integer()
#     discord = Nested()
#     donations = Integer()
#     experience_level = Integer()
#     league = Integer()
#     name = Text(fields={'raw': Keyword()})
#     name_with_tag = Text(fields={'raw': Keyword()})
#     previous_rank = Integer()
#     role = Integer()
#     role_name = Text(fields={'raw': Keyword()})
#     score = Integer()
#     tag = Text(fields={'raw': Keyword()})
#     timestamp = Date()
#
#     class Meta:
#         doc_type = 'member'
#
#     @classmethod
#     def doc(cls, data):
#         """Get doc"""
#         return CRClanMemberDoc(
#             clan=data.get('clan', None),
#             clan_chest_crowns=data.get('clanChestCrowns', None),
#             current_rank=data.get('currenRank', None),
#             discord=data.get('discord', None),
#             donations=data.get('donations', None),
#             discord_member_id=data.get('discord_member_id', None),
#             experience_level=data.get('expLevel', None),
#             league=data.get('league', None),
#             name=data.get('name', None),
#             name_with_tag='{} #{}'.format(
#                 data.get('name', ''),
#                 data.get('tag', None)
#             ),
#             previous_rank=data.get('previousRank', None),
#             role=data.get('role', None),
#             role_name=data.get('roleName', None),
#             score=data.get('score', None),
#             tag=data.get('tag', None),
#             timestamp=dt.datetime.utcnow(),
#         )
#
#     @classmethod
#     def log(cls, data, **kwargs):
#         """Log member."""
#         doc = CRClanMemberDoc.doc(data)
#         doc.save(**kwargs)
#
#     def save(self, **kwargs):
#         return super(CRClanMemberDoc, self).save(**kwargs)
#
#
# class CRClanDoc(DocType):
#     """CR Clan Elastic Search Document."""
#     timestamp = Date()
#     badge = Integer()
#     badge_url = Text(fields={'raw': Keyword()})
#     current_rank = Integer()
#     description = Text(
#         analyzer=analyzer("simple"),
#         fields={'raw': Keyword()}
#     )
#     donations = Integer()
#     members = Nested(doc_class=CRClanMemberDoc)
#     name = Text(fields={'raw': Keyword()})
#     number_of_members = Integer()
#     region = Integer()
#     required_score = Integer()
#     score = Integer()
#     tag = Text(fields={'raw': Keyword()})
#     type = Integer()
#     type_name = Text(fields={'raw': Keyword()})
#
#     class Meta:
#         doc_type = 'clan'
#
#     @classmethod
#     def log(cls, data, **kwargs):
#         """Log all."""
#         doc = CRClanDoc(
#             badge=data.get('badge', None),
#             badge_url=data.get('badge_url', None),
#             current_rank=data.get('currentRank', None),
#             description=data.get('description', None),
#             donations=data.get('donations', None),
#             members=[],
#             name=data.get('name', None),
#             name_with_tag='{} #{}'.format(
#                 data.get('name', ''),
#                 data.get('tag', None)
#             ),
#             number_of_members=data.get('numberOfMembers', None),
#             region=data.get('region', None),
#             required_score=data.get('requiredScore', None),
#             score=data.get('score', None),
#             tag=data.get('tag', None),
#             timestamp=dt.datetime.utcnow(),
#             type=data.get('type', None),
#             type_name=data.get('typeName', None),
#         )
#         for member_data in data.get('members', []):
#             doc.add_member(member_data)
#         doc.save(**kwargs)
#
#     def save(self, **kwargs):
#         return super(CRClanDoc, self).save(**kwargs)
#
#     def add_member(self, data):
#         self.members.append(
#             CRClanMemberDoc.doc(data)
#         )
#

class SettingsException(Exception):
    pass


class ClanTagNotInSettings(SettingsException):
    pass


class ClanKeyNotInSettings(SettingsException):
    pass


class APIFetchError(SettingsException):
    pass


class ServerModel:
    """Discord server data model.

    Sets per-server settings since the bot can be run on multiple servers.
    """
    DEFAULTS = {
        "clans": {},
        "players": {}
    }

    def __init__(self, data=None):
        """Init."""
        if data is None:
            data = self.DEFAULTS
        self.settings = data


class CogModel:
    """Cog settings.

    Functionally the CRClan cog model.
    """

    DEFAULTS = {
        "servers": {},
    }

    def __init__(self, filepath, bot):
        """Init."""
        self.filepath = filepath
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(filepath))
        self.bot = bot

        # arenas
        arenas = dataIO.load_json(os.path.join(PATH, 'arenas.json'))
        self.arenas = [CRArenaModel(**a) for a in arenas]
        self.arenas = sorted(self.arenas, key=lambda x: x.TrophyLimit, reverse=True)

    def init_server(self, server):
        """Initialized server settings.

        This will wipe all clan data and player data.
        """
        self.settings["servers"][server.id] = ServerModel.DEFAULTS
        self.save()

    def init_clans(self, server):
        """Initialized clan settings."""
        self.settings["servers"][server.id]["clans"] = {}
        self.save()

    def check_server(self, server):
        """Make sure server exists in settings."""
        if server.id not in self.settings["servers"]:
            self.settings["servers"][server.id] = ServerModel.DEFAULTS
        self.save()

    def get_clans(self, server):
        """CR Clans settings by server."""
        return self.settings["servers"][server.id]["clans"]

    def get_players(self, server):
        """CR Players settings by server."""
        return self.settings["servers"][server.id]["players"]

    def save(self):
        """Save data to disk."""
        dataIO.save_json(self.filepath, self.settings)

    def add_clan(self, server, tag, key, role_name):
        """Add a clan by server."""
        self.check_server(server)
        tag = SCTag(tag).tag
        role = discord.utils.get(server.roles, name=role_name)
        role_id = None
        if role is not None:
            role_id = role.id
        self.settings["servers"][server.id]["clans"][tag] = {
            'tag': tag,
            'key': key,
            'role_name': role_name,
            'role_id': role_id
        }
        self.save()

    def remove_clan(self, server, tag):
        """Remove clan(s) in settings by clan tags."""
        tag = SCTag(tag).tag
        clans = self.get_clans(server)
        if tag not in clans:
            raise ClanTagNotInSettings
        clans.pop(tag)
        self.save()

    def set_clan_key(self, server, tag, key):
        """Associate key with clan tag."""
        tag = SCTag(tag).tag
        clans = self.get_clans(server)
        if tag not in clans:
            raise ClanTagNotInSettings
        clans[tag]["key"] = key
        self.save()

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

    def key2tag(self, server, key):
        """Convert clan key to clan tag."""
        clans = self.get_clans(server)
        for tag, clan in clans.items():
            if clan["key"].lower() == key.lower():
                return tag
        return None

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

    async def get_clan_data(self, server, key=None, tag=None) -> CRClanModel:
        """Return data as CRClanData by key or tag

        Raise asyncio.TimeoutError if API is down.
        """
        if tag is None:
            if key is not None:
                tag = self.key2tag(server, key)

        if tag is None:
            return None

        data = await self.update_clan_data(tag)

        # if data is None:
        #     return None
        return data

    def server_settings(self, server):
        """Return server settings."""
        return self.settings["servers"][server.id]

    def discord_members_by_clankey(self, server, key=None, sort=True):
        """Return list of Discord members by clan key.

        This uses the role_id associated in settings to fetch
        list of users on server.

        Sorted alphabetically.
        """
        tag = self.key2tag(server, key)
        clan = self.server_settings(server)["clans"][tag]
        role = discord.utils.get(server.roles, id=clan['role_id'])
        members = [m for m in server.members if role in m.roles]
        if sort:
            members = sorted(members, key=lambda x: x.display_name.lower())
        return members

    async def update_clan_data(self, tag):
        """Update and save clan data from API.

        Return CRClanModel instance
        """
        tag = SCTag(tag).tag
        url = "{}{}".format(self.clan_api_url, tag)

        print(url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=API_FETCH_TIMEOUT) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            return False
        except asyncio.TimeoutError:
            # return CRClanModel(loaded=False, tag=tag)
            return False

        filepath = self.cached_filepath(tag)
        dataIO.save_json(filepath, data)

        is_cache = False
        timestamp = dt.datetime.utcnow()

        return CRClanModel(is_cache, timestamp, **data)

    def cached_clan_data(self, tag):
        """Load cached clan data. Used when live update failed."""
        filepath = self.cached_filepath(tag)
        if os.path.exists(filepath):
            is_cache = True
            data = dataIO.load_json(filepath)
            timestamp = dt.datetime.fromtimestamp(os.path.getmtime(filepath))
            return CRClanModel(is_cache, timestamp, **data)
        return None

    @staticmethod
    def cached_filepath(tag):
        """Cached clan data file path"""
        return os.path.join(PATH_CLANS, '{}.json'.format(tag))

    async def update_data(self):
        """Update all data and save to disk."""
        dataset = []
        for server_id in self.settings["servers"]:
            clans = self.settings["servers"][server_id]["clans"]
            for tag in clans.keys():
                data = await self.update_clan_data(tag)
                if not data:
                    data = self.cached_clan_data(tag)
                if data is None:
                    data = CRClanModel(loaded=False, tag=tag)
                dataset.append(data)
        return dataset

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

    @property
    def clan_api_url(self):
        """Clan API URL."""
        return 'http://cr-api.com/clan/'

    @property
    def data_update_interval(self):
        interval = self.settings.get("data_update_interval", DATA_UPDATE_INTERVAL)
        return int(interval)

    @data_update_interval.setter
    def data_update_interval(self, value):
        """Set data update interval."""
        self.settings["data_update_interval"] = int(value)
        self.save()

    @property
    def es_enabled(self):
        """Enable Elastic Search."""
        return self.settings["elasticsearch_enabled"]

    @es_enabled.setter
    def es_enabled(self, value):
        """Set Elastic Search enabled"""
        self.settings["elasticsearch_enabled"] = value
        self.save()

    @property
    def badge_url(self):
        """Clan Badge URL."""
        return 'http://cr-api.com'


class ErrorMessage:
    """Error Messages"""

    @staticmethod
    def key_error(key):
        return (
            "Error fetching data from API for clan key {}. "
            "Please try again later.").format(key)

    @staticmethod
    def tag_error(tag):
        return (
            "Error fetching data from API for clan tag #{}. "
            "Please try again later.").format(tag)


class CRClanInfoView:
    """Clan info view.

    This shows the clan’s general information
    e.g. trophy requirements, trophies, number of members, etc.
    """

    def __init__(self, bot, model):
        """Init."""
        self.bot = bot
        self.model = model

    async def send(
            self, ctx, data: CRClanModel,
            color=None, cache_warning=False, **kwargs):
        """Send info to destination according to context."""
        em = self.embed(data, color=color)
        await self.bot.send_message(ctx.message.channel, embed=em)
        if cache_warning and data.is_cache:
            await self.bot.say(data.cache_message)

    def embed(self, data: CRClanModel, color=None):
        """Return clan info embed."""
        if color is None:
            color = random_discord_color()
        em = discord.Embed(
            title=data.name,
            description=data.description,
            color=color)
        em.add_field(name="Clan Trophies", value=data.score)
        em.add_field(name="Type", value=CRClanType(data.type).typename)
        em.add_field(name="Required Trophies", value=data.requiredScore)
        em.add_field(name="Clan Tag", value=data.tag)
        em.add_field(name="Members", value=data.member_count_str)
        badge_url = '{}{}'.format(self.model.badge_url, data.badge_url)
        print(badge_url)
        em.set_thumbnail(url=badge_url)
        return em


class CRClanRosterView:
    """Clan roster view.

    Trying to see if breaking this out in its own class can make
    processing all those arguments easier to see.
    """

    def __init__(self, bot, model):
        """Init."""
        self.bot = bot
        self.model = model

    async def display(self, ctx, server, data: CRClanModel, color=None, cache_warning=False):
        """Intermediate step to sort data if necessary."""
        await self.send(ctx, server, data, color=color, cache_warning=cache_warning)

    async def send(self, ctx, server, data: CRClanModel, color=None, cache_warning=False):
        """Send roster to destination according to context.

        Results are split in groups of 25
        because Discord Embeds allow 25 fields per embed.
        """
        members_out = grouper(25, data.members, None)

        for page, members in enumerate(members_out, start=1):
            kwargs = {
                'server': server,
                'members': members,
                'title': data.name,
                'footer_text': '{} #{} - Page {}'.format(
                    data.name, data.tag, page),
                'footer_icon_url': self.model.badge_url + data.badge_url
            }
            em = self.embed(color=color, **kwargs)
            await self.bot.send_message(ctx.message.channel, embed=em)

        if cache_warning and data.is_cache:
            await self.bot.say(data.cache_message)

    def embed(
            self,
            server=None, title=None, members=None,
            footer_text=None, footer_icon_url=None,
            color=None):
        """Return clan roster as Discord embed.

        This represents a page of a roster.
        """
        em = discord.Embed(title=title)
        em.set_footer(text=footer_text, icon_url=footer_icon_url)
        for member in members:
            if member is not None:
                data = CRClanMemberModel(**member)
                discord_member = self.model.tag2member(server, data.tag)
                name = (
                    "{0.name}, {0.role_name} "
                    "(Lvl {0.expLevel})").format(data)
                stats = (
                    "{0.score:,d}"
                    " | {0.donations:\u00A0>4} d"
                    " | {0.clanChestCrowns:\u00A0>3} c"
                    " | #{0.tag}").format(data)
                stats = inline(stats)
                mention = ''
                if discord_member is not None:
                    mention = discord_member.mention
                arena = self.model.trophy2arena(data.score)
                """ Rank str
                41 ↓ 31
                """
                rank_delta = data.rankdelta
                rank_delta_str = '.  .'
                rank_current = '{: <2}'.format(data.currentRank)
                if data.rankdelta is not None:
                    if data.rankdelta > 0:
                        rank_delta_str = "↓ {: >2}".format(rank_delta)
                    elif data.rankdelta < 0:
                        rank_delta_str = "↑ {: >2}".format(-rank_delta)
                value = '`{rank_current} {rank_delta}` {emoji} {arena} {mention}\n{stats} '.format(
                    rank_current=rank_current,
                    rank_delta=rank_delta_str,
                    mention=mention,
                    emoji=data.league_emoji(self.bot),
                    arena=arena,
                    stats=stats)
                em.add_field(name=name, value=value, inline=False)
        if color is None:
            color = random_discord_color()
        em.color = color
        return em


# noinspection PyUnusedLocal
class CRClan:
    """Clash Royale Clan management."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.model = CogModel(JSON, bot)
        self.roster_view = CRClanRosterView(bot, self.model)
        self.info_view = CRClanInfoView(bot, self.model)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        """Loop task: update data daily."""
        await self.bot.wait_until_ready()
        await self.model.update_data()
        await asyncio.sleep(self.model.data_update_interval)
        if self is self.bot.get_cog('CRClan'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def crclanset(self, ctx):
        """Clash Royale clan management API.

        Requires: Clash Royale API access by Selfish.
        """
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crclanset.command(name="init", pass_context=True)
    async def crclanset_init(self, ctx):
        """Init CR Clan: server settings."""
        server = ctx.message.server
        self.model.init_server(server)
        await self.bot.say("Server settings initialized.")

    @crclanset.command(name="initclans", pass_context=True)
    async def crclanset_init(self, ctx):
        """Init CR Clan: clans settings."""
        server = ctx.message.server
        self.model.init_clans(server)
        await self.bot.say("Clan settings initialized.")

    @crclanset.command(name="dataupdateinterval", pass_context=True)
    async def crclanset_dataupdateintervall(self, ctx, seconds):
        """Data update interval

        unit is seconds.
        """
        self.model.data_update_interval = seconds
        await self.bot.say("Data update interval updated.")

    @crclanset.command(name="update", pass_context=True)
    async def crclanset_update(self, ctx):
        """Update data from api."""
        await self.bot.type()
        dataset = await self.model.update_data()
        for data in dataset:
            if not data.loaded:
                await self.bot.send_message(ctx.message.channel, "Cannot load data for {}.".format(data.tag))
            if data.is_cache:
                await self.bot.send_message(ctx.message.channel, data.cache_message)
            else:
                await self.bot.send_message(ctx.message.channel, "Data for {} updated".format(data.name))

    @crclanset.command(name="add", pass_context=True)
    async def crclanset_add(self, ctx, tag, key=None, role_name=None):
        """Add clan tag(s).

        [p]crclanset add 2CCCP alpha

        tag: clan tag without the # sign
        key: human readable key for easier calls for data
        role: server role assignment

        """
        sctag = SCTag(tag)

        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        self.model.add_clan(ctx.message.server, sctag.tag, key, role_name)

        await self.bot.say(
            'Added clan #{} with key: {} and role: {}'.format(
                tag, key, role_name))

    @crclanset.command(name="remove", pass_context=True)
    async def crclanset_remove(self, ctx, *clantags):
        """Remove clan tag(s).

        [p]crclanset remove LQQ 82RQLR 98VLYJ Q0YG8V

        """
        if not clantags:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server

        for clantag in clantags:
            try:
                self.model.remove_clan(server, clantag)
            except ClanTagNotInSettings:
                await self.bot.say("{} is not in clan settings.".format(clantag))
            else:
                await self.bot.say("Removed #{} from clans.".format(clantag))

    @crclanset.command(name="key", pass_context=True)
    async def crclanset_key(self, ctx, tag, key):
        """Human readable key for clan tags.

        This is used for running other commands to make
        fetching data easier without having to use
        clan tag every time.

        You can also set this key when adding clans
        with [p]crclanset add [tag] [key]
        """
        server = ctx.message.server

        sctag = SCTag(tag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        try:
            self.model.set_clan_key(server, sctag.tag, key)
        except ClanTagNotInSettings:
            await self.bot.say(
                "{} is not a clan tag you have added".format(tag))
        else:
            await self.bot.say("Added {} for clan #{}.".format(key, tag))


    @commands.group(pass_context=True, no_pm=True)
    async def crclan(self, ctx):
        """Clash Royale clan."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crclan.command(name="about", pass_context=True, no_pm=True)
    async def crclan_about(self, ctx):
        """About this cog."""
        await self.bot.say("Selfish + SML FTW!")

    @crclan.command(name="settag", pass_context=True, no_pm=True)
    async def crclan_settag(
            self, ctx, playertag, member: discord.Member = None):
        """Set playertag to discord member.

        Setting tag for yourself:
        !crclan settag C0G20PR2

        Setting tag for others (requires Bot Commander role):
        !crclan settag C0G20PR2 SML
        !crclan settag C0G20PR2 @SML
        !crclan settag C0G20PR2 @SML#6443
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
                    server.roles, name=r) for r in BOT_COMMANDER_ROLES]
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

    @crclan.command(name="gettag", pass_context=True, no_pm=True)
    async def crclan_gettag(self, ctx, member: discord.Member = None):
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

    @crclan.command(name="clankey", pass_context=True, no_pm=True)
    async def crclan_clankey(self, ctx, key):
        """Clan info + roster by key.

        Key of each clan is set from [p]bsclan addkey
        """
        success = await self.send_clan(ctx, key=key)
        if not success:
            await self.bot.say("Unable to get clan info by key entered.")

    @crclan.command(name="clantag", pass_context=True, no_pm=True)
    async def crclan_clantag(self, ctx, tag):
        """Clan info and roster by tag.

        Clan tag is the alphanumeric digits after the # sign
        found in the clan description.
        """
        success = await self.send_clan(ctx, tag=tag)
        if not success:
            await self.bot.say("Unable to get clan info by tag entered.")

    async def send_clan(self, ctx, key=None, tag=None):
        """Clan info and roster by either key or tag."""
        if not any([key, tag]):
            return False

        server = ctx.message.server
        if tag is None:
            if key is None:
                return False
            else:
                tag = self.model.key2tag(server, key)

        sctag = SCTag(tag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return False

        await self.bot.send_typing(ctx.message.channel)

        server = ctx.message.server
        data = await self.model.get_clan_data(server, tag=sctag.tag)
        data_is_cached = False
        if not data:
            data_is_cached = True
            data = self.model.cached_clan_data(self.model.key2tag(server, key))
            if data is None:
                await self.bot.say("Cannot find key {} in settings.".format(key))
                return

        color = random_discord_color()
        await self.info_view.send(ctx, data, color=color)
        await self.roster_view.send(ctx, server, data, color=color)

        if data_is_cached:
            await self.bot.say(data.cache_message)

        return True

    @crclan.command(name="info", pass_context=True, no_pm=True)
    async def crclan_info(self, ctx, key=None):
        """Clan info.

        Display clan name, description, trophy requirements, etc.
        """
        server = ctx.message.server
        await self.bot.send_typing(ctx.message.channel)

        clan_data = await self.model.get_clan_data(server, key=key)
        data_is_cached = False
        if not clan_data:
            data_is_cached = True
            clan_data = self.model.cached_clan_data(self.model.key2tag(server, key))
            if clan_data is None:
                await self.bot.say("Cannot find key {} in settings.".format(key))
                return

        await self.info_view.send(ctx, clan_data, cache_warning=data_is_cached)

    @crclan.command(name="roster", pass_context=True, no_pm=True)
    async def crclan_roster(self, ctx, key, *args):
        """Clan roster by key.

        To associate a key with a clan tag:
        [p]bsclan addkey

        Optional arguments:
        --sort {name,trophies,level,donations,crowns}

        Example: Display clan roster associated with key “alpha”, sorted by donations
        [p]bsclan roster alpha --sort donations
        """
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]crclan roster')
        # parser.add_argument('key')
        parser.add_argument(
            '--sort',
            choices=['name', 'trophies', 'level', 'donations', 'crowns'],
            default="trophies",
            help='Sort roster')

        try:
            p_args = parser.parse_args(args)
        except SystemExit:
            # await self.bot.send_message(ctx.message.channel, box(parser.format_help()))
            await send_cmd_help(ctx)
            return

        # key = p_args.key

        # Load data
        server = ctx.message.server
        await self.bot.send_typing(ctx.message.channel)
        clan_data = await self.model.get_clan_data(server, key=key)
        data_is_cached = False
        if not clan_data:
            data_is_cached = True
            clan_data = self.model.cached_clan_data(self.model.key2tag(server, key))
            if clan_data is None:
                await self.bot.say("Cannot find key {} in settings.".format(key))
                return

        # Sort data
        if p_args.sort == 'trophies':
            clan_data.members = sorted(clan_data.members, key=lambda member: -member['score'])
        elif p_args.sort == 'name':
            clan_data.members = sorted(clan_data.members, key=lambda member: member['name'].lower())
        elif p_args.sort == 'level':
            clan_data.members = sorted(clan_data.members, key=lambda member: -member['expLevel'])
        elif p_args.sort == 'donations':
            clan_data.members = sorted(clan_data.members, key=lambda member: -member['donations'])
        elif p_args.sort == 'crowns':
            clan_data.members = sorted(clan_data.members, key=lambda member: -member['clanChestCrowns'])

        await self.roster_view.send(
            ctx, server, clan_data, cache_warning=data_is_cached, color=random_discord_color())

    @commands.has_any_role(*BOT_COMMANDER_ROLES)
    @crclan.command(name="multiroster", pass_context=True, no_pm=True)
    async def crclan_multiroster(self, ctx, *keys):
        """Multiple rosters by list of keys.

        [p]crclan multiroster alpha bravo charlie
        """
        for key in keys:
            await ctx.invoke(self.crclan_roster, key)

    @crclan.command(name="audit", pass_context=True, no_pm=True)
    async def crclan_audit(self, ctx, key):
        """Compare roster with Discord roles.

        This shows an alphabetically sorted list of members on the roster
        side by side with that on Discord for easy auditing.
        """
        server = ctx.message.server

        await self.bot.type()

        data = await self.model.get_clan_data(server, key=key)
        data_is_cached = False
        if not data:
            data_is_cached = True
            data = self.model.cached_clan_data(self.model.key2tag(server, key))
            if data is None:
                await self.bot.send_message(
                    ctx.message.channel,
                    "API cannot be reached, and no cached data is available.")
                return

        # alphabetical list of discord members with associated role
        dc_members = self.model.discord_members_by_clankey(server, key=key)
        dc_names = [m.mention for m in dc_members]

        # alphabetical list of members in CR App
        cr_members = [CRClanMemberModel(**m) for m in data.members]
        cr_names = [m.name for m in cr_members]
        cr_names = sorted(cr_names, key=lambda x: x.lower())

        # split into groups because embed value size too large otherwise

        split_count = 3

        max_len = max(len(cr_names), len(dc_names))

        group_size = max_len // split_count + 1
        target_len = group_size * split_count

        if len(cr_names) < target_len:
            cr_names.extend(['_'] * (target_len - len(cr_names)))
        if len(dc_names) < target_len:
            dc_names.extend(['_'] * (target_len - len(dc_names)))

        cr_names_group = list(grouper(group_size, cr_names, '_'))
        dc_names_group = list(grouper(group_size, dc_names, '_'))

        color = random_discord_color()

        for i in range(split_count):
            cr_list = '\n'.join(cr_names_group[i])
            dc_list = '\n'.join(dc_names_group[i])

            em = discord.Embed(title=data.name, color=color)
            em.add_field(name="CR", value=cr_list, inline=True)
            em.add_field(name="Discord", value=dc_list, inline=True)

            # not sure why bot.say() fails again
            await self.bot.send_message(ctx.message.channel, embed=em)

        if data_is_cached:
            await self.bot.say(data.cache_message)

    @crclan.command(name="trophy2arena", pass_context=True, no_pm=True)
    async def crclan_trophy2arena(self, ctx, trophy: int):
        """Convert trophies to arenas."""
        text = self.model.trophy2arena(trophy)
        await self.bot.say(text)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)
    if not os.path.exists(PATH_CLANS):
        os.makedirs(PATH_CLANS)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = CRClan(bot)
    bot.add_cog(n)
