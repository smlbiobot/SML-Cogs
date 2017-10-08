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
import os
import re
from collections import defaultdict

import discord
import unidecode
import yaml
from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, box
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from tabulate import tabulate

PATH = os.path.join("data", "racf_audit")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def server_role(server, role_name):
    """Return discord role object by name."""
    return discord.utils.get(server.roles, name=role_name)


def member_has_role(server, member, role_name):
    """Return True if member has specific role."""
    role = discord.utils.get(server.roles, name=role_name)
    return role in member.roles


class RACFClan:
    """RACF Clan."""

    def __init__(self, name=None, tag=None, role=None, membership_type=None, model=None):
        """Init."""
        self.name = name
        self.tag = tag
        self.role = role
        self.membership_type = membership_type
        self.model = model

    @property
    def repr(self):
        """Representation of the clan. Used for debugging."""
        o = []
        o.append('RACFClan object')
        o.append(
            "{0.name} #{0.tag} | {0.role.name}".format(self)
        )
        members = sorted(self.model.members, key=lambda m: m.name.lower())
        member_names = [m.name for m in members]
        print(member_names)
        o.append(', '.join(member_names))
        return '\n'.join(o)


class DiscordUser:
    """Discord user = player tag association."""

    def __init__(self, user=None, tag=None):
        """Init."""
        self.user = user
        self.tag = tag


class DiscordUsers:
    """List of Discord users."""

    def __init__(self, crclan_cog, server):
        """Init."""
        self.crclan_cog = crclan_cog
        self.server = server
        self._user_list = None

    @property
    def user_list(self):
        """Create multiple DiscordUser from a list of tags.

        players format:
        '99688854348369920': '22Q0VGUP'
        discord_member_id: CR player tag
        """
        if self._user_list is None:
            players = self.crclan_cog.manager.get_players(self.server)
            out = []
            for member_id, player_tag in players.items():
                user = self.server.get_member(member_id)
                if user is not None:
                    out.append(DiscordUser(user=user, tag=player_tag))
            self._user_list = out
        return self._user_list

    def tag_to_member(self, tag):
        """Return Discord member from tag."""
        for u in self.user_list:
            if u.tag == tag:
                return u.user
        return None

    def tag_to_member_id(self, tag):
        """Return Discord member from tag."""
        for u in self.user_list:
            if u.tag == tag:
                return u.user
        return None


class MemberAudit:
    """Member audit object associates API model with discord model."""

    def __init__(self, member_model, server, clans):
        self.member_model = member_model
        self.server = server
        self.clans = clans

    @property
    def discord_member(self):
        return self.member_model.discord_member

    @property
    def has_discord(self):
        return self.discord_member is not None

    @property
    def api_clan_name(self):
        return self.member_model.clan_name

    @property
    def api_is_member(self):
        return self.member_model.role_is_member

    @property
    def api_is_elder(self):
        return self.member_model.role_is_elder

    @property
    def api_is_coleader(self):
        return self.member_model.role_is_coleader

    @property
    def api_is_leader(self):
        return self.member_model.role_is_leader

    @property
    def discord_role_member(self):
        return member_has_role(self.server, self.discord_member, "Member")

    @property
    def discord_role_elder(self):
        return member_has_role(self.server, self.discord_member, "Elder")

    @property
    def discord_role_coleader(self):
        return member_has_role(self.server, self.discord_member, "Co-Leader")

    @property
    def discord_role_leader(self):
        return member_has_role(self.server, self.discord_member, "Leader")

    @property
    def discord_clan_roles(self):
        if self.discord_member is None:
            return []
        return [c.role for c in self.clans if c.role in self.discord_member.roles]


class RACFAudit:
    """RACF Audit.
    
    Requires use of additional cogs for functionality:
    SML-Cogs: cr_api : ClashRoyaleAPI
    SML-Cogs: crclan : CRClan
    SML-Cogs: mm : MemberManagement
    """
    required_cogs = ['cr_api', 'crclan', 'mm']

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

        with open('data/racf_audit/family_config.yaml') as f:
            self.config = yaml.load(f)

    @property
    def api(self):
        """CR API cog."""
        return self.bot.get_cog("ClashRoyaleAPI")

    @property
    def crclan(self):
        """CRClan cog."""
        return self.bot.get_cog("CRClan")

    async def family_clan_models(self, server):
        """All family clan models."""
        clans = self.clans(server)
        clan_models = await self.api.clan_models([clan.tag for clan in clans])
        for clan_model in clan_models:
            for clan in clans:
                if clan.tag == clan_model.tag:
                    clan.model = clan_model
        return clan_models

    async def family_member_models(self, server):
        """All family member models."""
        clan_models = await self.family_clan_models(server)
        members = []
        for clan_model in clan_models:
            for member_model in clan_model.members:
                members.append(member_model)
        return members

    def clan_tags(self, membership_type=None):
        """RACF clans."""
        tags = []
        for clan in self.config['clans']:
            if membership_type is None:
                tags.append(clan['tag'])
            elif membership_type == clan['type']:
                tags.append(clan['tag'])
        return tags

    def clans(self, server):
        """List of RACFClan objects based on config."""
        out = []
        for clan in self.config['clans']:
            out.append(
                RACFClan(
                    name=clan['name'],
                    tag=clan['tag'],
                    role=server_role(server, clan['role_name']),
                    membership_type=clan['type']
                )
            )
        return out

    def clan_roles(self, server):
        """Clan roles."""
        return [clan.role for clan in self.clans(server)]

    def clan_name_to_role(self, server, clan_name):
        """Return Discord Role object by clan name."""
        for clan in self.clans(server):
            if clan.name == clan_name:
                return clan.role
        return None

    def check_cogs(self):
        """Check required cogs are loaded."""
        for cog in self.required_cogs:
            if self.bot.get_cog(cog) is None:
                return False
        return True

    @commands.group(aliases=["racfas"], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfauditset(self, ctx):
        """RACF Audit Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    async def update_server_settings(self, ctx, key, value):
        """Set server settings."""
        server = ctx.message.server
        self.settings[server.id][key] = value
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Updated settings.")

    @racfauditset.command(name="leader", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def racfauditset_leader(self, ctx, role_name):
        """Leader role name."""
        await self.update_server_settings(ctx, "leader", role_name)

    @racfauditset.command(name="coleader", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def racfauditset_coleader(self, ctx, role_name):
        """Elder role name."""
        await self.update_server_settings(ctx, "coleader", role_name)

    @racfauditset.command(name="elder", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def racfauditset_elder(self, ctx, role_name):
        """Elder role name."""
        await self.update_server_settings(ctx, "elder", role_name)

    @racfauditset.command(name="member", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def racfauditset_member(self, ctx, role_name):
        """Elder role name."""
        await self.update_server_settings(ctx, "member", role_name)

    @commands.group(aliases=["racfa"], pass_context=True, no_pm=True)
    async def racfaudit(self, ctx):
        """RACF Audit."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @racfaudit.command(name="config", pass_context=True, no_pm=True)
    async def racfaudit_config(self, ctx):
        """Show config."""
        for page in pagify(box(tabulate(self.config['clans'], headers="keys"))):
            await self.bot.say(page)

    def search_args_parser(self):
        """Search arguments parser."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]racfaudit search')

        parser.add_argument(
            'name',
            nargs=1,
            default='_',
            help='IGN')

        parser.add_argument(
            '-t', '--tag',
            nargs=1,
            help='Tag')

        return parser

    @racfaudit.command(name="search", pass_context=True, no_pm=True)
    async def racfaudit_search(self, ctx, *args):
        """Search for member.

        usage: [p]racfaudit search [-h] [-t TAG] name

        positional arguments:
          name               IGN

        optional arguments:
          -h, --help         show this help message and exit
          -t TAG, --tag TAG  Tag
        """
        parser = self.search_args_parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        results = []
        await self.bot.type()
        member_models = await self.family_member_models(server)
        for member_model in member_models:
            if pargs.name is not None:
                s = unidecode.unidecode(member_model.name)
                s = ''.join(re.findall(r'\w', s))
                if pargs.name[0].lower() in s.lower():
                    results.append(member_model)
            if pargs.tag is not None:
                if pargs.tag[0].lower() in member_model.tag.lower():
                    results.append(member_model)

        limit = 10
        if len(results) > 10:
            await self.bot.say(
                "Found more than {0} results. Returning top {0} only.".format(limit)
            )
            results = results[:limit]

        if len(results):
            out = []
            for member_model in results:
                out.append("**{0.name}** #{0.tag}, {0.clan_name}, {0.role_name}".format(member_model))
            for page in pagify('\n'.join(out)):
                await self.bot.say(page)
        else:
            await self.bot.say("No results found.")

    @racfaudit.command(name="run", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_run(self, ctx, *, options=''):
        """Audit the entire RACF family.
        
        Options:
        --removerole   Remove clan role from people who aren’t in clan
        --addrole      Add clan role to people who are in clan
        --exec         Run both add and remove role options
        --debug        Show debug in console 
        """
        server = ctx.message.server
        family_tags = self.crclan.manager.get_clans(server).keys()

        option_exec = '--exec' in options
        option_debug = '--debug' in options

        await self.bot.type()

        clans = self.clans(server)

        # Show settings
        await ctx.invoke(self.racfaudit_config)

        # Create list of all discord users with associated tags
        discord_users = DiscordUsers(crclan_cog=self.crclan, server=server)

        # Member models from API
        member_models = await self.family_member_models(server)

        # associate Discord user to member
        for member_model in member_models:
            member_model.discord_member = discord_users.tag_to_member(member_model.tag)

        if option_debug:
            for du in discord_users.user_list:
                print(du.tag, du.user)

        """
        Member processing.
        
        """
        out = []
        for i, member_model in enumerate(member_models):
            if i % 20 == 0:
                await self.bot.type()
            ma = MemberAudit(member_model, server, clans)
            m_out = []
            if ma.has_discord:
                if not ma.api_is_elder and ma.discord_role_elder:
                    m_out.append(":warning: Has Elder role but not promoted in clan.")
                if not ma.api_is_coleader and ma.discord_role_coleader:
                    m_out.append(":warning: Has Co-Leader role but not promoted in clan.")
                clan_role = self.clan_name_to_role(server, member_model.clan_name)
                if clan_role is not None:
                    if clan_role not in ma.discord_clan_roles:
                        m_out.append(":warning: Does not have {}".format(clan_role.name))
            else:
                m_out.append(':x: No Discord')

            if len(m_out):
                out.append(
                    "**{ign}** {clan}\n{status}".format(
                        ign=member_model.name,
                        clan=member_model.clan_name,
                        status='\n'.join(m_out)
                    )
                )

        for page in pagify('\n'.join(out)):
            await self.bot.type()
            await self.bot.say(page)


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
    n = RACFAudit(bot)
    bot.add_cog(n)
