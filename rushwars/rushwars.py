"""
The MIT License (MIT)

Copyright (c) 2019 SML <sml@royaleapi.com>

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
import re
import socket
from collections import defaultdict
from collections import namedtuple
from random import choice
from itertools import zip_longest
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

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def remove_color_tags(s):
    """Clean string and remove color tags from string"""
    return re.sub("<[^>]*>", "", s)


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


class RushWarsAPIError(Exception):
    pass


class APIRequestError(RushWarsAPIError):
    pass


class APITimeoutError(RushWarsAPIError):
    pass


class APIServerError(RushWarsAPIError):
    pass


TeamResults = namedtuple("TeamResults", ["results", "team_tags"])


class RWModel:
    def __init__(self, *args, **kwargs):
        self._box = Box(*args, default_box=True, **kwargs)

    def __getattr__(self, item):
        return self._box.get(item)


class RWPlayer(RWModel):
    """Player model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RWTeam(RWModel):
    """Team model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RWEmbed:
    """Rush Wars Embeds"""

    @staticmethod
    def player(p: RWPlayer, color=None):
        if color is None:
            color = random_discord_color()
        em = discord.Embed(
            title=p.name,
            description="#{0.tag}".format(p),
            color=color
        )
        em.add_field(
            name="Team",
            value="[{0.team.name} #{0.team.tag}](https://link.rushwarsgame.com/?clanInfo?id={0.team.tag})".format(p)
        )
        return em

    @staticmethod
    def team(team: RWTeam, color=None):
        if color is None:
            color = random_discord_color()
        em = discord.Embed(
            title=team.name,
            description=remove_color_tags(team.description),
            color=color,
            url="https://link.rushwarsgame.com/?clanInfo?id={0.tag}".format(team)
        )
        em.set_thumbnail(url=team.badgeUrl)
        em.add_field(name="Tag", value="#{0.tag}".format(team))
        em.add_field(name="Trophies", value="{0.score} Req: {0.requiredScore}".format(team))
        em.add_field(name="Members", value="{0.membersCount} / 25 ".format(team))
        return em

    @staticmethod
    def team_members(
            team:RWTeam,
            color=None,
            server:discord.Server=None,
            server_members:dict=None
    ):
        if color is None:
            color = random_discord_color()

        em = discord.Embed(
            title=team.name,
            description='#{}'.format(team.tag),
            color=color
        )

        tag2id = {v: k for k, v in server_members.items()}
        o = []
        for m in team.members:
            user_id = tag2id.get(m.tag)
            user = None
            if user_id is not None:
                user = server.get_member(user_id)
            o.append(
                "{name} #{tag}, {role}, {trophies} {d_name}".format(
                    name=remove_color_tags(m.name),
                    tag=m.tag,
                    role=m.role,
                    trophies=m.stars,
                    d_name=user if user else "----"
                )
            )

        count = 10
        pagified = grouper(o, count)
        for index, page in enumerate(pagified):
            v = [line for line in page if line is not None]
            em.add_field(name="Members {}-{}".format(index * 10 + 1, index * 10 + len(v)), value='\n'.join(v))


        return em

class RushWarsAPI:
    """Rush Wars API"""

    def __init__(self, auth, session=None):
        self._auth = auth
        self._session = session

    async def shutdown(self):
        if self._session:
            await self._session.close()

    async def _get_session(self):
        if self._session is None:
            conn = aiohttp.TCPConnector(
                family=socket.AF_INET,
                verify_ssl=False,
            )
            self._session = aiohttp.ClientSession(connector=conn)
        return self._session

    async def fetch(self, url=None, auth=None):
        """Fetch from API"""

        if auth is None:
            auth = self._auth

        session = await self._get_session()
        headers = dict(Authorization=auth)
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
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
        self.loop = asyncio.get_event_loop()

    def __unload(self):
        if self._api:
            self.loop.create_task(
                self._api.shutdown()
            )

    @property
    def api(self):
        if self._api is None:
            self._api = RushWarsAPI(self.settings['api_token'])
        return self._api

    def tag_to_id(self, server_id):
        """RW player tag to discord user id."""
        server_members = self.settings.get(server_id, {})
        return {v: k for k, v in server_members.items()}

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    async def _get_team_config(self, force_update=False):
        if force_update or self._team_config is None:
            async with aiofiles.open(TEAM_CONFIG_YML) as f:
                contents = await f.read()
                self._team_config = yaml.load(contents, Loader=yaml.FullLoader)
        return self._team_config

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
    async def rw_player(self, ctx, player=None):
        """Player profile.

        player can be a player tag or a Discord member.
        """
        server = ctx.message.server
        author = ctx.message.author
        member = None
        tag = None

        if player is None:
            tag = self.settings.get(server.id, {}).get(author.id)
        else:
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
            await self.bot.say(embed=RWEmbed.player(p))

    @rw.command(name="verify", aliases=['v'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def rw_verify(self, ctx, member: discord.Member, tag=None):
        """Verify members"""
        cfg = Box(await self._get_team_config())
        server = None
        ctx_server = ctx.message.server
        for s in cfg.servers:
            if str(s.id) == str(ctx.message.server.id):
                server = s
                break

        if server is None:
            await self.bot.say("No config for this server found.")
            return

        tag = clean_tag(tag)
        self.settings[ctx_server.id][member.id] = tag
        self._save_settings()
        await self.bot.say("Associated {tag} with {member}".format(tag=tag, member=member))

        try:
            player = await self.api.fetch_player(tag=tag)
        except RushWarsAPIError:
            await self.send_error_message(ctx)
            return

        await self.bot.say(embed=RWEmbed.player(player))

        team_tags = [t.tag for t in server.teams]

        to_add_roles = []
        to_remove_roles = []

        to_add_roles += server.everyone_roles

        # if member in clubs, add member roles
        if player.team and player.team.tag in team_tags:
            to_add_roles += server.member_roles

            for t in server.teams:
                if t.tag == player.team.tag:
                    to_add_roles += t.roles
        else:
            to_remove_roles += server.member_roles

        # change nick to match IGN
        player_name = remove_color_tags(player.name)
        try:
            await self.bot.change_nickname(member, player_name)
            await self.bot.say(
                "Change {member} to {nick} to match IGN".format(member=member.mention, nick=player_name))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to change nick for this user.")

        # add roles
        try:
            roles = [r for r in ctx_server.roles if r.name in to_add_roles]
            if roles:
                await self.bot.add_roles(member, *roles)
                await self.bot.say(
                    "Added {roles} to {member}".format(roles=", ".join(to_add_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

        # remove roles
        try:
            roles = [r for r in ctx_server.roles if r.name in to_remove_roles]
            if roles:
                await self.bot.remove_roles(member, *roles)
                await self.bot.say(
                    "Removed {roles} from {member}".format(roles=", ".join(to_remove_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

        # welcome user
        channel = discord.utils.get(ctx.message.server.channels, name="family-chat")

        if channel is not None:
            await self.bot.say(
                "{} Welcome! You may now chat at {} — enjoy!".format(
                    member.mention, channel.mention))

    async def _get_teams(self, server_id, query=None):
        """Return clubs."""
        cfg = Box(await self._get_team_config())
        server = None
        for s in cfg.servers:
            if str(s.id) == str(server_id):
                server = s
                break

        if server is None:
            await self.bot.say("No config for this server found.")
            return

        if query is None:
            team_tags = [t.tag for t in server.teams]
        else:
            team_tags = []
            for t in server.teams:
                if query.lower() in t.name.lower():
                    team_tags.append(t.tag)

        tasks = [
            self.api.fetch_team(tag=tag)
            for tag in team_tags
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return TeamResults(results=results, team_tags=team_tags)

    @rw.command(name="search", aliases=['s'], pass_context=True)
    async def bs_search(self, ctx, query: str):
        """Search for member name in configured clubs."""
        r = await self._get_teams(ctx.message.server.id)

        results = r.results
        team_tags = r.team_tags

        found = []

        for tag, team in zip(team_tags, results):
            if isinstance(team, RushWarsAPIError):
                await self.bot.say("Error fetching team info for {}".format(tag))
                await self.send_error_message(ctx)
                continue

            members = team.members

            for member in members:
                if query.lower() in member.get('name', '').lower():
                    member.update(dict(
                        clan_name=team.name,
                        clan_tag=team.tag
                    ))
                    found.append(member)

        if not found:
            await self.bot.say("Cannot find anyone named `{}` in our teams".format(query))
            return

        o = [
            "{name} #{tag}, {role}, {clan}, {stars}".format(
                name=m.get('name', ''),
                tag=m.get('tag', ''),
                role=m.get('role', '').title(),
                stars=m.get('stars', 0),
                clan=m.get('clan_name')
            ) for m in found
        ]

        await self.bot.say("\n".join(o))

    """
    Teams
    """

    @rw.command(name="teams", aliases=["t"], pass_context=True)
    async def rw_teams(self, ctx, query=None):
        """List clubs."""
        r = await self._get_teams(ctx.message.server.id, query=query)
        results = r.results
        team_tags = r.team_tags

        color = random_discord_color()

        for team, team_tag in zip(results, team_tags):
            if isinstance(r, Exception):
                await self.bot.say("Error fetching club info for {}".format(team_tag))
                continue
            await self.bot.say(
                embed=RWEmbed.team(team, color=color)
            )

    @rw.command(name="members", aliases=['m'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def bs_members(self, ctx, query: str = None):
        """List all members in clubs."""
        teams = await self._get_teams(ctx.message.server.id, query=query)

        color = random_discord_color()
        server = ctx.message.server

        for team, team_tag in zip(teams.results, teams.team_tags):
            if isinstance(team, Exception):
                await self.bot.say("Error fetching club info for {}".format(team_tag))
                continue

            await self.bot.say(
                embed=RWEmbed.team_members(
                    team,
                    color=color,
                    server=server,
                    server_members=self.settings.get(server.id, {})
                )
            )

    """
    Rush Wars Audit
    """

    @rw.command(name="audit", aliases=['a'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def rw_audit(self, ctx):
        """Run audit against the entire server."""
        server = ctx.message.server
        channel = ctx.message.channel
        audit = BrawlStarsAudit(cog=self)
        try:
            await audit.run(server, status_channel=channel)
        except RushWarsAuditException:
            await self.bot.say("Audit failed because of API error.")

    @rw.command(name="auditexec", aliases=['ax'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def rw_audit_exec(self, ctx):
        """Run audit against the entire server."""
        server = ctx.message.server
        channel = ctx.message.channel
        audit = BrawlStarsAudit(cog=self)
        try:
            await audit.run(server, status_channel=channel, exec=True)
        except RushWarsAuditException:
            await self.bot.say("Audit failed because of API error.")

class RushWarsAuditException(Exception):
    pass


class BrawlStarsAudit:
    """Audit Brawl Stars member roles on server."""

    def __init__(self, cog: RushWars = None):
        """Init."""
        self.cog = cog

    async def exec_add_roles(self, d_member, roles, channel=None):
        try:
            await self.cog.bot.add_roles(d_member, *roles)
        except Exception as e:
            pass
        else:
            if channel is not None:
                await self.cog.bot.send_message(
                    channel,
                    "Add {} to {}".format(
                        ", ".join(
                            [r.name for r in roles]
                        ),
                        d_member
                    )
                )

    async def exec_remove_roles(self, d_member, roles, channel=None):
        try:
            await self.cog.bot.remove_roles(d_member, *roles)
        except Exception as e:
            pass
        else:
            if channel is not None:
                await self.cog.bot.send_message(
                    channel,
                    "Remove {} from {}".format(
                        ", ".join(
                            [r.name for r in roles]
                        ),
                        d_member
                    )
                )

    async def run(self, server: discord.Server = None, exec=False, status_channel=None):
        """Run audit against server."""
        results = dict()
        # Fetch club info
        teams = await self.cog._get_teams(server.id)
        for r, team_tag, in zip(teams.results, teams.team_tags):
            if isinstance(r, Exception):
                raise RushWarsAuditException()

            results[team_tag] = r

        tag2id = self.cog.tag_to_id(server_id=server.id)

        member_ids = []

        # for each member, find discord user id
        for team_tag, team in results.items():
            for member in team.members:
                member_tag = member.get('tag')
                if member_tag is not None:
                    user_id = tag2id.get(member_tag)
                    member_ids.append(user_id)
                    member["discord_user_id"] = user_id

        # non members
        non_member_ids = [m.id for m in server.members if m.id not in member_ids]

        cfg = await self.cog._get_server_config(server_id=server.id)

        team_tag_to_team_roles = {}
        team_role_names = []
        for team in cfg.get('teams', []):
            team_tag_to_team_roles[team.get('tag')] = [
                discord.utils.get(server.roles, name=name) for name in
                team.get('roles', [])
            ]
            team_role_names += team.get('roles')

        all_team_roles = [
            discord.utils.get(server.roles, name=name) for name in team_role_names
        ]

        rw_member_role = discord.utils.get(server.roles, name="RW-Member")
        rw_members_roles = [rw_member_role] + all_team_roles

        if status_channel:
            for member_id in non_member_ids:
                user = server.get_member(member_id)
                if user is not None:
                    if rw_member_role in user.roles:
                        await self.cog.bot.send_message(status_channel, "{} is not in our teams".format(user))
                        if exec:
                            await self.exec_remove_roles(user, rw_members_roles, channel=status_channel)

            for member_id in member_ids:
                user = server.get_member(member_id)
                if user is not None:
                    if rw_member_role not in user.roles:
                        await self.cog.bot.send_message(status_channel, "{} is in our teams".format(user))
                        if exec:
                            await self.exec_add_roles(user, [rw_member_role], channel=status_channel)

        # teams
        for team_tag, team in results.items():
            team_member_ids = []
            for member in team.members:
                user_id = member.get('discord_user_id')
                if user_id is not None:
                    team_member_ids.append(user_id)

            non_team_member_ids = [m.id for m in server.members if m.id not in team_member_ids]

            team_roles = team_tag_to_team_roles[team_tag]
            team_role = team_roles[0]

            # members
            for user_id in team_member_ids:
                user = server.get_member(user_id)
                if user is not None:
                    if team_role not in user.roles:
                        await self.cog.bot.send_message(
                            status_channel,
                            "{} is in {}".format(user, team.name))
                        if exec:
                            await self.exec_add_roles(user, [team_role], channel=status_channel)

            for user_id in non_team_member_ids:
                user = server.get_member(user_id)
                if user is not None:
                    if team_role in user.roles:
                        await self.cog.bot.send_message(
                            status_channel,
                            "{} is not in {}".format(user, team.name))
                        if exec:
                            await self.exec_remove_roles(user, [team_role], channel=status_channel)

        # print_json(results)
        await self.cog.bot.send_message(status_channel, "Audit finished")


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
