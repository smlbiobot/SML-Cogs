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
import json
import os
import socket
from collections import defaultdict

import aiofiles
import aiohttp
import discord
import yaml
from box import Box
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import MemberConverter
from discord.ext.commands.errors import BadArgument

PATH = os.path.join("data", "rushwars")
JSON = os.path.join(PATH, "settings.json")
TEAM_CONFIG_YML = os.path.join(PATH, "team.config.yml")
CACHE_PATH = os.path.join(PATH, "cache")
CACHE_PLAYER_PATH = os.path.join(CACHE_PATH, "player")
CACHE_TEAM_PATH = os.path.join(CACHE_PATH, "team")

MANAGE_ROLE_ROLES = ['Bot Commander']


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def clean_tag(tag):
    """Clean supercell tag"""
    t = tag
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    t = t.replace('#', '')
    return t


class RushWarsAPIError(Exception):
    pass


class APIRequestError(RushWarsAPIError):
    pass


class APITimeoutError(RushWarsAPIError):
    pass


class APIServerError(RushWarsAPIError):
    pass


class RWPlayer(Box):
    """Player model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RWTeam(Box):
    """Team model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RushWarsAPI:
    """Rush Wars API"""

    def __init__(self, auth):
        self._auth = auth

    async def fetch(self, url=None, auth=None):
        """Fetch from API"""
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        if auth is None:
            auth = self._auth

        print("auth", auth)
        try:
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(url, headers=dict(Authorization=auth), timeout=10) as resp:
                    print(resp.status)
                    if str(resp.status).startswith('4'):
                        raise APIRequestError()

                    if str(resp.status).startswith('5'):
                        raise APIServerError()

                    data = await resp.json()
        except asyncio.TimeoutError:
            raise APITimeoutError()

        return data

    async def fetch_player(self, tag=None, auth=None, **kwargs):
        """Fetch player"""
        url = 'https://api.rushstats.com/v1/player/{}'.format(clean_tag(tag))
        fn = os.path.join(CACHE_PLAYER_PATH, "{}.json".format(tag))
        try:
            data = await self.fetch(url=url, auth=auth)
        except APIServerError:
            if os.path.exists(fn):
                async with aiofiles.open(fn, mode='r') as f:
                    data = json.load(await f.read())
            else:
                raise
        else:
            async with aiofiles.open(fn, mode='w') as f:
                json.dump(data, f)

        return RWPlayer(data)

    async def fetch_team(self, tag=None, auth=None, **kwargs):
        """Fetch player"""
        url = 'https://api.rushstats.com/v1/team/{}'.format(clean_tag(tag))
        fn = os.path.join(CACHE_TEAM_PATH, "{}.json".format(tag))
        try:
            data = await self.fetch(url=url, auth=auth)
        except APIServerError:
            if os.path.exists(fn):
                async with aiofiles.open(fn, mode='r') as f:
                    data = json.load(await f.read())
            else:
                raise
        else:
            async with aiofiles.open(fn, mode='w') as f:
                json.dump(data, f)

        return RWTeam(data)


class RushWars:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._team_config = None
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = RushWarsAPI(self.settings['api_token'])
        return self._api

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    async def _get_team_config(self, force_update=False):
        if force_update or self._club_config is None:
            async with aiofiles.open(TEAM_CONFIG_YML) as f:
                contents = await f.read()
                self._club_config = yaml.load(contents, Loader=yaml.FullLoader)
        return self._club_config

    async def _get_server_config(self, server_id=None):
        cfg = await self._get_team_config()
        for server in cfg.get('servers', []):
            if str(server.get('id')) == str(server_id):
                return server
        return None

    async def send_error_message(self, ctx):
        channel = ctx.message.channel
        await self.bot.send_message(channel, "RushWarsAPI Error. Please try again later…")

    def get_emoji(self, name):
        for emoji in self.bot.get_all_emojis():
            if emoji.name == str(name):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def rwset(self, ctx):
        """Set Rush Wars API settings.

        Require https://rushstats.com/api
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @rwset.command(name="init", pass_context=True)
    async def _rwset_init(self, ctx):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings[server.id] = {}
        if self._save_settings:
            await self.bot.say("Server settings initialized.")

    @rwset.command(name="auth", pass_context=True)
    async def _rwset_auth(self, ctx, token):
        """Authorization (token)."""
        self.settings['api_token'] = token
        self._api = RushWarsAPI(token)
        if self._save_settings():
            await self.bot.say("Authorization (token) updated.")
        await self.bot.delete_message(ctx.message)

    @rwset.command(name="config", pass_context=True)
    async def _rwset_config(self, ctx):
        """Team config"""
        if len(ctx.message.attachments) == 0:
            await self.bot.say(
                "Please attach config yaml with this command. "
                "See config.example.yml for how to format it."
            )
            return

        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(TEAM_CONFIG_YML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(TEAM_CONFIG_YML))

        self.settings['config'] = TEAM_CONFIG_YML
        dataIO.save_json(JSON, self.settings)

        await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    async def rw(self, ctx):
        """Rush Wars."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @rw.command(name="player", aliases=['p', 'profile'], pass_context=True)
    async def rw_player(self, ctx, player):
        """Player profile.

        player can be a player tag or a Discord member.
        """
        server = ctx.message.server
        member = None
        tag = None
        try:
            cvt = MemberConverter(ctx, player)
            member = cvt.convert()
        except BadArgument:
            # cannot convert to member. Assume argument is a tag
            tag = clean_tag(player)
        else:
            tag = self.settings.get(server.id, {}).get(member.id)
            if tag is None:
                await self.bot.say("Can’t find tag associated with user.")
                return

        try:
            p = await self.api.fetch_player(tag)
        except RushWarsAPIError as e:
            await self.bot.say("RushWarsAPIError")
        else:
            await self.bot.say(
                "{name} {tag} Stars:{stars}".format(
                    name=p.name,
                    tag=p.tag,
                    stars=p.stars
                )
            )



    @rw.command(name="verify", aliases=['v'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def rw_verify(self, ctx, member: discord.Member, tag=None):
        tag = clean_tag(tag)
        ctx_server = ctx.message.server

        self.settings[ctx_server.id][member.id] = tag
        self._save_settings()
        await self.bot.say("Associated {tag} with {member}".format(tag=tag, member=member))

        to_add_roles = ['Rush-Wars', 'RW-Member']

        # add roles
        try:
            roles = [r for r in ctx_server.roles if r.name in to_add_roles]
            if roles:
                await self.bot.add_roles(member, *roles)
                await self.bot.say(
                    "Added {roles} to {member}".format(roles=", ".join(to_add_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

        # welcome user
        channel = discord.utils.get(ctx.message.server.channels, name="family-chat")

        if channel is not None:
            await self.bot.say(
                "{} Welcome! You may now chat at {} — enjoy!".format(
                    member.mention, channel.mention))


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)
    os.makedirs(CACHE_PATH, exist_ok=True)
    os.makedirs(CACHE_PLAYER_PATH, exist_ok=True)
    os.makedirs(CACHE_TEAM_PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = RushWars(bot)
    bot.add_cog(n)
