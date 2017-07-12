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
from urllib.parse import urlunparse
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
JSON = os.path.join(PATH, "settings.json")
BADGES_JSON = os.path.join(PATH, "badges.json")

DATA_UPDATE_INTERVAL = timedelta(minutes=1).seconds

BOTCOMMANDER_ROLES = ["Bot Commander"]

SETTINGS_DEFAULTS = {
    "clan_api_url": {},
    "servers": {},
}
SERVER_DEFAULTS = {
    "clans": {},
    "players": {}
}


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class CRRole(Enum):
    """Clash Royale role."""

    MEMBER = 1
    LEADER = 2
    ELDER = 3
    COLEADER = 4


CR_ROLES = {
    CRRole.MEMBER: "Member",
    CRRole.LEADER: "Leader",
    CRRole.ELDER: "Elder",
    CRRole.COLEADER: "Co-Leader"
}


class CRClanType(Enum):
    """Clash Royale clan type."""

    OPEN = 1
    INVITE_ONLY = 2
    CLOSED = 3


CR_CLAN_TYPE = {
    CRClanType.OPEN.value: "Open",
    CRClanType.INVITE_ONLY.value: "Invite Only",
    CRClanType.CLOSED.value: "Closed"
}


class CRClanData:
    """Clash Royale Band data."""

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


class CRPlayerData:
    """Clash Royale player data."""

    def __init__(self, **kwargs):
        """Init.

        Expected list of keywords:
        From API:
            avatar
            clan
                badge
                badge_id
                high
                low
                member_count
                name
                requirement
                role
                role_id
                tag
                trophies
                type
                type_id
            brawler_count
            brawlers[]
                highest_trophies
                level
                name
                number
                trophies
                type
                value
            high
            highest_trophies
            low
            survival_wins
            tag
            total_experience
            trophies
            username
            wins
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


class CRClan:
    """Clash Royale Clan management."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.task = bot.loop.create_task(self.loop_task())
        self.settings = dataIO.load_json(JSON)
        self.badges = dataIO.load_json(BADGES_JSON)

    def __unload(self):
        self.task.cancel()

    async def loop_task(self):
        """Loop task: update data daily."""
        await self.bot.wait_until_ready()
        await self.update_data()
        await asyncio.sleep(DATA_UPDATE_INTERVAL)
        if self is self.bot.get_cog('CRClan'):
            self.task = self.bot.loop.create_task(self.loop_task())

    def check_server_settings(self, server_id):
        """Add server to settings if one does not exist."""
        if server_id not in self.settings["servers"]:
            self.settings["servers"][server_id] = SERVER_DEFAULTS
        dataIO.save_json(JSON, self.settings)

    def badge_url(self, badge_id):
        """Return Badge URL by badge ID."""
        return (
            "https://raw.githubusercontent.com"
            "/smlbiobot/smlbiobot.github.io/master"
            "/emblems/{}.png").format(self.badge[badge_id])

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def setcrclan(self, ctx):
        """Set Clash Royale Data settings.

        Require: Clash Royale API by Selfish.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcrclan.command(name="init", pass_context=True)
    async def setcrclan_init(self, ctx: Context):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings["servers"][server.id] = SERVER_DEFAULTS
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Server settings initialized.")

    @setcrclan.command(name="clanapi", pass_context=True)
    async def setcrclan_clanapi(self, ctx: Context, url):
        """CR Clan API URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings["clan_api_url"] = url

        server = ctx.message.server
        self.check_server_settings(server.id)

        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Band API URL updated.")

    @setcrclan.command(name="badgeurl", pass_context=True)
    async def setcrclan_badgeurl(self, ctx: Context, url):
        """badge URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings["badge_url"] = url

        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Badge URL updated.")

    async def get_clan_data(self, tag):
        """Return clan data JSON."""
        url = "{}{}".format(self.settings["clan_api_url"], tag)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                try:
                    data = await resp.json()
                except json.decoder.JSONDecodeError:
                    data = None
        return data

    async def update_data(self, clan_tag=None):
        """Perform data update from api."""
        for server_id in self.settings["servers"]:
            clans = self.get_clans_settings(server_id)

            for tag, clan in clans.items():
                do_update = False
                if clan_tag is None:
                    do_update = True
                elif clan_tag == tag:
                    do_update = True
                if do_update:
                    # async with self.get_clan_data(tag) as data:
                    data = await self.get_clan_data(tag)
                    if data is not None:
                        clans[tag].update(data)

            self.set_clans_settings(server_id, clans)
        return True

    def key2tag(self, server_id, key):
        """Convert clan key to clan tag."""
        clans = self.get_clans_settings(server_id)
        for tag, clan in clans.items():
            if clan["key"].lower() == key.lower():
                return tag
        return None

    def tag2member(self, tag=None):
        """Return Discord member from player tag."""
        for server in self.bot.servers:
            try:
                players = self.settings["servers"][server.id]["players"]
                for member_id, v in players.items():
                    if v == tag:
                        return server.get_member(member_id)
            except KeyError:
                pass
        return None

    @setcrclan.command(name="update", pass_context=True)
    async def setcrclan_update(self, ctx: Context):
        """Update data from api."""
        success = await self.update_data()
        if success:
            await self.bot.say("Data updated")

    def get_clans_settings(self, server_id):
        """Return clans in settings."""
        self.check_server_settings(server_id)
        return self.settings["servers"][server_id]["clans"]

    def set_clans_settings(self, server_id, data):
        """Set clans data in settings."""
        self.settings["servers"][server_id]["clans"] = data
        dataIO.save_json(JSON, self.settings)
        return True

    @setcrclan.command(name="add", pass_context=True)
    async def setcrclan_add(self, ctx: Context, tag=None, key=None, role=None):
        """Add clan tag(s).

        [p]setcrclan add 2CCCP alpha

        tag: clan tag without the # sign
        key: human readable key for easier calls for data
        role: server role assignment

        """
        if tag is None:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        self.check_server_settings(server.id)

        if tag.startswith('#'):
            tag = tag[1:]

        clans = self.get_clans_settings(server.id)
        if tag not in clans:
            clans[tag] = {
                'tag': tag,
                'key': key,
                'role': role
            }

        self.set_clans_settings(server.id, clans)

        await self.bot.say(
            'Added clan #{} with key: {} and role: {}'.format(
                tag, key, role))

        # await self.update_data()

    @setcrclan.command(name="remove", pass_context=True)
    async def setcrclan_remove(self, ctx: Context, *clantags):
        """Remove clan tag(s).

        [p]setbsclan remove LQQ 82RQLR 98VLYJ Q0YG8V

        """
        if not clantags:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        clans = self.get_clans_settings(server.id)

        for clantag in clantags:
            if clantag.startswith('#'):
                clantag = clantag[1:]

            removed = clans.pop(clantag, None)
            if removed is None:
                await self.bot.say("{} not in clan settings.".format(clantag))
                return

            self.set_clans_settings(server.id, clans)
            await self.bot.say("Removed #{} from clans.".format(clantag))

    @setcrclan.command(name="setkey", pass_context=True)
    async def setcrclan_setkey(self, ctx, tag, key):
        """Associate clan tag with human readable key.

        This is used for running other commands to make
        fetching data easier without having to use
        clan tag every time.
        """
        server = ctx.message.server
        clans = self.get_clans_settings(server.id)

        if tag not in clans:
            await self.bot.say(
                "{} is not a clan tag you have added".format(tag))
            return
        clans[tag]["key"] = key
        self.set_clans_settings(server.id, clans)
        await self.bot.say("Added {} for clan #{}.".format(key, tag))

    @commands.group(pass_context=True, no_pm=True)
    async def crclan(self, ctx: Context):
        """Clash Royale clan."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crclan.command(name="info", pass_context=True, no_pm=True)
    async def crclan_info(self, ctx: Context, key=None):
        """Information."""
        if key is None:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        clans = self.get_clans_settings(server.id)

        found_clan = None
        for tag, clan in clans.items():
            if clan["key"].lower() == key.lower():
                found_clan = clan
                break

        if found_clan is None:
            await self.bot.say("{} is not a valid key.".format(key))
            return

        tag = self.key2tag(server.id, key)
        await self.update_data(tag)

        em = self.embed_crclan_info(found_clan)
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        await self.bot.send_typing(ctx.message.channel)
        em.color = discord.Color(value=color)
        await self.bot.say(embed=em)

    def embed_crclan_info(self, clan):
        """Return clan info embed."""
        data = CRClanData(**clan)
        em = discord.Embed(
            title=data.name,
            description=data.description)
        em.add_field(name="Band Trophies", value=data.score)
        em.add_field(name="Type", value=CR_CLAN_TYPE[data.type])
        em.add_field(name="Required Trophies", value=data.requiredScore)
        em.add_field(name="Clan Tag", value=data.tag)
        em.add_field(
            name="Members", value=data.member_count_str)
        badge_url = self.settings["badge_url"] + data.badge_url
        em.set_thumbnail(url=badge_url)
        # em.set_author(name=data.name)
        return em

    @commands.has_any_role(*BOTCOMMANDER_ROLES)
    @crclan.command(name="roster", pass_context=True, no_pm=True)
    async def crclan_roster(self, ctx: Context, key):
        """Return clan roster by key.

        Key of each clan is set from [p]bsclan addkey
        """
        server = ctx.message.server
        await self.bot.send_typing(ctx.message.channel)
        clans = self.get_clans_settings(server.id)
        clan_result = None
        for k, clan in clans.items():
            data = CRClanData(**clan)
            if hasattr(data, "key"):
                if data.key == key:
                    clan_result = data
                    break

        if clan_result is None:
            await self.bot.say("Cannot find key {} in settings.".format(key))
            return

        members = clan_result.members
        tag = self.key2tag(server.id, key)
        await self.update_data(tag)

        # split results as list of 25
        members_out = grouper(25, members, None)
        color = self.random_color()
        page = 1
        for members in members_out:
            em = self.embed_crclan_roster(members)
            em.title = clan_result.name
            # em.description = (
            #     "Tag: {} | "
            #     "Required Trophies: {}").format(
            #         clan_result.tag, clan_result.requiredScore)
            em.color = discord.Color(value=color)
            badge_url = self.settings["badge_url"] + data.badge_url
            em.set_footer(
                text="Page {}".format(page),
                icon_url=badge_url)
            await self.bot.say(embed=em)
            page = page + 1

    def embed_crclan_roster(self, members):
        """Return clan roster embed."""
        em = discord.Embed(title=" ")
        for member in members:
            if member is not None:
                data = CRClanMemberData(**member)
                name = (
                    "{0.name}, {0.role_name} "
                    "(Lvl {0.expLevel}) ").format(data)
                # mention = ""
                # member = self.tag2member(data.tag)
                # if member is not None:
                #     mention = '\n{}'.format(member.mention)
                # data.mention = mention
                value = (
                    "{0.score:,d}"
                    " | {0.donations: >4} d"
                    " | {0.clanChestCrowns: >3} c"
                    " | #{0.tag}").format(data)
                # value = (
                #     "`{0.score:,d}` "
                #     "| `{0.donations: >4}` donations "
                #     "| `{0.clanChestCrowns: >4}` crowns"
                #     "| `#{0.tag}`").format(data)
                value = box(value, lang='py')
                em.add_field(name=name, value=value, inline=False)
        return em

    @crclan.command(name="profile", pass_context=True, no_pm=True)
    async def crclan_profile(self, ctx, member: discord.Member=None):
        """Return player profile by Discord member name or id."""
        server = ctx.message.server
        players = self.settings["servers"][server.id]["players"]

        if member is None:
            member = ctx.message.author

        if member.id not in players:
            await self.bot.say(
                "Member has not registered a player tag yet.\n"
                "Use `!crclan settag` to set it.")
            return

        await ctx.invoke(self.crclan_profiletag, players[member.id])

    @crclan.command(name="profiletag", pass_context=True, no_pm=True)
    async def crclan_profiletag(self, ctx, tag=None):
        """Return player profile by player tag."""
        if tag is None:
            await send_cmd_help(ctx)
            return

        data = await self.get_player_data(tag)
        if not data:
            await self.bot.say(
                "Error fetching player data. "
                "Please make sure that player tag is set correctly. "
                "It is set to #{} at the moment. "
                "Run `!crclan settag` if you need to update it.".format(tag))
            return

        player = CRPlayerData(**data)
        server = ctx.message.server
        player.discord_member = self.get_discord_member(server, tag)
        await self.bot.say(embed=self.embed_player(player))

    async def get_player_data(self, tag):
        """Return clan data JSON."""
        url = "{}{}".format(self.settings["player_api_url"], tag)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                try:
                    data = await resp.json()
                except json.decoder.JSONDecodeError:
                    data = None
        return data

    def embed_player(self, player: CRPlayerData):
        """Return player embed."""
        em = discord.Embed(
            title=player.username,
            description="#{}".format(player.tag))
        clan = CRClanData(**player.clan)
        em.color = discord.Color(value=self.random_color())

        if player.discord_member is not None:
            em.description = '{} {}'.format(
                em.description,
                player.discord_member.mention)

        em.add_field(name=clan.name, value=clan.role)
        em.add_field(name="Trophies", value=player.trophies)
        em.add_field(name="Victories", value=player.wins)
        em.add_field(name="Showdown Victories", value=player.survival_wins)
        em.add_field(name="Highest Trophies", value=player.highest_trophies)
        em.add_field(name="Brawlers", value=player.brawler_count)

        for brawler in player.brawlers:
            data = BSBrawlerData(**brawler)
            emoji = self.brawler_emoji(data.name)
            if emoji is None:
                emoji = ''
            name = '{} {} (Level {})'.format(data.name, emoji, data.level)
            trophies = '{}/{}'.format(data.trophies, data.highest_trophies)
            em.add_field(
                name=name,
                value=trophies)

        text = (
            '{0.name}'
            ' Trophies: {0.trophies}'
            ' Requirement: {0.requirement}'
            ' Tag: {0.tag}'
            ' Type: {0.type}').format(clan)

        em.set_footer(
            text=text,
            icon_url=clan.badge_url)

        return em

    def get_discord_member(self, server, player_tag):
        """Return Discord member if tag is associated."""
        member_id = None
        try:
            players = self.settings["servers"][server.id]["players"]
            for k, v in players.items():
                if v == player_tag:
                    member_id = k
        except KeyError:
            pass
        if member_id is None:
            return None
        return server.get_member(member_id)

    def set_player_settings(self, server_id, playertag, member_id):
        """Set player tag to member id.

        Remove previously stored playertags associated with member_id.
        """
        if "players" not in self.settings["servers"][server_id]:
            self.settings["servers"][server_id]["players"] = {}
        players = self.settings["servers"][server_id]["players"]
        players[member_id] = playertag
        self.settings["servers"][server_id]["players"] = players
        dataIO.save_json(JSON, self.settings)

    @crclan.command(name="settag", pass_context=True, no_pm=True)
    async def crclan_settag(
            self, ctx, playertag=None, member: discord.Member=None):
        """Set playertag to discord member.

        Setting tag for yourself:
        !crclan settag 889QC9

        Setting tag for others (requires Bot Commander role):
        !crclan settag 889QC9 SML
        !crclan settag 889QC9 @SML
        !crclan settag 889QC9 @SML#6443
        """
        server = ctx.message.server
        author = ctx.message.author

        if playertag is None:
            await send_cmd_help(ctx)
            return

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

        self.set_player_settings(server.id, playertag, member.id)

        await self.bot.say("Associated player tag with Discord Member.")

    @staticmethod
    def random_color():
        """Return random color as an integer."""
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        return color

    def brawler_emoji(self, name):
        """Emoji of the brawler.

        Find emoji against all known servers
        to look for match
        <:emoji_name:emoji_id>
        """
        for server in self.bot.servers:
            for emoji in server.emojis:
                if emoji.name == name:
                    return '<:{}:{}>'.format(emoji.name, emoji.id)
        return None



def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


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


