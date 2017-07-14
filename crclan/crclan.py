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

import os
import asyncio
import itertools
import datetime as dt
from random import choice
import json
from collections import defaultdict
from datetime import timedelta
from enum import Enum

import discord
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

PATH = os.path.join("data", "crclan")
PATH_CLANS = os.path.join(PATH, "clans")
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")

DATA_UPDATE_INTERVAL = timedelta(minutes=30).seconds

BOTCOMMANDER_ROLES = ["Bot Commander"]

SETTINGS_DEFAULTS = {
    "clan_api_url": {},
    "servers": {},
}
SERVER_DEFAULTS = {
    "clans": {},
    "players": {}
}

CREDITS = 'Selfish + SML'


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)

class SCTag:
    """SuperCell tags."""

    def __init__(self, tag):
        """Init.

        Remove # if found.
        Convert to uppercase.
        """
        if tag is not None:
            if tag.startswith('#'):
                tag = tag[:1]
            tag = tag.upper()
        self._tag = tag

    @property
    def tag(self):
        """Return tag as str."""
        return self._tag

class CRRole(Enum):
    """Clash Royale role."""

    MEMBER = 1
    LEADER = 2
    ELDER = 3
    COLEADER = 4

    def __init__(self, type):
        """Init."""
        self.type = type

    @property
    def rolename(self):
        """Convert type to name"""
        roles = {
            self.MEMBER: "Member",
            self.LEADER: "Leader",
            self.ELDER: "Elder",
            self.COLEADER: "Co-Leader"
        }
        for k, v in roles.items():
            if k == self.type:
                return v
        return None


class CRClanType(Enum):
    """Clash Royale clan type."""

    OPEN = 1
    INVITE_ONLY = 2
    CLOSED = 3

    def __init__(self, type):
        """Init."""
        self.type = type

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


class CRClanData:
    """Clash Royale Clan data."""

    def __init__(self, **kwargs):
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

    @property
    def member_count_str(self):
        """Member count in #/50 format."""
        count = self.numberOfMembers
        if count is None:
            count = 0
        return '{}/50'.format(count)


class CRClanMemberData:
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
    def discord_member(self):
        """Discord user id."""
        return self._discord_member

    @discord_member.setter
    def discord_member(self, value):
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
        """Rank in clan with trend."""
        # rank diff is in reverse because lower is better
        # previous rank is 0 when user is new to clan
        rank_str = '--'
        if self.previousRank != 0:
            rank_diff = self.currentRank - self.previousRank
            if rank_diff > 0:
                rank_str = "↓ {}".format(rank_diff)
            elif rank_diff < 0:
                rank_str = "↑ {}".format(-rank_diff)
        return "{}\u00A0\u00A0\u00A0{}".format(self.currentRank, rank_str)


class SettingsException(Exception):
    pass

class ClanTagNotInSettings(SettingsException):
    pass

class ClanKeyNotInSettings(SettingsException):
    pass

class APIFetchError(SettingsException):
    pass

class Settings:
    """Cog settings"""

    DEFAULTS = {
        "clan_api_url": {},
        "servers": {},
    }
    SERVER_DEFAULTS = {
        "clans": {},
        "players": {}
    }

    def __init__(self, filepath):
        """Init."""
        self.filepath = filepath
        self.settings = dataIO.load_json(filepath)

    def init_server(self, server):
        """Initialized server settings.

        This will wipe all clan data and player data.
        """
        self.settings["servers"][server.id] = self.SERVER_DEFAULTS
        self.save()

    def init_clans(self, server):
        """Initialized clan settings."""
        self.settings["servers"][server.id]["clans"] = {}
        self.save()

    def check_server(self, server):
        """Make sure server exists in settings."""
        if server_id not in self.settings["servers"]:
            self.settings["servers"][server.id] = self.SERVER_DEFAULTS
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

    async def get_clan_data(self, server, key=None, tag=None) -> CRClanData:
        """Return data as CRClanData by key or tag

        Raise asyncio.TimeoutError if API is down.
        """
        if tag is None:
            if key is not None:
                tag = self.key2tag(server, key)

        if tag is None:
            return None

        data = await self.update_clan_data(tag)
        if data is None:
            return None
        return CRClanData(**data)

    async def update_clan_data(self, tag):
        """Update and save clan data from API."""
        tag = SCTag(tag).tag
        url = "{}{}".format(self.settings["clan_api_url"], tag)
        data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            pass
        except asyncio.TimeoutError:
            pass

        filename = os.path.join(PATH_CLANS, '{}.json'.format(tag))
        if data is not None:
            dataIO.save_json(filename, data)
            return data

        # try to load data from disk if loading from url failed
        if data is None:
            return dataIO.load_json(filename)
        return None

    async def update_data(self):
        """Update all data and save to disk."""
        for server_id in self.settings["servers"]:
            clans = self.settings["servers"][server_id]["clans"]
            for tag in clans.keys():
                await self.update_clan_data(tag)

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

    @property
    def clan_api_url(self):
        """Clan API URL."""
        return self.settings["clan_api_url"]

    @clan_api_url.setter
    def clan_api_url(self, value):
        """Set Clan API URL."""
        self.settings["clan_api_url"] = value
        self.save()

    @property
    def badge_url(self):
        """Clan Badge URL."""
        return self.settings["badge_url"]

    @badge_url.setter
    def clan_api_url(self, value):
        """lan Badge URL"""
        self.settings["badge_url"] = value
        self.save()


class CRClan:
    """Clash Royale Clan management."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = Settings(JSON)
        self.badges = dataIO.load_json(BADGES_JSON)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        """Loop task: update data daily."""
        await self.bot.wait_until_ready()
        await self.settings.update_data()
        await self.update_data()
        await asyncio.sleep(DATA_UPDATE_INTERVAL)
        if self is self.bot.get_cog('CRClan'):
            self.task = self.bot.loop.create_task(self.loop_task())

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def crclanset(self, ctx):
        """Set Clash Royale Data settings.

        Require: Clash Royale API by Selfish.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crclanset.command(name="init", pass_context=True)
    async def crclanset_init(self, ctx):
        """Init CR Clan: server settings."""
        server = ctx.message.server
        self.settings.init_server(server)
        await self.bot.say("Server settings initialized.")

    @crclanset.command(name="initclans", pass_context=True)
    async def crclanset_init(self, ctx):
        """Init CR Clan: clans settings."""
        server = ctx.message.server
        self.settings.init_clans(server)
        await self.bot.say("Clan settings initialized.")

    @crclanset.command(name="clanapi", pass_context=True)
    async def crclanset_clanapi(self, ctx, url):
        """CR Clan API URL base.

        Format:
        If path is http://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings.clan_api_url = url
        await self.bot.say("Clan API URL updated.")

    @crclanset.command(name="badgeurl", pass_context=True)
    async def crclanset_badgeurl(self, ctx, url):
        """badge URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings.badge_url = url
        await self.bot.say("Badge URL updated.")

    @crclanset.command(name="update", pass_context=True)
    async def crclanset_update(self, ctx):
        """Update data from api."""
        success = await self.update_data()
        if success:
            await self.bot.say("Data updated.")
        else:
            await self.bot.say("Data update failed.")

    @crclanset.command(name="add", pass_context=True)
    async def crclanset_add(self, ctx, tag=None, key=None, role_name=None):
        """Add clan tag(s).

        [p]crclanset add 2CCCP alpha

        tag: clan tag without the # sign
        key: human readable key for easier calls for data
        role: server role assignment

        """
        if tag is None:
            await send_cmd_help(ctx)
            return

        self.settings.add_clan(ctx.message.server, tag, key, role_name)

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
                self.settings.remove_clan(server, clantag)
            except ClanTagNotInSettings:
                await self.bot.say("{} is not in clan settings.".format(clantag))
            else:
                await self.bot.say("Removed #{} from clans.".format(clantag))

    @crclanset.command(name="key", pass_context=True)
    async def crclanset_key(self, ctx, tag, key):
        """Human readable key.

        This is used for running other commands to make
        fetching data easier without having to use
        clan tag every time.
        """
        server = ctx.message.server
        try:
            self.settings.set_clan_key(server, tag, key)
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

    @crclan.command(name="settag", pass_context=True, no_pm=True)
    async def crclan_settag(
            self, ctx, playertag=None, member: discord.Member = None):
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

        if playertag is None:
            await send_cmd_help(ctx)
            return

        playertag = SCTag(playertag).tag

        allowed = False
        if member is None:
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

        self.settings.set_player(server, member, playertag)

        # self.set_player_settings(server.id, playertag, member.id)

        await self.bot.say("Associated player tag with Discord Member.")

    @crclan.command(name="gettag", pass_context=True, no_pm=True)
    async def crclan_gettag(self, ctx, member: discord.Member = None):
        """Get playertag from Discord member."""
        server = ctx.message.server
        author = ctx.message.author
        if member is None:
            member = author
        tag = self.settings.member2tag(server, member)
        if tag is None:
            await self.bot.say("Cannot find associated player tag.")
            return
        await self.bot.say(
            "Player tag for {} is #{}".format(
                member.display_name, tag))

    @crclan.command(name="clankey", pass_context=True, no_pm=True)
    async def crclan_clankey(self, ctx, key, update=False):
        """Return clan roster by key.

        Key of each clan is set from [p]bsclan addkey
        """
        server = ctx.message.server
        tag = self.settings.key2tag(server, key)
        await ctx.invoke(self.crclan_clantag, tag)

    @crclan.command(name="clantag", pass_context=True, no_pm=True)
    async def crclan_clantag(self, ctx, clantag=None):
        """Clan info and roster by tag."""
        if clantag is None:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        data = None

        try:
            data = await self.settings.get_clan_data(server, tag=clantag)
        except ClanKeyNotInSettings:
            await self.bot.say("Cannot find key {} in settings.".format(key))
        except APIFetchError:
            await self.bot.say(
                "Error fetching data for clan tag #{} from API. "
                "Please try again later.".format(clantag))
        else:
            if data is None:
                await self.bot.say(
                    "Error fetching data for clan tag #{} from API. "
                    "Please try again later.".format(clantag))
            else:
                await self.bot.send_typing(ctx.message.channel)
                color = self.random_discord_color()

                em = self.embed_crclan_info(data)
                em.color = color
                await self.bot.say(embed=em)
                await self.send_roster(server, data, color=color)

    @crclan.command(name="info", pass_context=True, no_pm=True)
    async def crclan_info(self, ctx, key=None):
        """Information."""
        server = ctx.message.server

        await self.bot.send_typing(ctx.message.channel)

        try:
            clan_data = await self.settings.get_clan_data(server, key=key)
        except ClanKeyNotInSettings:
            await self.bot.say("Cannot find key {} in settings.".format(key))
        except APIFetchError:
            await self.bot.say(
                "Error fetching data from API for clan key {}. "
                "Please try again later.".format(key))
        else:
            if clan_data is None:
                await self.bot.say(
                    "Error fetching data from API for clan key {}. "
                    "Please try again later.".format(key))
            else:
                await self.bot.send_typing(ctx.message.channel)
                em = self.embed_crclan_info(clan_data)
                em.color = self.random_discord_color()
                await self.bot.say(embed=em)

    @crclan.command(name="roster", pass_context=True, no_pm=True)
    async def crclan_roster(self, ctx, key):
        """Return clan roster by key.

        Key of each clan is set from [p]bsclan addkey
        """
        server = ctx.message.server

        await self.bot.send_typing(ctx.message.channel)

        try:
            clan_data = await self.settings.get_clan_data(server, key=key)
        except ClanKeyNotInSettings:
            await self.bot.say("Cannot find key {} in settings.".format(key))
        except APIFetchError:
            await self.bot.say(
                "Error fetching data from API for clan key {}. "
                "Please try again later.".format(key))
        else:
            if clan_data is None:
                await self.bot.say(
                    "Error fetching data from API for clan key {}. "
                    "Please try again later.".format(key))
            else:
                await self.send_roster(server, clan_data, color=self.random_discord_color())

    @commands.has_any_role(*BOTCOMMANDER_ROLES)
    @crclan.command(name="multiroster", pass_context=True, no_pm=True)
    async def crclan_multiroster(self, ctx, *keys):
        """Return all list of rosters by keys.

        [p]crclan multiroster alpha bravo charlie
        """
        for key in keys:
            await ctx.invoke(self.crclan_roster, key)

    def embed_crclan_info(self, data: CRClanData):
        """Return clan info embed."""
        # data = CRClanData(**clan)
        em = discord.Embed(
            title=data.name,
            description=data.description)
        em.add_field(name="Clan Trophies", value=data.score)
        em.add_field(name="Type", value=CRClanType(data.type).typename)
        em.add_field(name="Required Trophies", value=data.requiredScore)
        em.add_field(name="Clan Tag", value=data.tag)
        em.add_field(name="Members", value=data.member_count_str)
        badge_url = self.settings.badge_url + data.badge_url
        em.set_thumbnail(url=badge_url)
        return em

    async def send_roster(self, server, data: CRClanData, **kwargs):
        """Send roster to destination according to context.

        Results are split in groups of 25
        because Discord Embeds allow 25 fields per embed.
        """
        members_out = grouper(25, data.members, None)
        if 'color' in kwargs:
            color = kwargs['color']
        else:
            color = self.random_discord_color()

        for page, members in enumerate(members_out, start=1):
            kwargs = {
                'server': server,
                'members': members,
                'title': data.name,
                'footer_text': '{} #{} - Page {}'.format(
                    data.name, data.tag, page),
                'footer_icon_url': self.settings.badge_url + data.badge_url
            }
            em = self.embed_roster(**kwargs)
            em.color = color
            await self.bot.say(embed=em)

    def embed_roster(
            self,
            server=None,
            title=None, members=None,
            footer_text=None, footer_icon_url=None):
        """Return clan roster as Discord embed.

        This represents a page of a roster.
        """
        em = discord.Embed(title=title)
        em.set_footer(text=footer_text, icon_url=footer_icon_url)
        for member in members:
            if member is not None:
                data = CRClanMemberData(**member)
                discord_member = self.settings.tag2member(server, data.tag)
                name = (
                    "{0.name}, {0.role_name} "
                    "(Lvl {0.expLevel})").format(data)
                value = (
                    "{0.score:,d}"
                    " | {0.donations: >4} d"
                    " | {0.clanChestCrowns: >3} c"
                    " | #{0.tag}").format(data)
                value = box(value, lang='py')
                mention = ''
                if discord_member is not None:
                    mention = discord_member.mention
                value = '{} {}{}'.format(
                    data.rank, mention, value)
                em.add_field(name=name, value=value, inline=False)
        return em


    async def update_data(self, clan_tag=None):
        """Perform data update from api."""
        success = False
        for server_id in self.settings["servers"]:
            clans = self.get_clans_settings(server_id)

            for tag, clan in clans.items():
                do_update = False
                if clan_tag is None:
                    do_update = True
                elif clan_tag == tag:
                    do_update = True
                if do_update:
                    data = await self.get_clan_data(tag)
                    if data is not None:
                        clans[tag].update(data)
                        success = True

            self.set_clans_settings(server_id, clans)
        return success



    @staticmethod
    def random_discord_color():
        """Return random color as an integer."""
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        return discord.Color(value=color)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)
    if not os.path.exists(PATH_CLANS):
        os.makedirs(PATH_CLANS)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, SETTINGS_DEFAULTS)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = CRClan(bot)
    bot.add_cog(n)


