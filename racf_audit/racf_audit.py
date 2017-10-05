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
import yaml
from __main__ import send_cmd_help
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


class RACFClan:
    """RACF Clan."""

    def __init__(self, name=None, tag=None, role=None, membership_type=None, model=None):
        """Init."""
        self.name = name
        self.tag = tag
        self.role = role
        self.membership_type = membership_type
        self.model = model

    async def update_model(self, api):
        """Update model using the API."""
        self.model = await api.clan_model(self.tag)
        if self.model is None:
            return False
        return True

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

    @classmethod
    def create_user(cls, crclan_cog, server, tag):
        """Create single DiscordUser."""
        return DiscordUser(
            user=crclan_cog.manager.tag2member(server, tag),
            tag=tag
        )

    @classmethod
    def create_user_list(cls, crclan_cog, server):
        """Create multiple DiscordUser from a list of tags.
        
        players format:
        '99688854348369920': '22Q0VGUP'
        discord_member_id: CR player tag
        """
        players = crclan_cog.manager.get_players(server)
        return [DiscordUser(user=server.get_member(k), tag=v) for k, v in players.items()]


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

        print(self.config)

    @property
    def api(self):
        """CR API cog."""
        return self.bot.get_cog("ClashRoyaleAPI")

    @property
    def crclan(self):
        """CRClan cog."""
        return self.bot.get_cog("CRClan")

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

    def check_cogs(self):
        """Check required cogs are loaded."""
        for cog in self.required_cogs:
            if self.bot.get_cog(cog) is None:
                return False
        return True

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

    @racfaudit.command(name="run", pass_context=True, no_pm=True)
    async def racfaudit_run(self, ctx, *, options=''):
        """Audit the entire RACF family.
        
        Options:
        --removerole   Remove clan role from people who aren’t in clan
        --addrole      Add clan role to people who are in clan
        --exec         Run both add and remove role options    
        """
        server = ctx.message.server
        family_tags = self.crclan.manager.get_clans(server).keys()

        option_exec = '--exec' in options

        await self.bot.type()

        clans = self.clans(server)
        tags = self.clan_tags()
        await self.bot.say("Family tags: {}".format(",".join(tags)))

        # Add clan model from API
        for clan in clans:
            success = await clan.update_model(self.api)
            if success:
                await self.bot.say(clan.repr)

        # Create list of all discord users with assoicated tags
        discord_users = DiscordUser.create_user_list(self.crclan, server)
        for du in discord_users:
            print(du.tag, du.user)



        #
        #
        # # List of cr_api.CRClanModel
        # clan_models = await self.api.clan_models(family_tags)
        #
        # # - add role to models
        # for c in clan_models:
        #     await self.bot.type()
        #     role = self.crclan.manager.clantag_to_discord_role(server, c.tag)
        #     if role is None:
        #         role = 'No found role.'
        #     c.role = role
        #
        # # - all player models from clan_models
        # # member_models = [m for m in c.members for c in clan_models]
        # member_models = []
        # for c in clan_models:
        #     for m in c.members:
        #         member_models.append(m)
        # await self.bot.say("Total members: {}".format(len(member_models)))
        #
        # members_without_discord = []
        # # - Audit clan roles
        # for c in clan_models:
        #     clan_role = c.role
        #     for m in c.members:
        #         discord_user = self.crclan.manager.tag2member(server, m.tag)
        #         if discord_user is None:
        #             members_without_discord.append(m)
        #             continue
        #         else:
        #             if clan_role not in discord_user.roles:
        #                 await self.bot.say("{} does not have {} but is in clan.".format(
        #                     discord_user, clan_role
        #                 ))


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
