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
from collections import defaultdict

import discord
from __main__ import send_cmd_help
from discord.ext import commands
import aiohttp
import json
import asyncio

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

BOTCOMMANDER_ROLES = ['Bot Commander']

TOGGLE_ROLES = ["Trusted", "Visitor"]

TOGGLE_PERM = {
    "Trusted": [
        "Tournaments"
    ],
    "Visitor": [
    ]
}

PATH = os.path.join("data", "rcs")
JSON = os.path.join(PATH, "settings.json")

RCS_SERVER_IDS = ''


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class RCS:
    """Reddit Clan System (RCS) utility."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def rcsset(self, ctx):
        """RCS Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @rcsset.command(name="apiurl", pass_context=True)
    async def rcsset_profileapi(self, ctx, url):
        """CR Profile API URL base.

        Format:
        If path is http://domain.com/path/LQQ
        Enter http://domain.com/path/
        """
        self.settings["profile_api_url"] = url
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Profile API URL saved.")
        await self.bot.delete_message(ctx.message)

    @rcsset.command(name="apitoken", pass_context=True)
    async def rcssett_porfileapitoken(self, ctx, token):
        """API Authentication token."""
        self.settings["profile_api_token"] = token
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Profile API token saved.")
        await self.bot.delete_message(ctx.message)

    @rcsset.command(name="role", pass_context=True)
    async def rcsset_clan(self, ctx, clan_tag, role_name, role_nick=None):
        """Associate clan tags to role names.
        
        Internally store roles as role IDs in case role renames.
        Optionally set role_nick for used in nicknames for special cases 
        e.g. RACF Delta uses Ⓐ - Delta instead of the default
        """
        server = ctx.message.server
        role = discord.utils.get(server.roles, name=role_name)
        if role is None:
            await self.bot.say("Cannot find that role on this server.")
            return
        if role_nick is None:
            role_nick = role_name
        if clan_tag.startswith('#'):
            clan_tag = clan_tag[1:]
        clan_tag = clan_tag.upper()
        clan = {
            "tag": clan_tag,
            "role_id": role.id,
            "role_name": role.name,
            "role_nick": role_nick
        }
        self.settings[server.id]["clans"][clan_tag] = clan
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Settings updated:\n"
            "Clan Tag: {}\n"
            "Role Name: {}\n"
            "Role Nick: {}\n"
            "Role ID: {}\n".format(
                clan_tag, role_name, role_nick, role.id
            )
        )

    @commands.group(pass_context=True, no_pm=True)
    async def rcs(self, ctx):
        """Reddit Clan System (RCS)."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.mod_or_permissions(manage_roles=True)
    @rcs.command(name="verify", aliases=["v"], pass_context=True, no_pm=True)
    async def verify(self, ctx, member: discord.Member, tag):
        """Verify RCS membership using player tag.
        
        1. Check clan information via CR Profile API
        2. Map clan information to server roles.
        3. Assign Trused + clan roles.
        4. Rename user to IGN (Role)
        
        """
        # Check clan info
        if tag.startswith('#'):
            tag = tag[1:]
        tag = tag.upper()
        player = await self.fetch_player_profile(tag)
        player_clan_tag = player.get("clanTag", None)

        server = ctx.message.server
        clans = self.settings[server.id]["clans"]
        if player_clan_tag not in clans:
            await self.bot.say("User is not in one of our clans, or the clan has not be set by MODs.")
            return

        clan_settings = self.settings[server.id]["clans"][player_clan_tag]

        # Assign roles
        await self.changerole(ctx, member, "Trusted", "Tournaments", clan_settings["role_name"])

        # Rename member to IGN (role_nick)
        nick = "{ign} ({role_nick})".format(
            ign=player["name"],
            role_nick=clan_settings["role_nick"]
        )

        try:
            await self.bot.change_nickname(member, nick)
            await self.bot.say("Renamed {} to {}".format(member, nick))
        except discord.errors.Forbidden:
            await self.bot.say("I do not have permission to change the nick of {}".format(member))

    async def changerole(self, ctx, member: discord.Member, *roles):
        """Perfect change roles."""
        mm = self.bot.get_cog("MemberManagement")
        await ctx.invoke(mm.changerole, member, *roles)

    async def fetch_player_profile(self, tag):
        """Fetch player profile data."""
        url = "{}{}".format('http://api.cr-api.com/profile/', tag)
        print(url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise
        except asyncio.TimeoutError:
            raise

        return data

    @commands.has_any_role(*TOGGLE_ROLES)
    @rcs.command(pass_context=True, no_pm=True)
    async def togglerole(self, ctx, role_name):
        """Self-toggle role assignments."""
        author = ctx.message.author
        server = ctx.message.server
        # toggleable_roles = [r.lower() for r in TOGGLEABLE_ROLES]

        member_role = discord.utils.get(server.roles, name="Trusted")
        is_member = member_role in author.roles

        if is_member:
            toggleable_roles = TOGGLE_PERM["Trusted"]
        else:
            toggleable_roles = TOGGLE_PERM["Visitor"]

        toggleable_roles = sorted(toggleable_roles)

        toggleable_roles_lower = [r.lower() for r in toggleable_roles]

        if role_name.lower() in toggleable_roles_lower:
            role = [
                r for r in server.roles
                if r.name.lower() == role_name.lower()]

            if len(role):
                role = role[0]
                if role in author.roles:
                    await self.bot.remove_roles(author, role)
                    await self.bot.say(
                        "Removed {} role from {}.".format(
                            role.name, author.display_name))
                else:
                    await self.bot.add_roles(author, role)
                    await self.bot.say(
                        "Added {} role for {}.".format(
                            role_name, author.display_name))
            else:
                await self.bot.say(
                    "{} is not a valid role on this server.".format(role_name))
        else:
            out = []
            out.append(
                "{} is not a toggleable role for you.".format(role_name))
            out.append(
                "Toggleable roles for you: {}.".format(
                    ", ".join(toggleable_roles)))
            await self.bot.say("\n".join(out))


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = RCS(bot)
    bot.add_cog(n)
