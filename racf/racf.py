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
import itertools
from itertools import zip_longest

import aiohttp
import asyncio
import discord
import json
import logging
import os
import socket
import yaml
from box import Box
from discord.ext import commands
from discord.ext.commands import Context
from random import choice

import cogs
from cogs.utils import checks
from cogs.utils import dataIO
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

logger = logging.getLogger(__name__)

CHANGECLAN_ROLES = ["Leader", "Co-Leader", "Elder", "High Elder", "Member"]
BS_CHANGECLAN_ROLES = ["Member", "Brawl-Stars"]
DISALLOWED_ROLES = ["SUPERMOD", "MOD", "AlphaBot"]
MEMBER_DEFAULT_ROLES = ["Member", "Tourney" "Content"]
CLANS = [
    "Alpha", "Bravo", "Charlie", "Delta",
    "Echo", "Foxtrot", "Golf", "Hotel"]
BS_CLANS = [
    "BS-Alpha", "BS-Bravo", "BS-Charlie"]
BS_CLANS_PREFIX = 'BS-'
BOTCOMMANDER_ROLE = ["Bot Commander"]
HE_BOTCOMMANDER_ROLES = ["Bot Commander", "High-Elder"]
COMPETITIVE_CAPTAIN_ROLES = ["Competitive-Captain", "Bot Commander"]
COMPETITIVE_TEAM_ROLES = [
    "CRL", "RPL-NA", "RPL-EU", "RPL-APAC", "MLG",
    "ClashWars", "CRL-Elite", "CRL-Legends", "CRL-Rockets"]
CLAN_PERMISSION = {
    '9PJ82CRC': {
        'tag': '9PJ82CRC',
        'role': 'Alpha',
        'assign_role': True,
        'member': True
    },
    '9UQJUJC9': {
        'tag': '9UQJUJC9',
        'role': 'Bravo',
        'assign_role': True,
        'member': True
    },
    '9G99JQPL': {
        'tag': '9G99JQPL',
        'role': 'Charlie',
        'assign_role': True,
        'member': True
    },
    '9G8VYGL0': {
        'tag': '9G8VYGL0',
        'role': 'Delta',
        'assign_role': True,
        'member': True
    },
    '9CJ0L9RG': {
        'tag': '9CJ0L9RG',
        'role': 'Echo',
        'assign_role': True,
        'member': True
    },
    '9UQC2P0V': {
        'tag': '9UQC2P0V',
        'role': 'Foxtrot',
        'assign_role': True,
        'member': True
    },
    '9UG2R2LQ': {
        'tag': '9UG2R2LQ',
        'role': 'Golf',
        'assign_role': True,
        'member': True
    },
    '9Y9VR2JR': {
        'tag': '9Y9VR2JR',
        'role': 'Hotel',
        'assign_role': True,
        'member': True
    },
    '9R8GUC0L': {
        'tag': '9R8GUC0L',
        'role': 'YOLO',
        'assign_role': True,
        'member': True
    },
    '9LPVG9UC': {
        'tag': '9LPVG9UC',
        'role': 'Zen',
        'assign_role': True,
        'member': True
    },
    '22LR8JJ2': {
        'tag': '22LR8JJ2',
        'role': 'Mini',
        'assign_role': True,
        'member': False
    },
    '2Q09VJC8': {
        'tag': '2Q09VJC8',
        'role': 'Mini2',
        'assign_role': True,
        'member': False
    },
}

BAND_PERMISSION = {
    'LQQ': {
        'tag': 'LQQ',
        'role': 'BS-Alpha',
        'assign_role': True,
        'member': False
    },
    '82RQLR': {
        'tag': '82RQLR',
        'role': 'BS-Bravo',
        'assign_role': True,
        'member': False
    },
    '98VLYJ': {
        'tag': '98VLYJ',
        'role': 'BS-Charlie',
        'assign_role': True,
        'member': False
    },
    'Q0YG8V': {
        'tag': 'Q0YG8V',
        'role': 'BS-Delta',
        'assign_role': True,
        'member': False
    }

}

PATH = os.path.join("data", "racf")
JSON = os.path.join(PATH, "settings.json")


CLAN_ROLES = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'YOLO', 'Zen']
MEMBER_ROLES = ['Content', 'Tourney', 'Member']
VISITOR_ROLES = ['Visitor']
RECRUIT_ROLES = ['{}Recruit'.format(r) for r in CLAN_ROLES]
RECRUIT_ROLES.append('Recruit')


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if isinstance(t, list):
        t = t[0]
    if isinstance(t, tuple):
        t = t[0]
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    return t


class TagNotFound(Exception):
    pass


class UnknownServerError(Exception):
    pass


def get_emoji(bot, name):
    for emoji in bot.get_all_emojis():
        if emoji.name == name:
            return '<:{}:{}>'.format(emoji.name, emoji.id)
    return name


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


async def check_manage_roles(ctx, bot):
    """Check for permissions to run command since no one has manage roles anymore."""
    server = ctx.message.server
    author = ctx.message.author
    channel = ctx.message.channel
    # For 100T server, only allow command to run if user has the "Bot Comamnder" role
    if server.id == '218534373169954816':
        bc_role = discord.utils.get(server.roles, name="Bot Commander")
        if bc_role not in author.roles:
            await bot.send_message(
                channel,
                "Only Bot Commanders on this server can run this command.")
            return False
        else:
            return True

    # For other servers, only allow to run if user has manage role permissions
    if not author.server_permissions.manage_roles:
        await bot.send_message(
            channel,
            "You don’t have the manage roles permission.")
        return False

    return True


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


class RACF:
    """Display RACF specifc info.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        with open(os.path.join("data", "racf", "config.yaml")) as f:
            self.config = Box(yaml.load(f))
        self.settings = dataIO.load_json(JSON)

    @property
    def auth(self):
        return self.settings.get("auth")

    @auth.setter
    def auth(self, value):
        self.settings["auth"] = value
        dataIO.save_json(JSON, self.settings)

    async def add_roles(self, server: discord.Server, member: discord.Member, role_names):
        """Add roles by name"""
        roles = [discord.utils.get(server.roles, name=role_name) for role_name in role_names]
        roles = [r for r in roles if r]
        await self.bot.add_roles(member, *roles)

    async def remove_roles(self, server: discord.Server, member: discord.Member, role_names):
        """Remove roles by name.

        Return list of roles removed.
        """
        roles = [discord.utils.get(member.roles, name=role_name) for role_name in role_names]
        roles = [r for r in roles if r]
        if len(roles):
            print([r.name for r in roles])
            await self.bot.remove_roles(member, *roles)
        return [r.name for r in roles]

    @commands.group(pass_context=True, no_pm=True)
    async def racfset(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.is_owner()
    @racfset.command(name="auth", pass_context=True, no_pm=True)
    async def racfset_auth(self, ctx, token):
        """Save auth"""
        self.auth = token
        await self.bot.say("Token saved.")
        await self.bot.delete_message(ctx.message)

    @commands.group(aliases=['r'], pass_context=True, no_pm=True)
    async def racf(self, ctx):
        """RACF commands."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @racf.command(name="info", pass_context=True, no_pm=True)
    async def racf_info(self, ctx: Context):
        """RACF Rules + Roles."""
        server = ctx.message.server

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        em = discord.Embed(
            color=discord.Color(value=color),
            title="Rules + Roles",
            description="Important information for all members. Please read.")

        if server.icon_url:
            em.set_author(name=server.name, url=server.icon_url)
            em.set_thumbnail(url=server.icon_url)
        else:
            em.set_author(name=server.name)

        em.add_field(name='Documentation', value=self.config.url.docs)

        try:
            await self.bot.say(embed=em)
        except discord.HTTPException:
            await self.bot.say(
                "I need the `Embed links` permission to send this.")

    def player_info(self, player_data):
        """Short player info without full profile."""
        data = player_data
        clan = player_data.get("clan", None)
        if clan is None:
            data["clan"] = {
                "name": "No Clan",
                "tag": "N/A",
                "role": "N/A"
            }
        return (
            "Player Tag: {tag}\n"
            "IGN: {name}\n"
            "Clan Name: {clan_name}\n"
            "Clan Tag: {clan_tag}\n"
            "Clan Role: {clan_role}\n"
            "Trophies: {trophies:,} / {pb:,} PB\n"
            "CW: {cards:,} cards / {war_wins:,} war wins".format(
                tag=data.get('tag'),
                name=data.get('name'),
                clan_name=data['clan']['name'],
                clan_tag=data['clan']['tag'],
                clan_role=data.get('role'),
                trophies=data.get('trophies', 0),
                pb=data.get('bestTrophies', 0),
                cards=data.get('clanCardsCollected', 0),
                war_wins=data.get('warDayWins', 0),
            )
        )

    async def fetch_player_profile(self, tag):
        """Fetch player profile data."""
        url = "{}%23{}".format('https://api.clashroyale.com/v1/players/', tag)
        headers = {'Authorization': 'Bearer {}'.format(self.auth)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise
        except asyncio.TimeoutError:
            raise

        return data

    @racf.command(name="verify", aliases=['v'], pass_context=True, no_pm=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racf_verify(self, ctx, member: discord.Member, tag):
        """Verify CR members by player tag."""

        # verify for RoyaleAPI server
        if ctx.message.server.name == 'RoyaleAPI':
            await self.royaleapi_verify(ctx, member, tag)
            return

        # verify permissions on 100T server
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        sctag = SCTag(tag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        tag = sctag.tag

        # - Set their tags
        await ctx.invoke(self.crsettagmod, tag, member)

        # - Lookup profile
        try:
            player = await self.fetch_player_profile(tag)
        except json.decoder.JSONDecodeError:
            await self.bot.send_message(
                ctx.message.channel,
                "Error getting data from API. "
                "Aborting…")
            return
        except asyncio.TimeoutError:
            await self.bot.send_message(
                ctx.message.channel,
                "Getting profile info resulted in a timeout. "
                "API may be down or player tag cannot be found. "
                "Aborting…")
            return

        # - Show player info
        await self.bot.say(self.player_info(player))

        # - Change nickname to IGN
        ign = player.get('name')
        if ign is None:
            await self.bot.say("Cannot find IGN.")
        else:
            try:
                await self.bot.change_nickname(member, ign)
            except discord.HTTPException:
                await self.bot.say(
                    "I don’t have permission to change nick for this user.")
            else:
                await self.bot.say("{} changed to {}.".format(member.mention, ign))

        # - Check clan
        player_clan_tag = None
        try:
            player_clan = player.get("clan", None)
            if player_clan is not None:
                player_clan_tag = player_clan.get("tag")
        except KeyError:
            await self.bot.say("Cannot find clan tag in API. Aborting…")
            return

        player_clan_tag = SCTag(player_clan_tag).tag
        channels = ctx.message.server.channels

        if player_clan_tag in CLAN_PERMISSION.keys():
            # - Check allow role assignment
            perm = CLAN_PERMISSION[player_clan_tag]
            if not perm['assign_role']:
                await self.bot.say('User belong to a clan that requires roster verifications.')
                return

            # - Assign role - not members
            mm = self.bot.get_cog("MemberManagement")
            if not perm['member']:
                await ctx.invoke(mm.changerole, member, perm['role'], 'Visitor')
                channel = discord.utils.get(channels, name="visitors")
                await ctx.invoke(self.dmusers, self.config.messages.visitor_rules, member)
            else:
                # remove all clan roles
                to_remove = CLAN_ROLES.copy()
                to_remove.extend(VISITOR_ROLES)
                to_remove.extend(RECRUIT_ROLES)
                to_add = MEMBER_ROLES.copy()
                to_add.append(perm['role'])
                server = ctx.message.server
                removed_roles = await self.remove_roles(server, member, to_remove)
                await self.add_roles(server, member, to_add)
                await self.bot.say(
                    "Removed {} and added {} to {}".format(
                        ", ".join(removed_roles) if len(removed_roles) else 'nothing',
                        ", ".join(to_add),
                        member
                    )
                )

                channel = discord.utils.get(channels, name="family-chat")
                await ctx.invoke(self.dmusers, self.config.messages.member, member)

            if channel is not None:
                await self.bot.say(
                    "{} Welcome! You may now chat at {} — enjoy!".format(
                        member.mention, channel.mention))

        else:
            await ctx.invoke(self.visitor, member)

    async def royaleapi_verify(self, ctx, member: discord.Member, tag):
        """Verify CR members by player tag."""
        sctag = SCTag(tag)
        if not sctag.valid:
            await self.bot.say(sctag.invalid_error_msg)
            return

        tag = sctag.tag

        # - Set their tags
        await ctx.invoke(self.crsettagmod, tag, member)

        # - Lookup profile
        try:
            player = await self.fetch_player_profile(tag)
        except json.decoder.JSONDecodeError:
            await self.bot.send_message(
                ctx.message.channel,
                "Error getting data from API. "
                "Aborting…")
            return
        except asyncio.TimeoutError:
            await self.bot.send_message(
                ctx.message.channel,
                "Getting profile info resulted in a timeout. "
                "API may be down or player tag cannot be found. "
                "Aborting…")
            return

        # - Show player info
        await self.bot.say(self.player_info(player))

        # - Change nickname to IGN
        ign = player.get('name')
        if ign is None:
            await self.bot.say("Cannot find IGN.")
        else:
            try:
                await self.bot.change_nickname(member, ign)
            except discord.HTTPException:
                await self.bot.say(
                    "I don’t have permission to change nick for this user.")
            else:
                await self.bot.say("{} changed to {}.".format(member.mention, ign))

        # - Check clan
        player_clan_tag = None
        try:
            player_clan = player.get("clan", None)
            if player_clan is not None:
                player_clan_tag = player_clan.get("tag")
        except KeyError:
            await self.bot.say("Cannot find clan tag in API. Aborting…")
            return

        player_clan_tag = SCTag(player_clan_tag).tag

        if player_clan_tag in ['9R8G9290']:
            mm = self.bot.get_cog("MemberManagement")
            await ctx.invoke(mm.changerole, member, 'Member')
            channel = discord.utils.get(
                ctx.message.server.channels, name="clan")

            if channel is not None:
                await self.bot.say(
                    "{} Welcome! You may now chat at {} — enjoy!".format(
                        member.mention, channel.mention))

        else:
            await ctx.invoke(self.visitor, member)

    async def _add_roles(self, member, role_names):
        """Add roles"""
        server = member.server
        roles = [discord.utils.get(server.roles, name=role_name) for role_name in role_names]
        try:
            await self.bot.add_roles(member, *roles)
        except discord.Forbidden:
            raise
        except discord.HTTPException:
            raise

    async def _remove_roles(self, member, role_names):
        """Add roles"""
        server = member.server
        roles = [discord.utils.get(server.roles, name=role_name) for role_name in role_names]
        try:
            await self.bot.remove_roles(member, *roles)
        except discord.Forbidden:
            raise
        except discord.HTTPException:
            raise

    @racf.command(name="bsverify", aliases=['bv'], pass_context=True, no_pm=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racf_bsveify(self, ctx, member: discord.Member, tag):
        """Verify BS members by player tag."""

        # verify permissions on 100T server
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        # - Set tags
        bsdata = self.bot.get_cog("BSData")
        await ctx.invoke(bsdata.bsdata_settag, tag, member)

        # - Lookup profile
        try:
            player = await bsdata.get_player_model(tag)
        except asyncio.TimeoutError:
            await self.bot.send_message(
                ctx.message.channel,
                "Getting profile info resulted in a timeout. "
                "API may be down or player tag cannot be found. "
                "Aborting…")
            return

        # - Check clan
        try:
            band_tag = player.band.tag
        except KeyError:
            await self.bot.say("Profile API may be down. Aborting…")
            return

        if band_tag not in BAND_PERMISSION.keys():
            await self.bot.say("User is not in our clans.")
            return

        # - Output info
        await self.bot.say(
            "Player Tag: {0.tag}\n"
            "IGN: {0.username}\n"
            "Clan Name: {0.band.name}\n"
            "Clan Tag: {0.band.tag}\n"
            "Clan Role: {0.band.role}\n"
            "Trophies: {0.trophies:,} / {0.highest_trophies:,} PB".format(
                player
            )
        )

        # - Change nickname to IGN
        ign = player.username
        if ign is None:
            await self.bot.say("Cannot find IGN.")
        else:
            try:
                await self.bot.change_nickname(member, ign)
            except discord.HTTPException:
                await self.bot.say(
                    "I don’t have permission to change nick for this user.")
            else:
                await self.bot.say("{} changed to {}.".format(member.mention, ign))

        # - Assign roles
        role = BAND_PERMISSION[band_tag]["role"]
        await ctx.invoke(self.brawlstars, member, role)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*CHANGECLAN_ROLES)
    async def changeclan(self, ctx, clan: str = None, member: discord.Member = None):
        """Update clan role when moved to a new clan.

        Example: !changeclan Delta
        """
        author = ctx.message.author
        server = ctx.message.server
        if member is not None:
            if author != member:
                # verify permissions on 100T server
                verified = await check_manage_roles(ctx, self.bot)
                if not verified:
                    return

                # if not author.server_permissions.manage_roles:
                #     await self.bot.say("You do not have permissions to edit other people’s roles.")
                #     return
        else:
            member = author

        clans = [c.lower() for c in CLANS]
        await self.do_changeclan(ctx, member, server, clan, clans)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BS_CHANGECLAN_ROLES)
    async def bschangeclan(self, ctx, clan: str = None):
        """Update clan role when moved to a new clan.

        Example: !bschangeclan BS-Delta
        """
        member = ctx.message.author
        server = ctx.message.server
        if clan is None:
            await self.bot.send_cmd_help(ctx)
            return
        if not clan.lower().startswith(BS_CLANS_PREFIX.lower()):
            clan = BS_CLANS_PREFIX + clan
        clans = [c.lower() for c in BS_CLANS]
        await self.do_changeclan(ctx, member, server, clan, clans)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def bselder(self, ctx, member: discord.Member):
        """Add bs-elder role for member.

        TMP command for bs leader who’s not a bot comamnder.
        """
        role = discord.utils.get(ctx.message.server.roles, name="BS-Elder")
        await self.bot.add_roles(member, role)
        await self.bot.say(
            "Added {} for {}".format(
                role.name, member.display_name))

    async def do_changeclan(self, ctx, member, server, clan: str = None, clans=[]):
        """Perform clan changes."""
        if clan is None:
            await self.bot.send_cmd_help(ctx)
            return

        if clan.lower() not in clans:
            await self.bot.say(
                "{} is not a clan you can self-assign.".format(clan))
            return

        clan_roles = [r for r in server.roles if r.name.lower() in clans]

        to_remove_roles = set(member.roles) & set(clan_roles)
        to_add_roles = [
            r for r in server.roles if r.name.lower() == clan.lower()]

        await self.bot.remove_roles(member, *to_remove_roles)
        await self.bot.say("Removed {} for {}".format(
            ",".join([r.name for r in to_remove_roles]),
            member.display_name))

        await self.bot.add_roles(member, *to_add_roles)
        await self.bot.say("Added {} for {}".format(
            ",".join([r.name for r in to_add_roles]),
            member.display_name))

    async def changerole(self, ctx, member: discord.Member = None, *roles: str):
        """Change roles of a user.

        Uses the changerole command in the MM cog.
        """
        mm = self.bot.get_cog("MemberManagement")
        if mm is None:
            await self.bot.say(
                "You must load MemberManagement for this to run.")
            return
        await ctx.invoke(mm.changerole, member, *roles)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def mentionusers(self, ctx, role: str, *msg):
        """Mention users by role.

        Example:
        !mentionusers Delta Anyone who is 4,300+ please move up to Charlie!

        Note: only usable by people with the permission to mention @everyone
        """
        server = ctx.message.server
        server_roles_names = [r.name for r in server.roles]

        if role not in server_roles_names:
            await self.bot.say(
                "{} is not a valid role on this server.".format(role))
        elif not msg:
            await self.bot.say("You have not entered any messages.")
        else:
            out_mentions = []
            for m in server.members:
                if role in [r.name for r in m.roles]:
                    out_mentions.append(m.mention)
            await self.bot.say("{} {}".format(" ".join(out_mentions),
                                              " ".join(msg)))

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def mentionrole(self, ctx, role_name: str, *, msg):
        """Mention a role with message.

        Temporarily make a role mentionable and send a message.
        Delete message sending the command so it won’t be a dupe.
        """
        server = ctx.message.server

        # role = discord.utils.get(server.roles, name=role_name)
        # find role regardless of casing
        role = None
        for r in server.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
        if role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(
                    role_name))
            return

        orig_mentionable = role.mentionable
        await self.bot.edit_role(server, role, mentionable=True)
        await self.bot.say(
            '**{author.mention}** ({author.id}): '
            '{role.mention} {message}'.format(
                author=ctx.message.author,
                role=role,
                message=msg))
        await self.bot.edit_role(server, role, mentionable=orig_mentionable)
        await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True)
    async def avatar(self, ctx, member: discord.Member = None):
        """Display avatar of the user."""
        author = ctx.message.author

        if member is None:
            member = author
        await self.bot.say(member.avatar_url)

    @commands.command(pass_context=True, no_pm=True)
    async def serverinfo2(self, ctx: Context):
        """Show server's informations specific to RACF."""
        server = ctx.message.server
        online = len([m.status for m in server.members
                      if m.status == discord.Status.online or
                      m.status == discord.Status.idle])
        total_users = len(server.members)
        text_channels = len([x for x in server.channels
                             if x.type == discord.ChannelType.text])
        voice_channels = len(server.channels) - text_channels
        passed = (ctx.message.timestamp - server.created_at).days
        created_at = ("Since {}. That's over {} days ago!"
                      "".format(server.created_at.strftime("%d %b %Y %H:%M"),
                                passed))

        role_names = [
            "Leader", "Co-Leader", "High Elder", "Elder",
            "Member", "Honorary Member", "Visitor"]
        role_count = {}
        for role_name in role_names:
            role_count[role_name] = len(
                [m for m in server.members
                 if role_name in [r.name for r in m.roles]])

        colour = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        data = discord.Embed(
            description=created_at,
            colour=discord.Colour(value=colour))
        data.add_field(name="Region", value=str(server.region))
        data.add_field(name="Users", value="{}/{}".format(online, total_users))
        data.add_field(name="Text Channels", value=text_channels)
        data.add_field(name="Voice Channels", value=voice_channels)
        data.add_field(name="Roles", value=len(server.roles))
        data.add_field(name="Owner", value=str(server.owner))
        data.add_field(name="\a", value="\a", inline=False)

        for role_name in role_names:
            data.add_field(name="{}s".format(role_name),
                           value=role_count[role_name])

        data.set_footer(text="Server ID: " + server.id)

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(name=server.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def member2roles(self, ctx: Context, with_role, new_role):
        """Add role to a list of users with specific roles."""
        server = ctx.message.server
        with_role = discord.utils.get(server.roles, name=with_role)
        new_role = discord.utils.get(server.roles, name=new_role)
        if with_role is None:
            await self.bot.say('{} is not a valid role'.format(with_role))
            return
        if new_role is None:
            await self.bot.say('{} is not a valid role.'.format(new_role))
            return
        members = [m for m in server.members if with_role in m.roles]
        for member in members:
            await self.bot.add_roles(member, new_role)
            await self.bot.say("Added {} for {}".format(
                new_role, member.display_name))

    @commands.command(pass_context=True, no_pm=True, aliases=["m2v"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def member2visitor(self, ctx: Context, *members: discord.Member):
        """Re-assign list of people from members to visitors."""
        server = ctx.message.server
        to_add_roles = [r for r in server.roles if r.name == 'Visitor']
        for member in members:
            to_remove_roles = [
                r for r in member.roles if r.name in self.config.roles.member_default]
            to_remove_roles.extend([
                r for r in member.roles if r.name in CLANS])
            to_remove_roles.extend([
                r for r in member.roles if r.name in ['eSports']])
            await self.bot.add_roles(member, *to_add_roles)
            await self.bot.say("Added {} for {}".format(
                ", ".join([r.name for r in to_add_roles]), member.display_name))
            await self.bot.remove_roles(member, *to_remove_roles)
            await self.bot.say("Removed {} from {}".format(
                ", ".join([r.name for r in to_remove_roles]), member.display_name))

    @commands.command(pass_context=True, no_pm=True, aliases=["v2m"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitor2member(
            self, ctx: Context, member: discord.Member, *roles):
        """Assign visitor to member and add clan name."""
        server = ctx.message.server
        roles_param = self.config.roles.member_default.copy()
        roles_param.extend(roles)
        roles_param.extend(["-Visitor", "-Recruit"])
        channel = discord.utils.get(
            ctx.message.server.channels, name="family-chat")
        # print(roles_param)
        await self.changerole(ctx, member, *roles_param)
        if channel is not None:
            await self.bot.say(
                "{} Welcome! Main family chat at {} — enjoy!".format(
                    member.mention, channel.mention))

        await ctx.invoke(self.dmusers, self.config.messages.member, member)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def dmusers(self, ctx: Context, msg: str = None,
                      *members: discord.Member):
        """Send a DM to a list of people.

        Example
        !dmusers "Please move up to Charlie" @SML @6john Meridian
        """
        if msg is None:
            await self.bot.say("Please include a message.")
        elif not len(members):
            await self.bot.say("You must include at least one member.")
        else:
            data = discord.Embed(description=msg)
            data.set_author(
                name=ctx.message.author,
                icon_url=ctx.message.author.avatar_url)
            data.set_footer(text=ctx.message.server.name)
            # data.add_field(
            #     name="How to reply",
            #     value="DM or tag {0.mention} if you want to reply.".format(
            #         ctx.message.author))
            for m in members:
                try:
                    await self.bot.send_message(m, embed=data)
                    await self.bot.say(
                        "Message sent to {}".format(m.display_name))
                except discord.errors.Forbidden:
                    await self.bot.say(
                        "{} does not accept DMs from me.".format(
                            m.display_name))
                    raise

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def changenick(
            self, ctx: Context, member: discord.Member, *, nickname: str):
        """Change the nickname of a member.

        Example
        !changenick SML "New Nick"
        !changenick @SML "New Nick"
        """
        # await self.bot.change_nickname(member, nickname)
        try:
            await self.bot.change_nickname(member, nickname)
        except discord.HTTPException:
            await self.bot.say(
                "I don’t have permission to do this.")
        else:
            await self.bot.say("{} changed to {}.".format(member.mention, nickname))

    @commands.command(pass_context=True, no_pm=True)
    async def emojis(self, ctx: Context, embed=False):
        """Show all emojis available on server."""
        server = ctx.message.server

        if embed:
            emoji_list = [emoji for emoji in server.emojis if not emoji.managed]
            emoji_lists = grouper(25, emoji_list)
            for emoji_list in emoji_lists:
                em = discord.Embed()
                for emoji in emoji_list:
                    if emoji is not None:
                        em.add_field(
                            name=str(emoji), value="`:{}:`".format(emoji.name))
                await self.bot.say(embed=em)
        else:
            out = []
            for emoji in server.emojis:
                # only include in list if not managed by Twitch
                if not emoji.managed:
                    emoji_str = str(emoji)
                    out.append("{} `:{}:`".format(emoji_str, emoji.name))
            for page in pagify("\n".join(out), shorten_by=12):
                await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True, aliases=["k5", "pleb", "m5"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def kick5050(self, ctx, member: discord.Member):
        """Notify member that they were kicked for lower trophies.

        Remove clan tags in the process.
        """
        await ctx.invoke(self.dmusers, self.config.messages.kick5050, member)
        member_clan = [
            '-{}'.format(r.name) for r in member.roles if r.name in CLANS]
        if len(member_clan):
            await self.changerole(ctx, member, *member_clan)
        else:
            await self.bot.say("Member has no clan roles to remove.")

    @commands.command(pass_context=True, no_pm=True, aliases=["k5a"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def k5alpha(self, ctx, member: discord.Member):
        """Notify member that they were kicked clan war performance.

        Remove clan tags in the process.
        """
        await ctx.invoke(self.dmusers, self.config.messages.k5alpha, member)
        member_clan = [
            '-{}'.format(r.name) for r in member.roles if r.name in CLANS]
        if len(member_clan):
            await self.changerole(ctx, member, *member_clan)
        else:
            await self.bot.say("Member has no clan roles to remove.")

    @commands.command(pass_context=True, no_pm=True, aliases=["bsk5", "bk5"])
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def bskick5050(self, ctx, member: discord.Member):
        """Notify member that they were kicked for lower trophies.

        Remove clan tags in the process.
        """
        await ctx.invoke(self.dmusers, self.config.messages.bskick5050, member)
        member_clan = [
            '-{}'.format(r.name) for r in member.roles if r.name in BS_CLANS]
        if len(member_clan):
            await self.changerole(ctx, member, *member_clan)
        else:
            await self.bot.say("Member has no clan roles to remove.")

    @commands.command(pass_context=True, no_pm=True, aliases=['v'])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitor(self, ctx, member: discord.Member):
        """Assign member with visitor roles and give them info."""
        visitor_roles = ["Visitor"]
        channel = discord.utils.get(
            ctx.message.server.channels, name="visitors")
        await self.changerole(ctx, member, *visitor_roles)
        if channel is not None:
            await self.bot.say(
                "{} You can now chat in {} — enjoy!".format(
                    member.mention, channel.mention))
        await ctx.invoke(self.visitorrules, member)

    @commands.command(pass_context=True, no_pm=True, aliases=['bs'])
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def brawlstars(self, ctx, member: discord.Member, *roles):
        """Assign member with visitor and brawl-stars roles."""
        bs_roles = ["Brawl-Stars"]
        if discord.utils.get(member.roles, name="Member") is None:
            if discord.utils.get(member.roles, name="Guest") is None:
                if discord.utils.get(member.roles, name="Visitor") is None:
                    bs_roles.append("Visitor")
        channel = discord.utils.get(
            ctx.message.server.channels, name="brawl-stars")
        await self.changerole(ctx, member, *bs_roles)
        if channel is not None:
            await self.bot.say(
                "{} You can now chat in {} — enjoy!".format(
                    member.mention, channel.mention))
        if "Visitor" in bs_roles:
            await ctx.invoke(self.visitorrules, member)

        # Add additional roles if present
        if len(roles):
            await self.changerole(ctx, member, *roles)

    @commands.command(pass_context=True, no_pm=True, aliases=['vrules', 'vr'])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitorrules(self, ctx, *members: discord.Member):
        """DM server rules to user."""
        try:
            await ctx.invoke(self.dmusers, self.config.messages.visitor_rules, *members)
            await self.bot.say(
                "A list of rules has been sent via DM to {}.".format(
                    ", ".join([m.display_name for m in members])))
        except discord.errors.Forbidden:
            await self.bot.say(
                '{} {}'.format(
                    " ".join([m.mention for m in members]),
                    self.config.messages.visitor_rules))

    @commands.command(pass_context=True, no_pm=True)
    async def pay(self, ctx, amt, *members: discord.Member):
        """Pay amount to member(s).

        If more than one person is specificed, equally divide the credits.
        """
        bank = self.bot.get_cog('Economy').bank
        amt = int(amt)
        split_amt = int(amt / (len(members)))
        for member in members:
            if member != ctx.message.author:
                try:
                    bank.transfer_credits(
                        ctx.message.author, member, split_amt)
                except cogs.economy.NoAccount:
                    await self.bot.say(
                        "{} has no account.".format(member.display_name))
        split_msg = ""
        if len(members) > 1:
            split_msg = ' ({} credits each)'.format(split_amt)
        await self.bot.say(
            "{} has transfered {} credits{} to {}.".format(
                ctx.message.author.display_name,
                amt,
                split_msg,
                ", ".join([m.display_name for m in members])))

    @commands.command(pass_context=True, no_pm=True)
    async def skill(self, ctx, pb, *cardlevels):
        """Calculate skill level based on card levels.

        !skills 5216 c12 c12 r10 r9 e5 e4 l2 l1
        c = commons
        r = rares
        e = epics
        l = legendaries
        """
        if not pb.isdigit():
            await self.bot.say("PB (Personal Best) must be a number.")
            await self.bot.send_cmd_help(ctx)
            return
        if len(cardlevels) != 8:
            await self.bot.say("You must enter exactly 8 cards.")
            await self.bot.send_cmd_help(ctx)
            return
        rarities = {
            'c': 0,
            'r': 2,
            'e': 5,
            'l': 8
        }
        rarity_names = {
            'c': 'Common',
            'r': 'Rare',
            'e': 'Epic',
            'l': 'Legendary'
        }
        cards = [{'r': cl[0], 'l': int(cl[1:])} for cl in cardlevels]

        common_levels = []
        for card in cards:
            rarity = card['r']
            level = int(card['l'])
            if rarity not in rarities:
                await self.bot.say('{} is not a valid rarity.'.format(rarity))
                return
            common_level = level + rarities[rarity]
            common_levels.append(common_level)

        pb = int(pb)
        skill = pb / sum(common_levels) * 8

        out = []
        out.append('You have entered:')
        out.append(
            ', '.join(
                ['{} ({})'.format(
                    rarity_names[card['r']], card['l']) for card in cards]))
        out.append(
            'With a PB of {}, your skill level is {}.'.format(pb, skill))

        await self.bot.say('\n'.join(out))

    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    @commands.command(pass_context=True, no_pm=True)
    async def iosfix(self, ctx: Context, *members: discord.Member):
        """Quick fix to iOS bug.

        Remove all roles from members and then re-add them."""
        await self.bot.say("iOS Fix")
        await self.run_iosfix(ctx, *members)

    @commands.command(pass_context=True, no_pm=True)
    async def iosfixme(self, ctx: Context):
        """Self-Quick fix to iOS bug."""
        await self.bot.say("iOS Fix me")
        await self.run_iosfix(ctx, ctx.message.author)

    @checks.serverowner_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def say(self, ctx, *, msg):
        """Have bot say stuff. Remove command after run."""
        message = ctx.message
        await self.bot.delete_message(message)
        await self.bot.say(msg)

    @checks.serverowner_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def sayc(self, ctx, channel: discord.Channel, *, msg):
        """Have bot say stuff in channel. Remove command after run."""
        message = ctx.message
        await self.bot.delete_message(message)
        await self.bot.send_message(channel, msg)

    @commands.command(pass_context=True, no_pm=True)
    async def crsettag(self, ctx, tag, member: discord.Member = None):
        """Set CR tags for members.

        This is the equivalent of running:
        !crclan settag [tag] [member]
        !crprofile settag [tag] [member]

        If those cogs are not loaded, it will just ignore it.
        """
        author = ctx.message.author
        server = ctx.message.server

        crclan = self.bot.get_cog("CRClan")
        crprofile = self.bot.get_cog("CRProfile")
        racfaudit = self.bot.get_cog("RACFAudit")

        # verify permissions on 100T server
        verified = await check_manage_roles(ctx, self.bot)

        allowed = False
        if member is None:
            member = author
            allowed = True
        elif member.id == author.id:
            allowed = True
        elif verified:
            allowed = True
        elif author.server_permissions.manage_roles:
            allowed = True

        if not allowed:
            await self.bot.say("Only people with manage-roles permissions can set tags for others.")
            return

        if crclan is not None:
            await ctx.invoke(crclan.crclan_settag, tag, member)
        if crprofile is not None:
            await ctx.invoke(crprofile.crprofile_settag, tag, member)
        if racfaudit is not None:
            success = await racfaudit.set_player_tag(tag, member)
            if success:
                await self.bot.say("RACF Audit: associated player tag with member.")
            if not success:
                player = await racfaudit.get_player_tag(tag)
                if str(player.get('user_id')) == str(member.id):
                    await self.bot.say("RACF Audit: associated player tag with member. (already set)")
                else:
                    await self.bot.say(
                        "RACF Audit: Tag {} already associated with member {}. Ask a mod to run `!crsettagmod` to overwrite.".format(
                            player.get('tag'),
                            server.get_member(player.get('user_id'))
                        ))

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def crrmtag(self, ctx, tag):
        """Remove tag from further association.

        Applies to !crprofile and !racfaudit
        """
        crprofile = self.bot.get_cog("CRProfile")
        racfaudit = self.bot.get_cog("RACFAudit")

        if crprofile is not None:
            await ctx.invoke(crprofile.crprofileset_rm_tag, tag)
        if racfaudit is not None:
            await ctx.invoke(racfaudit.racfaudit_rm_tag, tag)

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def crsettagmod(self, ctx, tag, member: discord.Member = None, force=True):
        """Set CR tags for members.

        If the bot complains that that player tag is associated with another user
        You can overwrite by running
        !crsettagmod [tag] [member] 1
        """
        server = ctx.message.server

        if member is None:
            await self.bot.say("You must specify a member.")
            return

        crclan = self.bot.get_cog("CRClan")
        crprofile = self.bot.get_cog("CRProfile")
        racfaudit = self.bot.get_cog("RACFAudit")

        if crclan is not None:
            await ctx.invoke(crclan.crclan_settag, tag, member)
        if crprofile is not None:
            await ctx.invoke(crprofile.crprofile_settag, tag, member)
        if racfaudit is not None:
            success = await racfaudit.set_player_tag(tag, member, force=force)
            if success:
                await self.bot.say("RACF Audit: associated player tag with member.")
            if not success:
                player = await racfaudit.get_player_tag(tag)
                print(player)
                if str(player.get('user_id')) == str(member.id):
                    await self.bot.say("RACF Audit: associated player tag with member. (already set)")
                else:
                    await self.bot.say(
                        "RACF Audit: Tag {} already associated with member {}. Ask a mod to run `!crsettagmod` to overwrite.".format(
                            player.get('tag'),
                            server.get_member(player.get('user_id'))
                        ))

    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    @commands.command(pass_context=True, no_pm=True)
    async def elder(self, ctx, *members: discord.Member):
        """Elder promotion DM + role change."""
        elder_roles = ["Elder"]
        for member in members:
            await self.changerole(ctx, member, *elder_roles)
            try:
                await ctx.invoke(self.dmusers, self.config.messages.elder, member)
            except discord.errors.Forbidden:
                await self.bot.say(
                    "Unable to send DM to {}. User might have a stricter DM setting.".format(member))

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def reelder(self, ctx, *members: discord.Member):
        """Refresher for elders."""
        for member in members:
            try:
                await ctx.invoke(self.dmusers, self.config.messages.elder_refresh, member)
            except discord.errors.Forbidden:
                await self.bot.say(
                    "Unable to send DM to {}. User might have a stricter DM setting.".format(member))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def fixme(self, ctx):
        """Leader fix role permissions."""
        await self.bot.say("Fix me")
        author = ctx.message.author
        for role in author.roles:
            if role.name in ["Bot Commander", "Leader", "Co-Leader", "Member", "addrole", "Coleader"]:
                try:
                    await self.bot.remove_roles(author, role)
                    await self.bot.add_roles(author, role)
                    await self.bot.say(
                        "Removed and re-added {} to {}.".format(
                            role, author))
                except discord.errors.Forbidden:
                    await self.bot.say(
                        "I am not allowed to remove {} from {}.".format(
                            role, author))

    async def run_iosfix(self, ctx: Context, *members: discord.Member):
        """Actual fix to allow members without the bot commander to run on themselves."""
        for member in members:
            roles = member.roles.copy()
            for role in roles:
                if not role.is_everyone:
                    try:
                        await self.bot.remove_roles(member, role)
                        await self.bot.add_roles(member, role)
                        await self.bot.say(
                            "Removed and re-added {} to {}.".format(
                                role, member))
                    except discord.errors.Forbidden:
                        await self.bot.say(
                            "I am not allowed to remove {} from {}.".format(
                                role, member))

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['re'])
    async def recruit(self, ctx, member: discord.Member = None, tag=None):
        """Add recruit tag."""
        if member is None:
            await self.bot.send_cmd_help()
            return

        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        channel = ctx.message.channel

        tag = clean_tag(tag)

        # run verify if tag is provided
        if tag is not None:
            await ctx.invoke(self.racf_verify, member, tag)

        # Send visitor rule if in welcome
        elif channel.name == 'welcome':
            await ctx.invoke(self.visitor, member)

        recruit_role = discord.utils.get(ctx.message.server.roles, name='Recruit')
        recruit_channel = discord.utils.get(ctx.message.server.channels, name='recruit')
        await self.bot.add_roles(member, recruit_role)
        await self.bot.say("Added Recruit to {}".format(member))

        # Add player profile to recruit channel automatically
        if tag is not None:
            await self.bot.send_message(
                recruit_channel,
                "{member.mention} Thank you for your interest! "
                "Our leaders will review your profile and let you know if you have been accepted. "
                "https://royaleapi.com/player/{tag}".format(member=member, tag=tag)
            )
            await self.bot.send_message(
                recruit_channel,
                embed=await self.cwready_embed(tag)
            )
        else:
            await self.bot.send_message(
                recruit_channel,
                "{member.mention} Thank you for your interest! Please type "
                "`!pt PlayerTag` at {channel.mention} — for example, type `!pt C0G20PR2` if that’s your tag. "
                "Our leaders will review your profile and let you know if you have been accepted."
                "".format(member=member, channel=recruit_channel)
            )

    async def cwready_embed(self, tag):
        url = 'https://royaleapi.com/data/member/war/ready/{}'.format(tag)
        player_url = "https://royaleapi.com/player/{}".format(tag)
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                elif resp.status == 404:
                    raise TagNotFound()
                else:
                    raise UnknownServerError()

        em = discord.Embed(
            title="{name} #{tag}".format(name=data.get('name'), tag=data.get('tag')),
            description="Clan War Readiness",
            url=player_url
        )
        # em.url = player_url
        # stats
        clan_name = data.get('clan', {}).get('name', '')
        clan_tag = data.get('clan', {}).get('tag', '')
        em.add_field(name='Clan', value="{} #{}".format(clan_name, clan_tag))
        em.add_field(
            name='Trophies',
            value="{trophies} / {pb} PB :trophy:".format(
                trophies=data.get('trophies', 0),
                pb=data.get('trophies_best', 0)
            ))
        em.add_field(name='War Wins', value=data.get('war_day_wins', 0))
        em.add_field(name='War Cards', value=data.get('clan_cards_collected', 0))
        em.add_field(name='Challenge Max Wins', value=data.get('challenge_max_wins', 0))
        em.add_field(name='Challenge Cards Won', value=data.get('challenge_cards_won', 0))

        # leagues
        for league in data.get('leagues'):
            name = league.get('name')
            total = league.get('total', 0)
            percent = league.get('total_percent', 0)
            levels = league.get('levels', 0)
            f_name = "{name} League .. {percent:.0%} .. {levels}".format(
                name=name, total=total, percent=percent, levels=levels
            )
            cards = league.get('cards', [])

            groups = grouper(cards, 20)
            for index, crds in enumerate(groups):
                value = ""
                for card in crds:
                    if card is not None:
                        value += get_emoji(self.bot, card.get('key', None).replace('-', ''))
                        if card.get('overlevel'):
                            value += '+'
                em.add_field(name=f_name if index == 0 else '.', value=value, inline=False)

        em.set_footer(text=player_url, icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')

        return em

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['cwr'])
    async def cwready(self, ctx, member: discord.Member = None):
        """Return clan war readiness."""
        if member is None:
            member = ctx.message.author

        tag = None

        # if tag is none, attempt to load from racf_audit
        db = os.path.join("data", "racf_audit", "player_db.json")
        players = dataIO.load_json(db)
        for k, v in players.items():
            if v.get('user_id') == member.id:
                tag = v.get('tag')

        if tag is None:
            await self.bot.say("Cannot find associated tag in DB. Please use `cwreadytag` or `cwrt` to fetch by tag")
            await self.bot.send_cmd_help(ctx)
            return

        tag = clean_tag(tag)

        try:
            em = await self.cwready_embed(tag)
        except TagNotFound:
            await self.bot.say("Invalid tag #{}. Please verify that tag is set correctly.".format(tag))
            return
        except UnknownServerError:
            await self.bot.say("Unknown server error from API")
            return
        except Exception as e:
            logger.exception("Unknown exception", e)
            await self.bot.say("Server error: {}".format(e))
        else:
            await self.bot.say(embed=em)

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['cwrt'])
    async def cwreadytag(self, ctx, tag):
        """Return clan war readiness."""
        tag = clean_tag(tag)

        try:
            em = await self.cwready_embed(tag)
        except Exception as e:
            logger.exception("Unknown exception", e)
            await self.bot.say("Server error: {}".format(e))
        else:
            await self.bot.say(embed=em)

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['rmre'])
    async def rmrecruit(self, ctx, member: discord.Member = None):
        """Remove recruit."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        if member is None:
            await self.bot.send_cmd_help()
            return

        # remove roles
        server = ctx.message.server
        clans = ['', 'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'Yolo', 'Zen']
        role_names = ['{}Recruit'.format(clan) for clan in clans]
        roles = [discord.utils.get(server.roles, name=role_name) for role_name in role_names]
        roles = [r for r in roles if r]
        await self.bot.remove_roles(member, *roles)
        await self.bot.say("Removed {} from {}".format(", ".join(role_names), member))

        # delete messages from recruit channel
        recruit_channel = discord.utils.get(ctx.message.server.channels, name='recruit')
        tmp = ctx.message
        to_delete = [ctx.message]
        async for message in self.bot.logs_from(recruit_channel, limit=200, before=tmp):
            if message.author == member:
                to_delete.append(message)

        for message in to_delete:
            try:
                await self.bot.delete_message(message)
            except:
                pass

    @commands.command(pass_context=True, no_pm=True)
    async def reject(self, ctx, member: discord.Member):
        """Remove recruit."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return
        await ctx.invoke(self.dmusers, self.config.messages.reject, member)
        await ctx.invoke(self.rmrecruit, member)

    @commands.command(pass_context=True, no_pm=True, aliases=['pt'])
    async def playertag(self, ctx, player_tag):
        """Link to RoyaleAPI player profile
        """
        tag = clean_tag(player_tag)
        await self.bot.say("https://royaleapi.com/player/{}".format(tag))
        await self.bot.say(embed=await self.cwready_embed(tag))

    @commands.command(pass_context=True, no_pm=True)
    async def toprole(self, ctx, member: discord.Member = None):
        """Return top role of self (or another member).
        
        Written mostly for debugging Discord’s odd behavior.
        """
        if member is None:
            member = ctx.message.author
        await self.bot.say(member.top_role.name)

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(name="rmvisitorclan", no_pm=True, pass_context=True)
    async def visitor_remove_clan_roles(self, ctx):
        """Remove clan roles from visitors without the member role."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            await self.bot.say("Not verified")
            return

        server = ctx.message.server
        clan_role_names = [
            'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'YOLO', 'Zen'
        ]
        clan_roles = [discord.utils.get(server.roles, name=name) for name in clan_role_names]
        for member in server.members:
            member_role_names = [r.name for r in member.roles]
            if 'Member' in member_role_names:
                continue
            if 'Visitor' in member_role_names:
                for clan_role in clan_roles:
                    if clan_role in member.roles:
                        await self.bot.remove_roles(member, clan_role)
                        await self.bot.say("Removed {} from {}".format(clan_role, member))

        await self.bot.say("Completed.")

    @checks.mod_or_permissions()
    @commands.command(name="fadmin", no_pm=True, pass_context=True)
    async def fadmin(self, ctx, arg):
        """Return hash used on fadmin."""
        arg = arg.upper()
        hash = int(arg[::-1], 36)
        await self.bot.say("fadmin: {}".format(hash))

    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(no_pm=True, pass_context=True)
    async def rmnonmemberclanroles(self, ctx):
        """Remove clan roles for people without member roles."""
        server = ctx.message.server
        users = []
        for member in server.members:
            member_role_names = set([r.name for r in member.roles])
            allowed_role_names = {'Member', 'Keep-Member', 'Special'}
            # find set intersection
            inter = member_role_names & allowed_role_names
            if len(inter) == 0:
                users.append(member)

        clan_roles = {'Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'YOLO', 'Zen'}
        users_with_clan_roles = []
        for user in users:
            user_role_names = set([r.name for r in user.roles])
            inter = user_role_names & clan_roles
            if len(inter):
                users_with_clan_roles.append(user)

        for user in users_with_clan_roles:
            to_remove_roles = []
            for role in user.roles:
                if role.name in clan_roles:
                    to_remove_roles.append(role)
            if len(to_remove_roles) > 0:
                await self.bot.remove_roles(user, *to_remove_roles)
                await self.bot.say("Remove {} from {}".format(
                    ", ".join([r.name for r in to_remove_roles]),
                    user
                ))


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    check_folder()
    check_file()
    r = RACF(bot)
    bot.add_cog(r)
