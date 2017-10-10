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
from datetime import timedelta
from random import choice

import discord
from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

PATH = os.path.join("data", "bsdata")
JSON = os.path.join(PATH, "settings.json")

DATA_UPDATE_INTERVAL = timedelta(minutes=5).seconds

RESULTS_MAX = 3
PAGINATION_TIMEOUT = 20

BOTCOMMANDER_ROLES = ["Bot Commander"]

SETTINGS_DEFAULTS = {
    "band_api_url": {},
    "player_api_url": {},
    "servers": {},
}
SERVER_DEFAULTS = {
    "bands": {},
    "players": {}
}
BAND_DEFAULTS = {
    "name": None,
    "role": "",
    "tag": "",
    "members": []
}
# this one here is mostly for reference
MEMBER_DEFAULTS = {
    "experience_level": 0,
    "id": {
        "high": 0,
        "low": 0,
        "unsigned": False
    },
    "name": "Name",
    "role": "Member",
    "role_id": 1,
    "tag": "XXX",
    "trophies": 0,
    "unk1": 0
}


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


def format_timedelta(td):
    """Timedelta in 4 hr 2 min 3 sec"""
    l = str(td).split(':')
    return '{0[0]} hr {0[1]} min {0[2]} sec'.format(l)


async def fetch(url, timeout=10, headers=None):
    """Fetch URL.

    :param session: aiohttp.ClientSession
    :param url: URL
    :return: Response in JSON
    """
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=timeout) as resp:
                data = await resp.json()
                return data
    except asyncio.TimeoutError:
        return None
    except aiohttp.ClientResponseError:
        return None
    return None


class BotEmoji:
    """Emojis available in bot."""

    def __init__(self, bot, mapping=None):
        """Init.

        map: a dictionary mapping a key to to an emoji name.
        """
        self.bot = bot
        self.mapping = mapping

    def name(self, name):
        """Emoji by name."""
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    def named(self, name):
        """Emoji object by name"""
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return emoji
        return None

    def key(self, key):
        """Chest emojis by api key name or key.

        name is used by this cog.
        key is values returned by the api.
        Use key only if name is not set
        """
        if key in self.mapping:
            name = self.mapping[key]
            return self.name(name)
        return ''

    def key_to_name(self, key):
        """Return emoji name by key."""
        if key in self.mapping:
            return self.mapping[key]
        return None


class BSBandModel:
    """Brawl Stars Band data."""

    def __init__(self, data=None):
        """Init.
        From cog:
            key
            role
            tag
        """
        self.data = data
        self.members = []

    """
    API Properties
    """

    @property
    def name(self):
        return self.data.get('name', None)

    @property
    def tag(self):
        return self.data.get('tag', None)

    @property
    def badge_id(self):
        return self.data.get('badge_id', None)

    @property
    def badge_export(self):
        return self.data.get('badge_export', None)

    @property
    def type_id(self):
        return self.data.get('type_id', None)

    @property
    def type(self):
        return self.data.get('type', None)

    @property
    def member_count(self):
        return self.data.get('member_count', None)

    @property
    def score(self):
        return self.data.get('score', None)

    @property
    def required_score(self):
        return self.data.get('required_score', None)

    @property
    def description(self):
        return self.data.get('description', None)

    @property
    def description_clean(self):
        return self.data.get('description_clean', None)

    """
    Property used for BSPlayerModel
    """

    @property
    def role(self):
        return self.data.get('role', None)

    """
    Model Properties
    """

    @property
    def member_count_str(self):
        """Member count in #/50 format."""
        count = self.member_count
        if count is None:
            count = 0
        return '{}/100'.format(count)

    @property
    def badge_url(self):
        """Return band emblem URL."""
        return (
            "http://smlbiobot.github.io/img"
            "/bs-badge/{}.png").format(self.badge_export)


class BSBandMemberModel:
    """Brawl Stars Member data."""

    def __init__(self, data=None):
        """Init.
        """
        self.data = data
        self._discord_member = None

    @property
    def tag(self):
        return self.data.get('tag', None)

    @property
    def name(self):
        return self.data.get('name', None)

    @property
    def role_id(self):
        return self.data.get('role_id', None)

    @property
    def experience_level(self):
        return self.data.get('experience_level', None)

    @property
    def trophies(self):
        return self.data.get('trophies', None)

    @property
    def avatar(self):
        return self.data.get('avatar', None)

    @property
    def avatar_export(self):
        return self.data.get('avatar_export', None)

    @property
    def role(self):
        return self.data.get('role', None)

    @property
    def discord_member(self):
        """Discord user id."""
        return self._discord_member

    @discord_member.setter
    def discord_member(self, value):
        """Discord user id."""
        self._discord_member = value


class BSBrawlerModel:
    """Brawl Stars Brawler data."""

    def __init__(self, data=None):
        """Init.
        """
        self.data = data

    @property
    def tid(self):
        return self.data.get('tid', None)

    @property
    def name(self):
        return self.data.get('name', None)

    @property
    def icon_export(self):
        return self.data.get('icon_export', None)

    @property
    def id(self):
        return self.data.get('id', None)

    @property
    def trophies(self):
        return self.data.get('trophies', None)

    @property
    def highest_trophies(self):
        return self.data.get('highest_trophies', None)

    @property
    def level(self):
        return self.data.get('level', None)

    @property
    def rarity(self):
        return self.data.get('rarity', None)

    @property
    def rank(self):
        return self.data.get('rank', None)

    @property
    def rank_export(self):
        return self.data.get('rank_export', None)

    @property
    def required_trophies_for_next_rank(self):
        return self.data.get('required_trophies_for_next_rank', None)


class BSPlayerModel:
    """Brawl Stars player data."""

    class BSPlayerBandModel:
        """Band model inside player.
        
        This is different than the BSBandModel because API uses different field name
        and has different data structure."""

        def __init__(self, data=None):
            """Init.
            From cog:
                key
                role
                tag
            """
            self.data = data
            self.members = []

        """
        API Properties
        """

        @property
        def name(self):
            return self.data.get('name', None)

        @property
        def tag(self):
            return self.data.get('tag', None)

        @property
        def badge_id(self):
            return self.data.get('badge_id', None)

        @property
        def badge_export(self):
            return self.data.get('badge_export', None)

        @property
        def type_id(self):
            return self.data.get('type_id', None)

        @property
        def type(self):
            return self.data.get('type', None)

        @property
        def member_count(self):
            return self.data.get('member_count', None)

        @property
        def score(self):
            return self.data.get('trophies', None)

        @property
        def required_score(self):
            return self.data.get('required_trophies_to_join', None)

        @property
        def role(self):
            return self.data.get('role', None)

        """
        Model Properties
        """

        @property
        def badge_url(self):
            """Return band emblem URL."""
            return (
                "http://smlbiobot.github.io/img"
                "/bs-badge/{}.png").format(self.badge_export)

    def __init__(self, data=None):
        """Init."""
        self.data = data
        self._discord_member = None
        self._brawlers = None
        self._band = None

    """
    API properties
    """

    @property
    def username(self):
        return self.data.get('username', None)

    @property
    def tag(self):
        return self.data.get('tag', None)

    @property
    def brawler_count(self):
        return self.data.get('brawler_count', None)

    @property
    def brawlers(self):
        if self._brawlers is not None:
            return self._brawlers
        blist = self.data.get('brawlers', None)
        if blist is None:
            return None
        self._brawlers = []
        for b in blist:
            b = BSBrawlerModel(data=b)
            self._brawlers.append(b)
        return self._brawlers

    @property
    def value_count(self):
        return self.data.get('value_count', None)

    @property
    def wins(self):
        return self.data.get('wins', None)

    @property
    def total_experience(self):
        return self.data.get('total_experience', None)

    @property
    def trophies(self):
        return self.data.get('trophies', None)

    @property
    def highest_trophies(self):
        return self.data.get('highest_trophies', None)

    @property
    def account_age_in_days(self):
        return self.data.get('account_age_in_days', None)

    @property
    def avatar(self):
        return self.data.get('avatar', None)

    @property
    def survival_wins(self):
        return self.data.get('survival_wins', None)

    @property
    def avatar_export(self):
        return self.data.get('avatar_export', None)

    @property
    def level(self):
        return self.data.get('level', None)

    @property
    def current_experience(self):
        return self.data.get('current_experience', None)

    @property
    def required_experience(self):
        return self.data.get('required_experience', None)

    @property
    def band(self):
        if self._band is not None:
            return self._band
        b = self.data.get('band', None)
        if b is None:
            return None
        self._band = BSPlayerModel.BSPlayerBandModel(data=b)
        return self._band

    """
    Cog properties
    """

    @property
    def discord_member(self):
        """Discord user id."""
        return self._discord_member

    @discord_member.setter
    def discord_member(self, value):
        """Discord user id."""
        self._discord_member = value


class BSEventModel:
    """Brawl Stars event model."""

    def __init__(self, data=None):
        self.data = data

    @property
    def time(self):
        return self.data.get('time', None)

    @property
    def time_starts_in(self):
        if self.time is None:
            return 0
        return self.time.get('starts_in', 0)

    @property
    def time_ends_in(self):
        if self.time is None:
            return 0
        return self.time.get('ends_in', 0)

    @property
    def coins(self):
        return self.data.get('coins', None)

    @property
    def coins_free(self):
        if self.coins is None:
            return 0
        return self.coins.get('free', 0)

    @property
    def coins_first_win(self):
        if self.coins is None:
            return 0
        return self.coins.get('first_win', 0)

    @property
    def coins_max(self):
        if self.coins is None:
            return 0
        return self.coins.get('max', 0)

    @property
    def number(self):
        return self.data.get('number', None)

    @property
    def xp_multiplier(self):
        return self.data.get('xp_multiplier', None)

    @property
    def index(self):
        return self.data.get('index', None)

    @property
    def location(self):
        return self.data.get('location', None)

    @property
    def type(self):
        return self.data.get('type', None)

    @property
    def mode(self):
        return self.data.get('mode', None)

    @property
    def mode_name(self):
        if self.mode is None:
            return ''
        return self.mode.get('name', '')

    @property
    def mode_color(self):
        if self.mode is None:
            return ''
        return self.mode.get('color', '')

    @property
    def mode_description(self):
        if self.mode is None:
            return ''
        return self.mode.get('description', '')

    @property
    def info(self):
        return self.data.get('info', None)

    @property
    def map_url(self):
        return self.data.get('map', None)


class BSDataServerSettings:
    """Brawl Stars Data server settings."""

    def __init__(self, server):
        self.server = server


class BSDataSettings:
    """Brawl Stars Data Settings."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def save(self):
        """Save settings to file."""
        dataIO.save_json(JSON, self.settings)

    def init_server(self, server):
        """Initialize server settings."""
        self.settings["servers"][server.id] = SERVER_DEFAULTS
        self.save()

    def check_server_settings(self, server):
        """Add server to settings if one does not exist."""
        if server.id not in self.settings["servers"]:
            self.settings["servers"][server.id] = SERVER_DEFAULTS
        self.save()

    @property
    def servers(self):
        return self.settings["servers"]

    def server_settings(self, server):
        self.check_server_settings(server)
        return self.settings["servers"][server.id]

    @property
    def player_api_url(self):
        return self.settings["player_api_url"]

    @player_api_url.setter
    def player_api_url(self, value):
        self.settings["player_api_url"] = value
        self.save()

    @property
    def band_api_url(self):
        return self.settings["band_api_url"]

    @band_api_url.setter
    def band_api_url(self, value):
        self.settings["band_api_url"] = value
        self.save()

    @property
    def event_api_url(self):
        return self.settings["event_api_url"]

    @event_api_url.setter
    def event_api_url(self, value):
        self.settings["event_api_url"] = value
        self.save()

    @property
    def api_auth(self):
        return self.settings["api_auth"]

    @api_auth.setter
    def api_auth(self, value):
        self.settings["api_auth"] = value
        self.save()

    def get_bands_settings(self, server):
        """Return bands in settings."""
        return self.server_settings(server)["bands"]

    def set_bands_settings(self, server, data):
        """Set bands data in settings."""
        self.server_settings(server)["bands"] = data
        self.save()
        return True

    def get_players(self, server):
        """Return players on a server."""
        return self.server_settings(server)["players"]

    def get_server(self, server):
        return self.server_settings(server)

    def add_player(self, server, player_tag, member_id):
        """Add or edit a player."""
        if "players" not in self.settings["servers"][server.id]:
            self.settings["servers"][server.id]["players"] = {}
        self.settings["servers"][server.id]["players"][member_id] = player_tag
        self.save()


class BSData:
    """Brawl Stars Clan management."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = BSDataSettings(bot)
        self.bot_emoji = BotEmoji(
            bot,
            mapping={
                "Smash & Grab": "icon_smashgrab",
                "Heist": "icon_heist",
                "Bounty": "icon_bounty",
                "Showdown": "icon_showdown",
                "Brawl Ball": "icon_brawlball"
            }
        )
        self.sessions = {}

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def bsdataset(self, ctx):
        """Set Brawl Stars Data settings.

        Require: Brawl Stars API by Harmiox.
        May not work for you."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @bsdataset.command(name="init", pass_context=True)
    async def bsdataset_init(self, ctx):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings.init_server(server)
        await self.bot.say("Server settings initialized.")

    @bsdataset.command(name="auth", pass_context=True)
    async def bsdataset_auth(self, ctx, token):
        """Authorization (token)."""
        self.settings.api_auth = token
        await self.bot.say("Authorization (token) updated.")

    @bsdataset.command(name="bandapi", pass_context=True)
    async def bsdataset_bandapi(self, ctx, url):
        """BS Band API URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings.band_api_url = url
        await self.bot.say("Band API URL updated.")

    @bsdataset.command(name="playerapi", pass_context=True)
    async def bsdataset_playerapi(self, ctx: Context, url):
        """BS Member API URL base.

        Format:
        If path is hhttp://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings.player_api_url = url
        await self.bot.say("Player API URL updated.")

    @bsdataset.command(name="eventapi", pass_context=True)
    async def bsdataset_playerapi(self, ctx: Context, url):
        """BS Event API URL base.

        Format:
        If path is http://domain.com/path/
        Enter http://domain.com/path/
        """
        self.settings.event_api_url = url
        await self.bot.say("Event API URL updated.")

    async def get_band_data(self, tag):
        """Return band data JSON."""
        url = "{}{}".format(self.settings.band_api_url, tag)
        data = await fetch(url, headers={"Authorization": self.settings.api_auth})
        return data

    def tag2member(self, tag=None):
        """Return Discord member from player tag."""
        for server in self.bot.servers:
            try:
                players = self.settings.get_players(server)
                for member_id, v in players.items():
                    if v == tag:
                        return server.get_member(member_id)
            except KeyError:
                pass
        return None

    @bsdataset.command(name="add", pass_context=True)
    async def bsdataset_add(self, ctx: Context, *clantags):
        """Add clan tag(s).

        [p]setbsband add LQQ 82RQLR 98VLYJ Q0YG8V

        """
        if not clantags:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        # self.check_server_settings(server.id)

        for clantag in clantags:
            if clantag.startswith('#'):
                clantag = clantag[1:]

            bands = self.settings.get_bands_settings(server)
            if clantag not in bands:
                bands[clantag] = BAND_DEFAULTS

            self.settings.set_bands_settings(server, bands)

            await self.bot.say("added Band with clan tag: #{}".format(clantag))

        await self.update_data()

    @bsdataset.command(name="remove", pass_context=True)
    async def bsdataset_remove(self, ctx: Context, *clantags):
        """Remove clan tag(s).

        [p]setbsband remove LQQ 82RQLR 98VLYJ Q0YG8V

        """
        if not clantags:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        bands = self.settings.get_bands_settings(server)

        for clantag in clantags:
            if clantag.startswith('#'):
                clantag = clantag[1:]

            removed = bands.pop(clantag, None)
            if removed is None:
                await self.bot.say("{} not in clan settings.".format(clantag))
                return

            self.settings.set_bands_settings(server, bands)
            await self.bot.say("Removed #{} from bands.".format(clantag))

    @bsdataset.command(name="setkey", pass_context=True)
    async def bsdataset_setkey(self, ctx, tag, key):
        """Associate band tag with human readable key.

        This is used for running other commands to make
        fetching data easier without having to use
        band tag every time.
        """
        server = ctx.message.server
        bands = self.settings.get_bands_settings(server)

        if tag not in bands:
            await self.bot.say(
                "{} is not a band tag you have added".format(tag))
            return
        bands[tag]["key"] = key
        self.settings.set_bands_settings(server, bands)
        await self.bot.say("Added {} for band #{}.".format(key, tag))

    @commands.group(pass_context=True, no_pm=True)
    async def bsdata(self, ctx: Context):
        """Brawl Stars band."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @bsdata.command(name="info", pass_context=True, no_pm=True)
    async def bsdata_info(self, ctx: Context):
        """Information."""
        server = ctx.message.server
        bands = self.settings.get_bands_settings(server)
        for k, band in bands.items():
            # update band data if it was never fetched
            if band["name"] is None:
                await self.update_data(band["tag"])
        embeds = [self.embed_bsdata_info(band) for tag, band in bands.items()]
        embeds = sorted(embeds, key=lambda x: x.title)

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        for em in embeds:
            em.color = discord.Color(value=color)
            await self.bot.say(embed=em)

    def embed_bsdata_info(self, band):
        """Return band info embed."""
        band_model = BSBandModel(data=band)
        em = discord.Embed(
            title=band_model.name,
            description=band_model.description)
        em.add_field(name="Band Trophies", value='{:,}'.format(band_model.score))
        em.add_field(name="Type", value=band_model.type)
        em.add_field(name="Required Trophies", value='{:,}'.format(band_model.required_score))
        em.add_field(name="Band Tag", value=band_model.tag)
        em.add_field(
            name="Members", value=band_model.member_count_str)
        em.set_thumbnail(url=band_model.badge_url)
        # em.set_author(name=data.name)
        return em

    @bsdata.command(name="roster", pass_context=True, no_pm=True)
    async def bsdata_roster(self, ctx: Context, key):
        """Return band roster by key.

        Key of each band is set from [p]bsband addkey
        """
        server = ctx.message.server
        bands = self.settings.get_bands_settings(server)
        band_result = None
        for k, band in bands.items():
            data = BSBandModel(data=band)
            if hasattr(data, "key"):
                if data.key == key:
                    band_result = data
                    break

        if band_result is None:
            await self.bot.say("Cannot find key {} in settings.".format(key))
            return

        members = band_result.members
        # split results as list of 24
        # because embeds can only contain 25 fields
        # if fields are displayed inline,
        # 24 can fit both 2 and 3-column layout
        members_out = grouper(24, members, None)
        color = random_discord_color()
        page = 1
        for members in members_out:
            em = self.embed_bsdata_roster(members)
            em.title = band_result.name
            em.description = (
                "Tag: {} | "
                "Required Trophies: {}").format(
                band_result.tag, band_result.required_score)
            em.color = color
            # em.set_thumbnail(url=band_result.badge_url_base)
            em.set_footer(
                text="Page {}".format(page),
                icon_url=band_result.badge_url, )
            await self.bot.say(embed=em)
            page = page + 1

    def embed_bsdata_roster(self, members):
        """Return band roster embed."""
        em = discord.Embed(title=".")
        for member in members:
            if member is not None:
                data = BSBandMemberModel(**member)
                name = "{}, {}".format(data.name, data.role)
                mention = ""
                member = self.tag2member(data.tag)
                if member is not None:
                    mention = '\n{}'.format(member.mention)
                value = "{}, {} XP, #{}{}".format(
                    data.trophies,
                    data.experience_level,
                    data.tag,
                    mention)
                em.add_field(name=name, value=value)
        return em

    @bsdata.command(name="profile", pass_context=True, no_pm=True)
    async def bsdata_profile(self, ctx, member: discord.Member = None):
        """Return player profile by Discord member name or id."""
        server = ctx.message.server
        players = self.settings.get_players(server)

        if member is None:
            member = ctx.message.author

        if member.id not in players:
            await self.bot.say(
                "Member has not registered a player tag yet.\n"
                "Use `!bsdata settag` to set it.")
            return

        await ctx.invoke(self.bsdata_profiletag, players[member.id])

    @bsdata.command(name="profiletag", pass_context=True, no_pm=True)
    async def bsdata_profiletag(self, ctx, tag=None):
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
                "Run `!bsdata settag` if you need to update it.".format(tag))
            return

        player = BSPlayerModel(data=data)
        server = ctx.message.server
        player.discord_member = self.get_discord_member(server, tag)

        for em in self.player_embeds(player, color=random_discord_color()):
            await self.bot.say(embed=em)

    async def get_player_data(self, tag):
        """Return player data JSON."""
        url = "{}{}".format(self.settings.player_api_url, tag)
        data = await fetch(url, headers={"Authorization": self.settings.api_auth})
        return data

    async def get_player_model(self, tag):
        """Return player data in BSPlayerModel"""
        data = await self.get_player_data(tag)
        if data is None:
            return None
        return BSPlayerModel(data=data)

    def player_embeds(self, player: BSPlayerModel, color=None):
        """Return player embed."""
        embeds = []

        em = discord.Embed(
            title=player.username,
            description="#{}".format(player.tag),
            color=color)

        if player.discord_member is not None:
            em.description = '{} {}'.format(
                em.description,
                player.discord_member.mention)

        def fmt(value, type):
            """Format value by type."""
            if value is None:
                return ''
            if type == int:
                return '{:,}'.format(value)

        em.add_field(name=player.band.name, value=player.band.role)
        em.add_field(name="Level: XP",
                     value='{0.level}: {0.current_experience:,} / {0.required_experience:,}'.format(player))
        em.add_field(name="Trophies {}".format(self.bot_emoji.name('trophy_bs')), value=fmt(player.trophies, int))
        em.add_field(name="Highest Trophies {}".format(self.bot_emoji.name('trophy_bs')),
                     value=fmt(player.highest_trophies, int))
        em.add_field(name="Victories", value=fmt(player.wins, int))
        em.add_field(name="Showdown Victories", value=fmt(player.survival_wins, int))

        em.set_thumbnail(
            url='https://smlbiobot.github.io/bs-emoji-servers/avatars/{}.png'.format(
                player.avatar_export))

        embeds.append(em)

        # - Brawlers
        em = discord.Embed(
            title='Brawlers',
            descripton=fmt(player.brawler_count, int),
            color=color)

        for brawler in player.brawlers:
            icon_export = brawler.icon_export
            emoji = self.bot_emoji.name(icon_export)
            name = '{emoji} {name}'.format(
                name=brawler.name,
                emoji=emoji,
                level=brawler.level,
                level_emoji=self.bot_emoji.name('lvl'))
            value = '{trophies} / {pb} ({level} upg)'.format(
                trophies=brawler.trophies,
                pb=brawler.highest_trophies,
                level=brawler.level,
                level_emoji=self.bot_emoji.name('lvl'))
            em.add_field(
                name=name,
                value=value)

        text = (
            '{0.name}'
            ' Trophies: {0.score:,}'
            ' Requirement: {0.required_score:,}'
            ' Tag: {0.tag}'
            ' Type: {0.type}').format(player.band)

        em.set_footer(
            text=text,
            icon_url=player.band.badge_url)

        embeds.append(em)
        return embeds

    def get_discord_member(self, server, player_tag):
        """Return Discord member if tag is associated."""
        member_id = None
        try:
            players = self.settings.get_players(server)
            for k, v in players.items():
                if v == player_tag:
                    member_id = k
        except KeyError:
            pass
        if member_id is None:
            return None
        return server.get_member(member_id)

    def set_player_settings(self, server, playertag, member_id):
        """Set player tag to member id.

        Remove previously stored playertags associated with member_id.
        """
        self.settings.add_player(server, playertag, member_id)
        # if "players" not in self.settings["servers"][server_id]:
        #     self.settings["servers"][server_id]["players"] = {}
        # players = self.settings["servers"][server_id]["players"]
        # players[member_id] = playertag
        # self.settings["servers"][server_id]["players"] = players
        # dataIO.save_json(JSON, self.settings)

    @bsdata.command(name="settag", pass_context=True, no_pm=True)
    async def bsdata_settag(
            self, ctx, playertag=None, member: discord.Member = None):
        """Set playertag to discord member.

        Setting tag for yourself:
        !bsdata settag 889QC9

        Setting tag for others (requires Bot Commander role):
        !bsdata settag 889QC9 SML
        !bsdata settag 889QC9 @SML
        !bsdata settag 889QC9 @SML#6443
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

        self.set_player_settings(server, playertag, member.id)

        await self.bot.say("Associated player tag with Discord Member.")

    @bsdata.command(name="events", pass_context=True)
    async def bsdata_events(self, ctx, type="now"):
        """Return events.
        
        [p]bsdata events 
        [p]bsdata events now
        [p]bsdata events later
        """
        author = ctx.message.author
        server = ctx.message.server
        channel = ctx.message.channel

        await self.bot.type()
        url = self.settings.event_api_url
        data = await fetch(url, headers={"Authorization": self.settings.api_auth})
        if data is None:
            await self.bot.say("Error fetching events from API.")
            return
        event_data = data[type]

        event_models = (BSEventModel(data=e) for e in event_data)

        await self.bot.type()

        message = None
        for i, e in enumerate(event_models):
            if i == 0:
                message = await self.bot.say(embed=self.event_embed(e))
            emoji = self.bot_emoji.named('number{}'.format(i+1))
            await self.bot.add_reaction(message, emoji)

        self.sessions[author.id] = {
            "data": event_data,
            "message_id": message.id,
            "channel_id": channel.id
        }

    def event_embed(self, event_model, color=None):
        """BS event embed."""
        e = event_model

        if color is None:
            color = discord.Color(value=int(e.mode_color[1:], 16))

        em = discord.Embed(
            title=e.mode_name,
            description=e.mode_description,
            color=color,
            url=e.map_url
        )
        em.add_field(name="Location", value=e.location)
        em.add_field(name="Type", value=e.type)
        if e.time_starts_in == 0:
            starts_in_value = 'Started'
        else:
            starts_in_value = format_timedelta(dt.timedelta(seconds=e.time_starts_in))
        em.add_field(
            name="Starts in {}".format(self.bot_emoji.name("timer")),
            value=starts_in_value)
        em.add_field(
            name="Ends in {}".format(self.bot_emoji.name("timer")),
            value=format_timedelta(dt.timedelta(seconds=e.time_ends_in)))
        em.add_field(
            name="Coins {}".format(self.bot_emoji.name("coin")),
            value=(
                "{0.coins_free} Free | "
                "{0.coins_first_win} First Win | "
                "{0.coins_max} Max".format(e))
        )
        em.set_thumbnail(url=e.map_url)
        return em

    async def on_reaction_add(self, reaction, user):
        """Event: on_reaction_add."""
        await self.handle_reaction(reaction, user)

    async def on_reaction_remove(self, reaction, user):
        """Event: on_reaction_remove."""
        await self.handle_reaction(reaction, user)

    async def handle_reaction(self, reaction, user):
        """Handle reactions.

        + Check to see if reaction is added in active sessions.
        + Change embeds based on reaction name.
        """
        if user == self.bot.user:
            return
        if user.id not in self.sessions:
            return
        if self.sessions[user.id]["message_id"] != reaction.message.id:
            return

        # emoji names: number1, number2, etc.
        index = int(reaction.emoji.name[-1]) - 1

        session = self.sessions[user.id]
        channel = self.bot.get_channel(session["channel_id"])
        message = await self.bot.get_message(channel, session["message_id"])
        data = session["data"]
        event_model = BSEventModel(data=data[index])

        await self.bot.edit_message(message, embed=self.event_embed(event_model))


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
    n = BSData(bot)
    bot.add_cog(n)
