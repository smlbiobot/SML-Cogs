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
from collections import defaultdict
from collections import namedtuple
from itertools import zip_longest

import aiofiles
import aiohttp
import discord
import os
import re
import socket
import yaml
from discord.ext import commands
from random import choice

from cogs.utils import checks
from cogs.utils.chat_formatting import bold
from cogs.utils.chat_formatting import inline
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "brawlstars")
JSON = os.path.join(PATH, "settings.json")
BAND_CONFIG_YML = os.path.join(PATH, "club.config.yml")

MANAGE_ROLE_ROLES = ['Bot Commander']

from box import Box


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def clean_tag(tag):
    """Clean supercell tag"""
    t = tag
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    t = t.replace('#', '')
    return t


def remove_color_tags(s):
    """Clean string and remove color tags from string"""
    return re.sub("<[^>]*>", "", s)


class BSPlayer(Box):
    """Player model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BSClub(Box):
    """Player model"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class APIError(Exception):
    pass


class MissingServerConfig(Exception):
    pass


ClubResults = namedtuple("ClubResults", ["results", "club_tags"])


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


async def api_fetch(url=None, auth=None):
    """Fetch from BS API"""
    conn = aiohttp.TCPConnector(
        family=socket.AF_INET,
        verify_ssl=False,
    )
    async with aiohttp.ClientSession(connector=conn) as session:
        async with session.get(url, headers=dict(Authorization=auth)) as resp:
            if resp.status != 200:
                raise APIError()
            data = await resp.json()
    return data


async def api_fetch_player(tag=None, auth=None):
    """Fetch player"""
    url = 'https://brawlapi.cf/api/players/{}'.format(clean_tag(tag))
    data = await api_fetch(url=url, auth=auth)
    return BSPlayer(data)


async def api_fetch_club(tag=None, auth=None):
    """Fetch player"""
    url = 'https://brawlapi.cf/api/clubs/{}'.format(clean_tag(tag))
    data = await api_fetch(url=url, auth=auth)
    return BSClub(data)


class BrawlStars:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._club_config = None

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    def get_emoji(self, name):
        for emoji in self.bot.get_all_emojis():
            if emoji.name == str(name):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    def get_avatar(self, player):
        avatar_id = player.get('avatarId') or 28000000
        avatar = self.get_emoji(avatar_id)
        return avatar

    def _player_embed(self, player: BSPlayer):
        if player.avatarId:
            avatar = self.get_avatar(player)
            description = '{} #{}'.format(avatar, player.tag.upper())
        else:
            description = '#{}'.format(player.tag.upper())

        em = discord.Embed(
            title=player.name,
            description=description,
            color=random_discord_color()
        )

        # club
        em.add_field(name=player.club.name, value=player.club.role, inline=False)

        # fields
        em.add_field(name='Trophies', value="{} / {} PB".format(player.trophies, player.highestTrophies))
        em.add_field(name='Boss', value="{}".format(player.bestTimeAsBoss or ''))
        em.add_field(name='Robo Rumble', value="{}".format(player.bestRoboRumbleTime or ''))
        em.add_field(name='XP', value="{}".format(player.totalExp or ''))
        em.add_field(name='Victories', value="{}".format(player.victories or ''))
        em.add_field(name='Solo SD', value="{}".format(player.soloShowdownVictories or ''))
        em.add_field(name='Duo SD', value="{}".format(player.duoShowdownVictories or ''))

        # brawlers
        em.add_field(name="Brawlers Unlocked", value=player.brawlersUnlocked, inline=False)

        for b in player.brawlers or []:
            em.add_field(
                name="{} {}".format(self.get_emoji(b.name.lower().replace(' ', '')), b.name),
                value="{} / {} Lvl {}".format(b.trophies, b.highestTrophies, b.level)
            )

        # footer
        em.set_footer(
            text="Data by BrawlAPI https://brawlapi.cf"
        )
        return em

    def _player_mini_str(self, player: BSPlayer):
        """Minimal player profile for verification."""
        avatar = self.get_avatar(player)
        o = [
            '{}'.format(avatar),
            '{} #{}'.format(bold(player.name), player.tag),
            '{}, {} #{}'.format(player.club.role, player.club.name, player.club.tag) if player.club else 'No Clan',
            '{} {} / {}'.format(self.get_emoji('bstrophy'), player.trophies, player.highestTrophies),
        ]
        return "\n".join(o)

    def _player_str(self, player: BSPlayer):
        """Player profile as plain text."""
        avatar = self.get_avatar(player)

        o = [
            '{}'.format(avatar),
            '{} #{}'.format(bold(player.name), player.tag),
            '{}, {} #{}'.format(player.club.role, player.club.name, player.club.tag) if player.club else 'No Clan',
            '{} {} / {}'.format(self.get_emoji('bstrophy'), player.trophies, player.highestTrophies),
            '{emoji} {time} Best time as Boss'.format(
                emoji=self.get_emoji('bossfight'),
                time=inline(player.bestTimeAsBoss)),
            '{emoji} {time} Best Robo Rumble time'.format(
                emoji=self.get_emoji('roborumble'),
                time=inline(player.bestRoboRumbleTime)),
            # victories
            '{normal} {solo} {duo}'.format(
                normal='{emoji} {value} {name}'.format(
                    emoji=self.get_emoji('battlelog'),
                    value=inline(player.victories),
                    name='Victories'
                ),
                solo='{emoji} {value} {name}'.format(
                    emoji=self.get_emoji('showdown'),
                    value=inline(player.soloShowdownVictories),
                    name='Solo SD'
                ),
                duo='{emoji} {value} {name}'.format(
                    emoji=self.get_emoji('duoshowdown'),
                    value=inline(player.duoShowdownVictories),
                    name='Duo SD'
                ),
            )

        ]

        # brawlers
        for b in player.brawlers or []:
            o.append(
                '{emoji} `{trophies: >3} / {pb: >3} Lvl {level: >2}\u2800` {name}'.format(
                    emoji=self.get_emoji(b.name.lower().replace(' ', '')),
                    trophies=b.trophies,
                    pb=b.highestTrophies,
                    level=b.level,
                    name=b.name
                )
            )

        return '\n'.join(o)

    async def _get_club_config(self, force_update=False):
        if force_update or self._club_config is None:
            async with aiofiles.open(BAND_CONFIG_YML) as f:
                contents = await f.read()
                self._club_config = yaml.load(contents)
        return self._club_config

    async def send_error_message(self, ctx):
        await self.bot.say("BrawlAPI Error. Please try again later…")

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def bsset(self, ctx):
        """Set Brawl Stars API settings.

        Require https://brawlapi.cf/api
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @bsset.command(name="init", pass_context=True)
    async def _bsset_init(self, ctx):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings[server.id] = {}
        if self._save_settings:
            await self.bot.say("Server settings initialized.")

    @bsset.command(name="auth", pass_context=True)
    async def _bsset_auth(self, ctx, token):
        """Authorization (token)."""
        self.settings['brawlapi_token'] = token
        if self._save_settings():
            await self.bot.say("Authorization (token) updated.")
        await self.bot.delete_message(ctx.message)

    @bsset.command(name="config", pass_context=True)
    async def _bsset_config(self, ctx):
        """Band config"""
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
                with open(BAND_CONFIG_YML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(BAND_CONFIG_YML))

        self.settings['config'] = BAND_CONFIG_YML
        dataIO.save_json(JSON, self.settings)

        await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    async def bs(self, ctx):
        """Brawl Stars."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    # @bs.command(name="settag", alias=['st'], pass_context=True)
    # async def bs_settag(self, ctx, tag):
    #     """Assign tag to self."""
    #     tag = clean_tag(tag)
    #     server = ctx.message.server
    #     author = ctx.message.author
    #     self.settings[server.id][author.id] = tag
    #     if self._save_settings():
    #         await self.bot.say("Tag saved.")

    @bs.command(name="profile", aliases=['p'], pass_context=True)
    async def bs_profile(self, ctx, member: discord.Member = None):
        """Profile by Discord username."""
        server = ctx.message.server
        author = ctx.message.author
        if member is None:
            member = author

        tag = self.settings.get(server.id, {}).get(member.id)
        if tag is None:
            await self.bot.say("Can’t find tag associated with user.")
            return

        try:
            player = await api_fetch_player(tag=tag, auth=self.settings.get('brawlapi_token'))
        except APIError:
            await self.send_error_message(ctx)
        else:
            # await self.bot.say(embed=self._player_embed(player))
            await self.bot.say(self._player_str(player))

    @bs.command(name="profiletag", aliases=['pt'], pass_context=True)
    async def bs_profile_tag(self, ctx, tag=None):
        """Profile by player tag."""
        tag = clean_tag(tag)
        try:
            player = await api_fetch_player(tag=tag, auth=self.settings.get('brawlapi_token'))
        except APIError:
            await self.send_error_message(ctx)
        else:
            await self.bot.say(self._player_str(player))

    @bs.command(name="verify", aliases=['v'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def bs_verify(self, ctx, member: discord.Member, tag=None):
        cfg = Box(await self._get_club_config())
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
            player = await api_fetch_player(tag=tag, auth=self.settings.get('brawlapi_token'))
        except APIError:
            await self.send_error_message(ctx)
            return

        await self.bot.say(self._player_mini_str(player))

        club_tags = [b.tag for b in server.clubs]

        to_add_roles = []
        to_remove_roles = []

        to_add_roles += server.everyone_roles

        # if member in clubs, add member roles and remove visitor roles
        if player.club and player.club.tag in club_tags:
            to_remove_roles += server.visitor_roles
            to_add_roles += server.member_roles

            for b in server.clubs:
                if b.tag == player.club.tag:
                    to_add_roles += b.roles

        # add visitor roles if member not in club
        else:
            to_remove_roles += server.member_roles
            to_add_roles += server.visitor_roles

        # change nickname to match IGN
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
            await self.bot.add_roles(member, *roles)
            await self.bot.say(
                "Added {roles} to {member}".format(roles=", ".join(to_add_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

        # remove roles
        try:
            roles = [r for r in ctx_server.roles if r.name in to_remove_roles]
            await self.bot.remove_roles(member, *roles)
            await self.bot.say(
                "Removed {roles} from {member}".format(roles=", ".join(to_remove_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

    async def _get_clubs(self, server_id, query=None):
        """Return clubs."""
        cfg = Box(await self._get_club_config())
        server = None
        for s in cfg.servers:
            if str(s.id) == str(server_id):
                server = s
                break

        if server is None:
            await self.bot.say("No config for this server found.")
            return

        if query is None:
            club_tags = [b.tag for b in server.clubs]
        else:
            club_tags = []
            for b in server.clubs:
                if query.lower() in b.name.lower():
                    club_tags.append(b.tag)

        tasks = [
            api_fetch_club(tag=tag, auth=self.settings.get('brawlapi_token'))
            for tag in club_tags
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return ClubResults(results=results, club_tags=club_tags)

    @bs.command(name="search", aliases=['s'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def bs_search(self, ctx, query: str):
        """Search for member name in configured clubs."""
        r = await self._get_clubs(ctx.message.server.id)
        results = r.results
        club_tags = r.club_tags

        found = []

        for tag, result in zip(club_tags, results):
            if isinstance(result, APIError):
                await self.bot.say("Error fetching club info for {}".format(tag))
                await self.send_error_message(ctx)
                continue

            for member in result.get('members', []):
                if query.lower() in member.get('name', '').lower():
                    member.update(dict(
                        clan_name=result.get('name', ''),
                        clan_tag=result.get('tag', '')
                    ))
                    found.append(member)

        if not found:
            await self.bot.say("Cannot find anyone named `{}` in our clubs".format(query))
            return

        o = [
            "{name} #{tag}, {role}, {clan}, {trophies}".format(
                name=m.get('name', ''),
                tag=m.get('tag', ''),
                role=m.get('role', '').title(),
                trophies=m.get('trophies', 0),
                clan=m.get('clan_name')
            ) for m in found
        ]

        await self.bot.say("\n".join(o))

    async def _club_info(self, ctx, club: BSClub, color=None):
        """Show club info as embed."""
        if color is None:
            color = random_discord_color()

        em = discord.Embed(title=club.name, description=remove_color_tags(club.description), color=color)

        em.set_thumbnail(url=club.badgeUrl)
        em.add_field(name="Tag", value="#{0.tag}".format(club))
        em.add_field(name="Trophies", value="{0.trophies} Req: {0.requiredTrophies}".format(club))
        em.add_field(name="Members", value="{0.membersCount} / 100 : {0.onlineMembers} online".format(club))

        await self.bot.say(embed=em)

    @bs.command(name="clubtag", aliases=["ct"], pass_context=True)
    async def bs_club_tag(self, ctx, tag):
        """Club by tag"""
        tag = clean_tag(tag)
        try:
            r = await api_fetch_club(tag=tag, auth=self.settings.get('brawlapi_token'))
            club = BSClub(r)
            await self._club_info(ctx, club)
        except APIError:
            await self.send_error_message(ctx)

    @bs.command(name="clubs", aliases=["c"], pass_context=True)
    async def bs_clubs(self, ctx):
        """List clubs."""
        r = await self._get_clubs(ctx.message.server.id)
        results = r.results
        club_tags = r.club_tags

        color = random_discord_color()

        for r, club_tag in zip(results, club_tags):
            if isinstance(r, Exception):
                await self.bot.say("Error fetching club info for {}".format(club_tag))
                continue

            club = BSClub(r)
            await self._club_info(ctx, club, color=color)

    async def _club_members(self, ctx, club: BSClub, color=None):
        if color is None:
            color = random_discord_color()

        em = discord.Embed(title=club.name, description='#{}'.format(club.tag), color=color)

        server = ctx.message.server
        server_members = self.settings.get(server.id, {})
        tag2id = {v: k for k, v in server_members.items()}
        o = []
        for m in club.members:
            user_id = tag2id.get(m.tag)
            user = None
            if user_id is not None:
                user = server.get_member(user_id)
            o.append(
                "**{name}** #{tag}, {role}, {trophies} {mention} {d_name}".format(
                    name=remove_color_tags(m.name),
                    tag=m.tag,
                    role=m.role,
                    trophies=m.trophies,
                    mention=user.mention if user else "",
                    d_name=user.name if user else ""
                )
            )

        count = 10
        pagified = grouper(o, count)
        for index, page in enumerate(pagified):
            v = [line for line in page if line is not None]
            em.add_field(name="Members {}-{}".format(index + 1, index * 10 + len(v)), value='\n'.join(v))

        await self.bot.say(embed=em)

    @bs.command(name="members", aliases=['m'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def bs_members(self, ctx, query: str = None):
        """List all members in clubs."""
        clubs = await self._get_clubs(ctx.message.server.id, query=query)

        color = random_discord_color()

        for r, club_tag in zip(clubs.results, clubs.club_tags):
            if isinstance(r, Exception):
                await self.bot.say("Error fetching club info for {}".format(club_tag))
                continue

            club = BSClub(r)
            await self._club_members(ctx, club, color=color)


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
    n = BrawlStars(bot)
    bot.add_cog(n)
