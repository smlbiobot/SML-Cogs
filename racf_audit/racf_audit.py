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
from collections import defaultdict, OrderedDict

import discord
import unidecode
import yaml
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, box, bold
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from tabulate import tabulate
import crapipy
import dateutil.parser
import pprint
import humanize
import datetime as dt
import aiohttp
import json
import asyncio

PATH = os.path.join("data", "racf_audit")
JSON = os.path.join(PATH, "settings.json")
PLAYERS = os.path.join("data", "racf_audit", "players.json")


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

class RACFAuditException(Exception):
    pass

class CachedClanModels(RACFAuditException):
    pass


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

def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    return t

def get_role_name(role):
    if role is None:
        return ''

    role = role.lower()

    roles_dict = {
        'leader': 'Leader',
        'coleader': 'Co-Leader',
        'elder': 'Elder',
        'member': 'Member'
    }

    if role in roles_dict.keys():
        return roles_dict.get(role)

    return ''


class ClashRoyaleAPIError(Exception):
    def __init__(self, status=None, message=None):
        super().__init__()
        self._status = status
        self._message = message

    @property
    def status(self):
        return self._status

    @property
    def message(self):
        return self._message

    @property
    def status_message(self):
        out = []
        if self._status is not None:
            out.append(str(self._status))
        if self._message is not None:
            out.append(self._message)
        return '. '.join(out)

class ClashRoyaleAPI:
    def __init__(self, token):
        self.token = token

    async def fetch_with_session(self, session, url, timeout=30.0):
        """Perform the actual fetch with the session object."""
        headers = {
            'Authorization': 'Bearer {}'.format(self.token)
        }
        async with session.get(url, headers=headers) as resp:
            async with aiohttp.Timeout(timeout):
                body = await resp.json()
                if resp.status != 200:
                    raise ClashRoyaleAPIError(status=resp.status, message=resp.reason)
        return body

    async def fetch(self, url):
        """Fetch request."""
        error_msg = None
        try:
            async with aiohttp.ClientSession() as session:
                body = await self.fetch_with_session(session, url)
        except asyncio.TimeoutError:
            error_msg = 'Request timed out'
            raise ClashRoyaleAPIError(message=error_msg)
        except aiohttp.ServerDisconnectedError as err:
            error_msg = 'Server disconnected error: {}'.format(err)
            raise ClashRoyaleAPIError(message=error_msg)
        except (aiohttp.ClientError, ValueError) as err:
            error_msg = 'Request connection error: {}'.format(err)
            raise ClashRoyaleAPIError(message=error_msg)
        except json.JSONDecodeError:
            error_msg = "Non JSON returned"
            raise ClashRoyaleAPIError(message=error_msg)
        else:
            return body
        finally:
            if error_msg is not None:
                raise ClashRoyaleAPIError(message=error_msg)


    async def fetch_multi(self, urls):
        """Perform parallel fetch"""
        results = []
        error_msg = None
        try:
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    await asyncio.sleep(0)
                    body = await self.fetch_with_session(session, url)
                    results.append(body)
        except asyncio.TimeoutError:
            error_msg = 'Request timed out'
            raise ClashRoyaleAPIError(message=error_msg)
        except aiohttp.ServerDisconnectedError as err:
            error_msg = 'Server disconnected error: {}'.format(err)
            raise ClashRoyaleAPIError(message=error_msg)
        except (aiohttp.ClientError, ValueError) as err:
            error_msg = 'Request connection error: {}'.format(err)
            raise ClashRoyaleAPIError(message=error_msg)
        except json.JSONDecodeError:
            error_msg = "Non JSON returned"
            raise ClashRoyaleAPIError(message=error_msg)
        else:
            return results
        finally:
            if error_msg is not None:
                raise ClashRoyaleAPIError(message=error_msg)

    async def fetch_clan(self, tag):
        """Get a clan."""
        tag = clean_tag(tag)
        url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
        body = await self.fetch(url)
        return body

    async def fetch_clan_list(self, tags):
        """Get multiple clans."""
        tags = [clean_tag(tag) for tag in tags]
        urls = ['https://api.clashroyale.com/v1/clans/%23{}'.format(tag) for tag in tags]
        results = await self.fetch_multi(urls)
        return results






class RACFAudit:
    """RACF Audit.
    
    Requires use of additional cogs for functionality:
    SML-Cogs: crclan : CRClan
    SML-Cogs: mm : MemberManagement
    """
    required_cogs = ['crclan', 'mm']

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

        players_path = os.path.join(PATH, "players.json")
        if not os.path.exists(players_path):
            players_path = os.path.join(PATH, "players_bak.json")
        self.players = dataIO.load_json(players_path)
        dataIO.save_json(PLAYERS, self.players)

        with open('data/racf_audit/family_config.yaml') as f:
            self.config = yaml.load(f)

    @commands.group(aliases=["racfas"], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfauditset(self, ctx):
        """RACF Audit Settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    async def update_server_settings(self, ctx, key, value):
        """Set server settings."""
        server = ctx.message.server
        self.settings[server.id][key] = value
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Updated settings.")

    @racfauditset.command(name="auth", pass_context=True, no_pm=True)
    @checks.is_owner()
    async def racfauditset_auth(self, ctx, token):
        """Set API Authentication token."""
        self.settings["auth"] = token
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Updated settings.")
        await self.bot.delete_message(ctx.message)

    @racfauditset.command(name="settings", pass_context=True, no_pm=True)
    @checks.is_owner()
    async def racfauditset_settings(self, ctx):
        """Set API Authentication token."""
        await self.bot.say(box(self.settings))


    @property
    def auth(self):
        """API authentication token."""
        return self.settings.get("auth")

    @commands.group(aliases=["racfa"], pass_context=True, no_pm=True)
    async def racfaudit(self, ctx):
        """RACF Audit."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @racfaudit.command(name="config", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def racfaudit_config(self, ctx):
        """Show config."""
        for page in pagify(box(tabulate(self.config['clans'], headers="keys"))):
            await self.bot.say(page)

    def clan_tags(self):
        tags = []
        for clan in self.config.get('clans'):
            tags.append(clan.get('tag'))
        return tags

    def search_args_parser(self):
        """Search arguments parser."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]racfaudit search')

        parser.add_argument(
            'name',
            nargs='?',
            default='_',
            help='IGN')
        parser.add_argument(
            '-c', '--clan',
            nargs='?',
            help='Clan')
        parser.add_argument(
            '-n', '--min',
            nargs='?',
            type=int,
            default=0,
            help='Min Trophies')
        parser.add_argument(
            '-m', '--max',
            nargs='?',
            type=int,
            default=10000,
            help='Max Trophies')
        parser.add_argument(
            '-l', '--link',
            action='store_true',
            default=False
        )

        return parser

    async def family_member_models(self):
        """All family member models."""
        try:
            api = ClashRoyaleAPI(self.auth)
            tags = self.clan_tags()
            clan_models = await api.fetch_clan_list(tags)
        except ClashRoyaleAPIError as e:
            pass
        else:
            members = []
            for clan_model in clan_models:
                for member_model in clan_model.get('memberList'):
                    member_model['tag'] = clean_tag(member_model.get('tag'))
                    member_model['clan'] = clan_model
                    members.append(member_model)
            return members

    @racfaudit.command(name="search", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_search(self, ctx, *args):
        """Search for member.

        usage: [p]racfaudit search [-h] [-t TAG] name

        positional arguments:
          name                  IGN

        optional arguments:
          -h, --help            show this help message and exit
          -c CLAN, --clan CLAN  Clan name
          -n MIN --min MIN      Min Trophies
          -m MAX --max MAX      Max Trophies
          -l --link             Display link to cr-api.com
        """
        parser = self.search_args_parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        results = []
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        if pargs.name != '_':
            for member_model in member_models:
                # simple search
                if pargs.name.lower() in member_model.get('name').lower():
                    results.append(member_model)
                else:
                    # unidecode search
                    s = unidecode.unidecode(member_model.get('name'))
                    s = ''.join(re.findall(r'\w', s))
                    if pargs.name.lower() in s.lower():
                        results.append(member_model)
        else:
            results = member_models

        # filter by clan name
        if pargs.clan:
            results = [m for m in results if pargs.clan.lower() in m.get('clan_name').lower()]

        # filter by trophies
        results = [m for m in results if pargs.min <= m.get('trophies') <= pargs.max]

        limit = 10
        if len(results) > limit:
            await self.bot.say(
                "Found more than {0} results. Returning top {0} only.".format(limit)
            )
            results = results[:limit]

        if len(results):
            out = []
            for member_model in results:
                clan = member_model.get('clan')
                clan_name = None
                if clan is not None:
                    clan_name = clan.get('name')

                out.append("**{name}** #{tag}, {clan_name}, {role}, {trophies}".format(
                    name=member_model.get('name'),
                    tag=member_model.get('tag'),
                    clan_name=clan_name,
                    role=get_role_name(member_model.get('role')),
                    trophies=member_model.get('trophies')
                ))
                if pargs.link:
                    out.append('http://cr-api.com/player/{}'.format(member_model.get('tag')))
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
        option_debug = '--debug' in options
        option_addrole = '--addrole' in options
        option_removerole = '--removerole' in options
        option_exec = '--exec' in options

        results = []
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        # Show settings
        await ctx.invoke(self.racfaudit_config)

        # Create list of all discord users with associated tags
        discord_users = DiscordUsers(crclan_cog=self.bot.get_cog('CRClan'), server=ctx.message.server)

        # associate Discord user to member
        for member_model in member_models:
            member_model['discord_member'] = discord_users.tag_to_member(member_model.get('tag'))

        if option_debug:
            for du in discord_users.user_list:
                print(du.tag, du.user)

        """
        Member processing.

        """
        # clan_defaults = {
        #     "elder_promotion_req": [],
        #     "coleader_promotion_req": [],
        #     "no_discord": [],
        #     "no_clan_role": []
        # }
        # clans_out = OrderedDict([(c.name, clan_defaults) for c in clans])
        #
        # def update_clan(clan_name, field, member_model):
        #     clans_out[clan_name][field].append(member_model)
        #
        # out = []
        # for i, member_model in enumerate(member_models):
        #     if i % 20 == 0:
        #         await self.bot.type()
        #
        #     ma = MemberAudit(member_model, server, clans)
        #     clan_name = member_model.clan_name
        #     m_out = []
        #     if ma.has_discord:
        #         if not ma.api_is_elder and ma.discord_role_elder:
        #             update_clan(clan_name, "elder_promotion_req", member_model)
        #             m_out.append(":warning: Has Elder role but not promoted in clan.")
        #         if not ma.api_is_coleader and ma.discord_role_coleader:
        #             update_clan(clan_name, "coleader_promotion_req", member_model)
        #             m_out.append(":warning: Has Co-Leader role but not promoted in clan.")
        #         clan_role = self.clan_name_to_role(server, member_model.clan_name)
        #         if clan_role is not None:
        #             if clan_role not in ma.discord_clan_roles:
        #                 update_clan(clan_name, "no_clan_role", member_model)
        #                 m_out.append(":warning: Does not have {}".format(clan_role.name))
        #     else:
        #         update_clan(clan_name, "no_discord", member_model)
        #         m_out.append(':x: No Discord')
        #
        #     if len(m_out):
        #         out.append(
        #             "**{ign}** {clan}\n{status}".format(
        #                 ign=member_model.name,
        #                 clan=member_model.clan_name,
        #                 status='\n'.join(m_out)
        #             )
        #         )
        #
        # # line based output
        # for page in pagify('\n'.join(out)):
        #     await self.bot.type()
        #     await self.bot.say(page)
        #
        # # clan based output
        # out = []
        # print(clans_out)
        # for clan_name, clan_dict in clans_out.items():
        #     out.append("**{}**".format(clan_name))
        #     if len(clan_dict["elder_promotion_req"]):
        #         out.append("Elders that need to be promoted:")
        #         out.append(", ".join([m.name for m in clan_dict["elder_promotion_req"]]))
        #     if len(clan_dict["no_discord"]):
        #         out.append("No Discord:")
        #         out.append(", ".join([m.name for m in clan_dict["no_discord"]]))
        #     if len(clan_dict["no_clan_role"]):
        #         out.append("No clan role on Discord:")
        #         out.append(", ".join([m.name for m in clan_dict["no_clan_role"]]))
        #
        # for page in pagify('\n'.join(out), shorten_by=24):
        #     await self.bot.type()
        #     if len(page):
        #         await self.bot.say(page)


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)
    os.makedirs(os.path.join(PATH, "clans"), exist_ok=True)


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
