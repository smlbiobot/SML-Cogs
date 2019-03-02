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
import itertools
from collections import OrderedDict
from collections import defaultdict
from collections import namedtuple

import aiohttp
import argparse
import csv
import datetime as dt
import discord
import humanfriendly
import io
import json
import os
import re
import unidecode
import yaml
from addict import Dict
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import inline
from cogs.utils.chat_formatting import pagify
from cogs.utils.chat_formatting import underline
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from tabulate import tabulate

PATH = os.path.join("data", "racf_audit")
JSON = os.path.join(PATH, "settings.json")

PLAYERS = os.path.join("data", "racf_audit", "player_db.json")

# RACF_SERVER_ID = '218534373169954816'
RACF_SERVER_ID = '528327242875535372'
SML_SERVER_ID = '275395656955330560'

MEMBER_ROLE_NAMES = [
    'Member',
    'Touney',
    'Practice',
    'CW',
    'Diary',
    'Alpha',
    'Bravo',
    'Coca',
    'Delta',
    'Echo',
    'Fox',
    'Golf',
    'Trade',
    'Zen',
    'Mini',
]


class NoPlayerRecord(Exception):
    pass


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


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


async def check_manage_roles(ctx, bot):
    """Check for permissions to run command since no one has manage roles anymore."""
    server = ctx.message.server
    author = ctx.message.author
    channel = ctx.message.channel
    # For 100T server, only allow command to run if user has the "Bot Comamnder" role
    if server.id == RACF_SERVER_ID:
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


class RACFAuditException(Exception):
    pass


class CachedClanModels(RACFAuditException):
    pass


AuditResult = namedtuple("AuditResult", "audit_results output error")


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
    t = tag.upper()
    t = t.replace('B', '8').replace('O', '0')
    t = re.sub(r'[^0289CGJLPQRUVY]+', '', t)
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
        tasks = [self.fetch_clan(tag) for tag in tags]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for index, r in enumerate(results):
            if isinstance(r, ClashRoyaleAPIError):
                print(r.status_message)
                results[index] = {}
        return results

    async def fetch_clan_leaderboard(self, location=None):
        """Get clan leaderboard"""
        url = 'https://api.clashroyale.com/v1/locations/global/rankings/clans'
        body = await self.fetch(url)
        return body

    async def fetch_clan_war(self, tag=None):
        url = 'https://api.clashroyale.com/v1/clans/%23{}/currentwar'.format(tag)
        body = await self.fetch(url)
        return body


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
        self._clan_roles = None

        players_path = PLAYERS

        if not os.path.exists(players_path):
            players_path = os.path.join(PATH, "player_db_bak.json")

        self._players = dataIO.load_json(players_path)
        dataIO.save_json(PLAYERS, self._players)

        with open('data/racf_audit/family_config.yaml') as f:
            self.config = yaml.load(f)

    @property
    def players(self):
        """Player dictionary, userid -> tag"""
        return self._players
        # players = dataIO.load_json(PLAYERS)
        # return players

    @commands.group(aliases=["racfas"], pass_context=True, no_pm=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racfauditset(self, ctx):
        """RACF Audit Settings."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    async def update_server_settings(self, ctx, key, value):
        """Set server settings."""
        server = ctx.message.server
        self.settings[server.id][key] = value
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Updated settings.")

    async def set_player_tag(self, tag, member: discord.Member, force=False):
        """Allow external programs to set player tags. (RACF)"""
        await asyncio.sleep(0)
        players = self.players
        # clean tags
        tag = clean_tag(tag)

        # ensure unique tag
        tag_in_db = False
        if tag in players.keys():
            tag_in_db = True
            if not force:
                return False

        # ensure unique user ids
        user_id_in_db = False
        for k, v in players.items():
            if v.get('user_id') == member.id:
                user_id_in_db = True
                if not force:
                    return False

        # if force override, remove the entries
        if tag_in_db:
            players.pop(tag, None)

        if user_id_in_db:
            _ks = None
            for k, v in players.items():
                if v.get('user_id') == member.id:
                    if _ks is None:
                        _ks = []
                    _ks.append(k)
            if _ks is not None:
                for k in _ks:
                    players.pop(k, None)

        players[tag] = {
            "tag": tag,
            "user_id": member.id,
            "user_name": member.display_name
        }
        dataIO.save_json(PLAYERS, players)
        return True

    async def get_player_tag(self, tag):
        await asyncio.sleep(0)
        return self.players.get(tag)

    async def rm_player_tag(self, tag):
        """Remove player tag from settings."""
        pass

    @racfauditset.command(name="auth", pass_context=True)
    @checks.is_owner()
    async def racfauditset_auth(self, ctx, token):
        """Set API Authentication token."""
        self.settings["auth"] = token
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Updated settings.")
        await self.bot.delete_message(ctx.message)

    @racfauditset.command(name="settings", pass_context=True)
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
            # only clans with member roles
            if clan.get('type') == 'Member':
                tags.append(clan.get('tag'))
        return tags

    @property
    def clan_roles(self):
        """Dictionary mapping clan name to clan role names"""
        if self._clan_roles is None:
            self._clan_roles = {}
            for clan in self.config.get('clans'):
                if clan['type'] == 'Member':
                    self._clan_roles[clan['name']] = clan['role_name']
        return self._clan_roles

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

    @property
    def api(self):
        return ClashRoyaleAPI(self.auth)

    async def family_member_models(self):
        """All family member models."""
        api = ClashRoyaleAPI(self.auth)
        tags = self.clan_tags()
        clan_models = await api.fetch_clan_list(tags)
        print(clan_models)
        members = []
        for clan_model in clan_models:
            for member_model in clan_model.get('memberList'):
                member_model['tag'] = clean_tag(member_model.get('tag'))
                member_model['clan'] = clan_model
                members.append(member_model)
        return members

    @racfaudit.command(name="tag2member", pass_context=True, aliases=['t2m'])
    async def racfaudit_tag2member(self, ctx, tag):
        """Find member by tag in DB."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        tag = clean_tag(tag)
        user_id = None
        for _key, m in self.players.items():
            m_tag = m.get('tag')
            if m_tag is not None and m_tag == tag:
                user_id = m['user_id']
                break

        if user_id is None:
            await self.bot.say("Member not found.")
        else:
            server = ctx.message.server
            member = server.get_member(user_id)
            await self.bot.say("{} ({}) is associated with #{}".format(
                member.mention if member is not None else 'Unknown user',
                user_id, tag)
            )

    @racfaudit.command(name="tag", pass_context=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_tag(self, ctx, member: discord.Member):
        """Find member tag in DB."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        found = False
        for tag, m in self.players.items():
            if m["user_id"] == member.id:
                await self.bot.say("RACF Audit database: `{}` is associated to `#{}`".format(member, tag))
                found = True

        if not found:
            await self.bot.say("RACF Audit database: Member is not associated with any tags.")

    @racfaudit.command(name="rmtag", pass_context=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_rm_tag(self, ctx, tag):
        """Remove tag in DB."""
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        tag = clean_tag(tag)
        try:
            self.players.pop(tag, None)
        except KeyError:
            await self.bot.say("Tag not found in DB.")
        else:
            dataIO.save_json(PLAYERS, self.players)
            await self.bot.say("Removed tag from DB.")

    @racfaudit.command(name="search", pass_context=True, no_pm=True)
    # @checks.mod_or_permissions(manage_roles=True)
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
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

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
            results = [m for m in results if pargs.clan.lower() in m.get('clan', {}).get('name', '').lower()]

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
                    trophies=member_model.get('trophies'),
                ))
                if pargs.link:
                    out.append('<http://royaleapi.com/player/{}>'.format(member_model.get('tag')))
                    out.append('<http://royaleapi.com/player/{}/battles>'.format(member_model.get('tag')))
            for page in pagify('\n'.join(out)):
                await self.bot.say(page)
        else:
            await self.bot.say("No results found.")

    def run_args_parser(self):
        """Search arguments parser."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]racfaudit run')

        parser.add_argument(
            '-x', '--exec',
            action='store_true',
            default=False,
            help='Execute add/remove roles')
        parser.add_argument(
            '-d', '--debug',
            action='store_true',
            default=False,
            help='Debug')
        parser.add_argument(
            '-c', '--clan',
            nargs='+',
            help='Clan(s) to show')
        parser.add_argument(
            '-s', '--settings',
            action='store_true',
            default=False,
            help='Settings')

        return parser

    @racfaudit.command(name="run", pass_context=True, no_pm=True)
    # @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_run(self, ctx, *args):
        """Audit the entire RACF family.

        [p]racfaudit run [-h] [-x] [-d] [-c CLAN [CLAN ...]]

        optional arguments:
          -h, --help            show this help message and exit
          -x, --exec            Execute add/remove roles
          -d, --debug           Debug
          -c CLAN [CLAN ...], --clan CLAN [CLAN ...]
                                Clan(s) to show
        """
        verified = await check_manage_roles(ctx, self.bot)
        if not verified:
            return

        server = ctx.message.server

        parser = self.run_args_parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        # Show settings
        if pargs.settings:
            await ctx.invoke(self.racfaudit_config)

        await self.bot.type()

        clan_filters = []
        if pargs.clan:
            clan_filters = pargs.clan

        result = await self.run_racfaudit(server, clan_filters=clan_filters)

        for page in pagify('\n'.join(result.output)):
            await self.bot.say(page)

        if pargs.exec:
            channel = ctx.message.channel
            await self.bot.type()
            await self.exec_racf_audit(channel=channel, audit_results=result.audit_results, server=server)

        await self.bot.say("Audit finished.")

    async def run_racfaudit(self, server: discord.Server, clan_filters=None) -> AuditResult:
        """Run audit and return results."""
        audit_results = {
            "elder_promotion_req": [],
            "coleader_promotion_req": [],
            "leader_promotion_req": [],
            "no_discord": [],
            "no_clan_role": [],
            "no_member_role": [],
            "not_in_our_clans": [],
        }

        error = False
        out = []

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            # await self.bot.say(e.status_message)
            error = True
        else:
            out.append("**RACF Family Audit**")

            # associate Discord user to member
            for member_model in member_models:
                tag = clean_tag(member_model.get('tag'))
                try:
                    discord_id = self.players[tag]["user_id"]
                except KeyError:
                    pass
                else:
                    member_model['discord_member'] = server.get_member(discord_id)

            # find member_models mismatch
            discord_members = []
            for member_model in member_models:
                has_discord = member_model.get('discord_member')
                if has_discord is None:
                    audit_results["no_discord"].append(member_model)

                if has_discord:
                    discord_member = member_model.get('discord_member')
                    discord_members.append(discord_member)
                    # promotions
                    is_elder = False
                    is_coleader = False
                    is_leader = False
                    for r in discord_member.roles:
                        if r.name.lower() == 'elder':
                            is_elder = True
                        if r.name.lower() == 'coleader':
                            is_coleader = True
                        if r.name.lower() == 'leader':
                            is_leader = True
                    if is_elder:
                        if member_model.get('role').lower() != 'elder':
                            audit_results["elder_promotion_req"].append(member_model)
                    if is_coleader:
                        if member_model.get('role').lower() != 'coleader':
                            audit_results["coleader_promotion_req"].append(member_model)
                    if is_leader:
                        if member_model.get('role').lower() != 'leader':
                            audit_results["leader_promotion_req"].append(member_model)

                    # no clan role
                    clan_name = member_model['clan']['name']
                    clan_role_name = self.clan_roles[clan_name]
                    if clan_role_name not in [r.name for r in discord_member.roles]:
                        audit_results["no_clan_role"].append({
                            "discord_member": discord_member,
                            "member_model": member_model
                        })

                    # no member role
                    discord_role_names = [r.name for r in discord_member.roles]
                    if 'Member' not in discord_role_names:
                        audit_results["no_member_role"].append(discord_member)

            # find discord member with roles
            for user in server.members:
                user_roles = [r.name for r in user.roles]
                if 'Member' in user_roles:
                    if user not in discord_members:
                        audit_results['not_in_our_clans'].append(user)

            # show results
            def list_member(member_model):
                """member row"""
                clan = member_model.get('clan')
                clan_name = None
                if clan is not None:
                    clan_name = clan.get('name')

                row = "**{name}** #{tag}, {clan_name}, {role}, {trophies}".format(
                    name=member_model.get('name'),
                    tag=member_model.get('tag'),
                    clan_name=clan_name,
                    role=get_role_name(member_model.get('role')),
                    trophies=member_model.get('trophies')
                )
                return row

            for clan in self.config['clans']:
                # await self.bot.type()
                await asyncio.sleep(0)

                display_output = False

                if clan_filters:
                    for c in clan_filters:
                        if c.lower() in [f.lower() for f in clan.get('filters', [])]:
                            display_output = True
                else:
                    display_output = True

                if not display_output:
                    continue

                if clan['type'] == 'Member':
                    out.append("-" * 40)
                    out.append(inline(clan.get('name')))
                    # no discord
                    out.append(underline("Members without discord"))
                    for member_model in audit_results["no_discord"]:
                        try:
                            if member_model['clan']['name'] == clan.get('name'):
                                out.append(list_member(member_model))
                        except KeyError:
                            pass
                    # elders
                    out.append(underline("Elders need promotion"))
                    for member_model in audit_results["elder_promotion_req"]:
                        try:
                            if member_model['clan']['name'] == clan.get('name'):
                                out.append(list_member(member_model))
                        except KeyError:
                            pass
                    # coleaders
                    out.append(underline("Co-Leaders need promotion"))
                    for member_model in audit_results["coleader_promotion_req"]:
                        try:
                            if member_model['clan']['name'] == clan.get('name'):
                                out.append(list_member(member_model))
                        except KeyError:
                            pass
                    # clan role
                    out.append(underline("No clan role"))
                    for result in audit_results["no_clan_role"]:
                        try:
                            if result["member_model"]['clan']['name'] == clan.get('name'):
                                out.append(result['discord_member'].mention)
                        except KeyError:
                            pass

            # not in our clans
            out.append("-" * 40)
            out.append(underline("Discord users not in our clans but with member roles"))
            for result in audit_results['not_in_our_clans']:
                out.append('`{}` {}'.format(result, result.id))

        return AuditResult(
            audit_results=audit_results,
            output=out,
            error=error
        )

    async def exec_racf_audit(self, channel: discord.Channel = None, audit_results=None, server=None):
        """Execute audit and output to specific channel."""

        await self.bot.send_message(channel, "**RACF Family Audit**")
        await self.bot.send_typing(channel)

        async def exec_add_roles(d_member, roles, channel=None):
            # print("add roles", d_member, [r.name for r in roles])
            # await asyncio.sleep(0)
            await self.bot.add_roles(d_member, *roles)
            if channel is not None:
                await self.bot.send_message(channel,
                                            "Add {} to {}".format(", ".join([r.name for r in roles]), d_member))

        async def exec_remove_roles(d_member, roles, channel=None):
            # print("remove roles", d_member, [r.name for r in roles])
            # await asyncio.sleep(0)
            await self.bot.remove_roles(d_member, *roles)
            if channel is not None:
                await self.bot.send_message(channel,
                                            "Remove {} from {}".format(", ".join([r.name for r in roles]),
                                                                       d_member))

        # change clan roles
        for result in audit_results["no_clan_role"]:
            try:
                member_model = result['member_model']
                discord_member = result['discord_member']
                clan_role_name = self.clan_roles[member_model['clan']['name']]
                other_clan_role_names = [r for r in self.clan_roles.values() if r != clan_role_name]
                for rname in other_clan_role_names:
                    role = discord.utils.get(discord_member.roles, name=rname)
                    if role is not None:
                        await exec_remove_roles(discord_member, [role], channel=channel)

                role = discord.utils.get(server.roles, name=clan_role_name)
                if role is not None:
                    await exec_add_roles(discord_member, [role], channel=channel)
            except KeyError:
                pass

        member_role = discord.utils.get(server.roles, name='Member')
        visitor_role = discord.utils.get(server.roles, name='Visitor')
        for discord_member in audit_results["no_member_role"]:
            try:
                if member_role is not None:
                    await exec_add_roles(discord_member, [member_role], channel=channel)

                if visitor_role is not None:
                    await exec_remove_roles(discord_member, [visitor_role], channel=channel)

            except KeyError:
                pass

        # remove member roles from people who are not in our clans
        for result in audit_results['not_in_our_clans']:
            result_role_names = [r.name for r in result.roles]
            # ignore people with special
            if 'Special' in result_role_names:
                continue
            if 'Keep-Member' in result_role_names:
                continue
            if 'Leader-Emeritus' in result_role_names:
                continue

            to_remove_role_names = []
            for role_name in MEMBER_ROLE_NAMES:
                if role_name in result_role_names:
                    to_remove_role_names.append(role_name)
            to_remove_roles = [discord.utils.get(server.roles, name=rname) for rname in to_remove_role_names]
            to_remove_roles = [r for r in to_remove_roles if r is not None]
            if len(to_remove_roles):
                await exec_remove_roles(result, to_remove_roles, channel=channel)
            if visitor_role is not None:
                await exec_add_roles(result, [visitor_role], channel=channel)

        # Remove clan roles from visitors
        member_role = discord.utils.get(server.roles, name='Member')
        for user in server.members:
            # not a member
            if member_role not in user.roles:
                user_role_names = [r.name for r in user.roles]
                user_member_role_names = set(user_role_names) & set(MEMBER_ROLE_NAMES)
                # union of user roles with member role names -> user has member roles which need to be removed
                if user_member_role_names:
                    to_remove_roles = [discord.utils.get(server.roles, name=rname) for rname in user_member_role_names]
                    to_remove_roles = [r for r in to_remove_roles if r is not None]
                    if to_remove_roles:
                        await exec_remove_roles(user, to_remove_roles, channel=channel)

        await self.bot.send_message(channel, "Audit finished.")

    async def search_player(self, tag=None, user_id=None):
        """Search for players.

        Return player dict
        {'tag': '200CYRVCU', 'user_id': '295317904633757696', 'user_name': 'Ryann'}
        """
        if tag is not None:
            for key, player in self.players.items():
                if player.get('tag') == tag:
                    return player

        if user_id is not None:
            for key, player in self.players.items():
                if player.get('user_id') == user_id:
                    return player

        return None

    @racfaudit.command(name="audit", pass_context=True)
    async def audit_member(self, ctx, member: discord.Member):
        """Run audit against specific user."""
        try:
            player = await self.search_player(user_id=member.id)
            if player is None:
                raise NoPlayerRecord()
            tag = player.get('tag')
            if tag is None:
                raise NoPlayerRecord()
        except NoPlayerRecord as e:
            await self.bot.say("Your tag is not set. Please ask a Co-Leader for help.")
            return

        racf = self.bot.get_cog("RACF")
        await ctx.invoke(racf.racf_verify, member, tag)

    @commands.command(name="auditme", pass_context=True)
    async def audit_self(self, ctx):
        """Run audit against self."""
        author = ctx.message.author
        try:
            player = await self.search_player(user_id=author.id)
            if player is None:
                raise NoPlayerRecord()
            tag = player.get('tag')
            if tag is None:
                raise NoPlayerRecord()
        except NoPlayerRecord as e:
            await self.bot.say("Your tag is not set. Please ask a Co-Leader for help.")
            return

        racf = self.bot.get_cog("RACF")
        await ctx.invoke(racf.racf_verify, author, tag, grant_permission=True)

    @racfaudit.command(name="rank", pass_context=True)
    async def racfaudit_rank(self, ctx, *names):
        """Look up member rank within the family.

        Options:
        -startswith search names from the start only
        """
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        results = []

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)

        option_startwith = '-startswith' in names

        if option_startwith:
            names = list(names)
            names.remove('-startswith')

        for index, member_model in enumerate(member_models, 1):
            # simple search
            for name in names:
                add_it = False
                if name.lower() in member_model.get('name').lower():
                    if option_startwith:
                        if member_model.get('name').lower().startswith(name):
                            add_it = True
                    else:
                        add_it = True
                else:
                    # unidecode search
                    s = unidecode.unidecode(member_model.get('name'))
                    s = ''.join(re.findall(r'\w', s))
                    if name.lower() in s.lower():
                        add_it = True
                if add_it:
                    results.append({
                        'index': index,
                        'member': member_model
                    })

        out = []

        limit = 20

        if len(results) > limit:
            await self.bot.say("More than {0} results found, showing top {0}…".format(limit))
            results = results[:limit]

        for result in results:
            index = result['index']
            member = result['member']
            out.append('{:<4} {:>4} {}'.format(
                index, member['trophies'], member['name']
            ))

        await self.bot.say(
            box('\n'.join(out), lang='python')
        )

    @commands.command(name="racfaudit_top", aliases=["rtop"], pass_context=True)
    async def racfaudit_top(self, ctx, count: int):
        """Show top N members in family."""
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        author = ctx.message.author
        if not author.server_permissions.manage_roles:
            count = min(count, 10)

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)
        results = member_models[:count]

        out = []

        def name_to_symbol(name):
            s = name[10:]
            if not s:
                s = 'M'
            return s

        for index, member in enumerate(results, 1):
            out.append('{:<4} {:>4} {:<5} {}'.format(
                index, member['trophies'], name_to_symbol(member['clan']['name']), member['name']
            ))

        for page in pagify('\n'.join(out)):
            await self.bot.say(box(page, lang='py'))

    @racfaudit.command(name="csv", pass_context=True)
    async def racfaudit_csv(self, ctx):
        """Output membership in CSV format."""
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        filename = "members-{:%Y%m%d-%H%M%S}.csv".format(dt.datetime.utcnow())

        tmp_file = os.path.join("data", "racf_audit", "member_csv.csv")

        fieldnames = [
            'name',
            'tag',
            'role',
            'expLevel',
            'trophies',
            'clan_tag',
            'clan_name',
            'clanRank',
            'previousClanRank',
            'donations',
            'donationsReceived',
        ]

        members = []
        for model in member_models:
            member = {k: v for k, v in model.items() if k in fieldnames}
            member['clan_tag'] = clean_tag(model.get('clan', {}).get('tag', ''))
            member['clan_name'] = model.get('clan', {}).get('name', '')
            member['tag'] = clean_tag(model.get('tag', ''))
            members.append(member)

        channel = ctx.message.channel
        with io.StringIO() as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for member in members:
                writer.writerow(member)

            s = f.getvalue()

            with io.BytesIO(s.encode()) as fb:
                await self.bot.send_file(
                    channel, fb, filename=filename)

    def calculate_clan_trophies(self, trophies):
        """Add a list of trophies to be calculated."""
        trophies = sorted(trophies, reverse=True)
        total = 0
        factors = OrderedDict({
            10: 0.5,
            20: 0.25,
            30: 0.12,
            40: 0.1,
            50: 0.03
        })
        for index, t in enumerate(trophies, 1):
            factor_list = [f for f in factors.keys() if index <= f]
            if len(factor_list) > 0:
                factor = min(factor_list)
                total += t * factors[factor]

        return int(total)

    @racfaudit.command(name="season", pass_context=True)
    async def racfaudit_season(self, ctx, *args):
        """Find top 50 RACF not in Alpha."""
        await self.bot.type()
        server = ctx.message.server
        author = ctx.message.author

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        top50_results = []
        non_top50_results = []

        ALPHA_CLAN_TAG = '#9PJ82CRC'
        # ALPHA_CLAN_TAG = '#PV98LY0P'

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)

        alpha_trophies = [m.get('trophies') for m in member_models if m.get('clan', {}).get('tag') == ALPHA_CLAN_TAG]
        alpha_clan_trophies = self.calculate_clan_trophies(alpha_trophies)
        top50_trophies = [m.get('trophies') for m in member_models[:50]]
        top50_clan_trophies = self.calculate_clan_trophies(top50_trophies)
        trophy_50 = int(member_models[49].get('trophies', 0))

        # Find alpha rank if top 50 in alpha
        api = ClashRoyaleAPI(self.auth)
        alpha_global_rank = 0
        possible_alpha_rank = 0
        ranks = []
        try:
            lb = await api.fetch_clan_leaderboard()
        except ClashRoyaleAPIError as e:
            await self.bot.say("Error: {}".format(e.message))
        else:
            items = lb.get('items', [])
            for item in items:
                if item.get('tag') == ALPHA_CLAN_TAG:
                    alpha_global_rank = item.get('rank')
            clan_scores = [item.get('clanScore') for item in items]

            possible_alpha_rank = len([score for score in clan_scores if score > top50_clan_trophies])

        # Summary
        o_summary = [
            '50th = {:,} :trophy: '.format(trophy_50),
            'Alpha Clan Trophies: {:,} :trophy:'.format(alpha_clan_trophies),
            'Global Rank: {:,}'.format(alpha_global_rank),
            'Top 50 Clan Trophies: {:,} :trophy:'.format(top50_clan_trophies),
            'Possible Rank: {:,}'.format(possible_alpha_rank),
        ]

        # await self.bot.say('\n'.join(o))

        # logic calc

        for index, member_model in enumerate(member_models, 1):
            # non alpha in top 50
            clan_tag = member_model.get('clan', {}).get('tag')

            if index == 50:
                trophy_50 = member_model.get('trophies')

            if index <= 50:
                if clan_tag != ALPHA_CLAN_TAG:
                    top50_results.append({
                        'index': index,
                        'member': member_model,
                    })

            # alphas not in top 50
            else:
                if clan_tag == ALPHA_CLAN_TAG:
                    non_top50_results.append({
                        'index': index,
                        'member': member_model
                    })

        def append_result(result, out, out_members):
            index = result['index']
            member = result['member']
            clan_name = member.get('clan', {}).get('name').replace('RoyaleAPI', '').strip()
            trophies = member.get('trophies')
            delta = trophies - trophy_50
            if delta > 0:
                delta = '+{}'.format(delta)
            elif delta == 0:
                delta = ' {}'.format(delta)
            line = '`\u2800{rank: >3} {trophies:<4}\u2800`**{member}** {clan_name} {delta:<4}'.format(
                rank=index,
                member=member.get('name')[:15],
                clan_name=clan_name,
                trophies=trophies,
                delta=delta
            )
            out.append(line)
            out_members.append(member)

        # top 50 not in alpha
        # out = ['Top 50 not in Alpha']
        out = []
        out_members = []
        for result in top50_results:
            append_result(result, out, out_members)

        # for page in pagify('\n'.join(out)):
        #     await self.bot.say(box(page, lang='py'))

        # alphas not in top 50
        # out_2 = ['Alphas not in top 50']
        out_2 = []
        out_2_members = []
        for result in non_top50_results:
            append_result(result, out_2, out_2_members)

        # for page in pagify('\n'.join(out_2)):
        #     await self.bot.say(box(page, lang='py'))

        # embed display
        em = discord.Embed(
            title="End of season",
            description="\n".join(o_summary),
            color=discord.Color.blue()
        )
        em.add_field(
            name="Top 50 not in Alpha",
            value='\n'.join(out),
            inline=False
        )
        em.add_field(
            name="Alphas not in Top 50",
            value='\n'.join(out_2),
            inline=False
        )
        await self.bot.say(embed=em)

        def append_discord_member(member_list, member):
            tag = clean_tag(member.get('tag'))
            try:
                discord_id = self.players[tag]["user_id"]
            except KeyError:
                pass
            else:
                discord_member = server.get_member(discord_id)
                if discord_member is not None:
                    member_list.append(discord_member)

        # options for output mentions
        if 'Bot Commander' in [r.name for r in author.roles]:
            top50_discord_members = []
            non_top50_discord_members = []
            for member in out_members:
                append_discord_member(top50_discord_members, member)

            for member in out_2_members:
                append_discord_member(non_top50_discord_members, member)

            if '-id' in args:
                out = ['Top 50 not in Alpha']
                for discord_member in top50_discord_members:
                    out.append(discord_member.id)

                out.append('Alphas not in Top 50')
                for discord_member in non_top50_discord_members:
                    out.append(discord_member.id)
                for page in pagify('\n'.join(out)):
                    await self.bot.say(box(page, lang='py'))

            if '-mention' in args:
                out = []
                for discord_member in top50_discord_members:
                    out.append(discord_member.mention)
                out.append(
                    'Congratulations! You are top 50 in the RACF. '
                    'Please move to Alpha by end of season to help us with the global rank!'
                )

                for discord_member in non_top50_discord_members:
                    out.append(discord_member.mention)
                out.append(
                    'You are not within top 50 in the RACF right now. '
                    'Please move to Bravo unless you are certain that you can un-tilt.'
                )
                out.append(
                    '\n\nNote: If you are _very_ close to where the 50th is, you can stay put. '
                    'Just be conscious of that number. Thank you! :heart:'
                )
                for page in pagify(' '.join(out)):
                    await self.bot.say(page)

    @racfaudit.command(name="auto", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manager_server=True)
    async def racfaudit_auto(self, ctx, channel: discord.Channel = None):
        """Auto audit server"""
        server = ctx.message.server
        enabled = channel is not None
        channel_id = None
        if channel is not None:
            channel_id = channel.id

        if not self.settings.get('auto_audit_servers'):
            self.settings['auto_audit_servers'] = dict()

        self.settings['auto_audit_servers'][server.id] = dict(
            enabled=enabled,
            channel_id=channel_id
        )
        dataIO.save_json(JSON, self.settings)

        if enabled:
            await self.bot.say("Auto audit enabled")
        else:
            await self.bot.say("Auto audit disabled")

    async def run_audit_task(self):
        """Auto run audit."""
        while self == self.bot.get_cog("RACFAudit"):
            try:
                for server_id, v in self.settings.get('auto_audit_servers', {}).items():
                    if server_id in [RACF_SERVER_ID, SML_SERVER_ID]:
                        channel_id = v.get('channel_id')
                        enabled = v.get('enabled')
                        if enabled:
                            channel = self.bot.get_channel(channel_id)
                            server = self.bot.get_server(server_id)
                            if channel is not None:
                                result = await self.run_racfaudit(server)
                                await self.exec_racf_audit(channel, audit_results=result.audit_results, server=server)
            except Exception:
                pass
            finally:
                interval = int(dt.timedelta(hours=4).total_seconds())
                await asyncio.sleep(interval)

    @racfaudit.command(name="nudge", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(kick_members=True)
    async def racfaudit_nudge(self, ctx, query):
        """Nudge members for CW battles."""
        api = ClashRoyaleAPI(self.auth)
        server = ctx.message.server

        # find clan tag based on config filters
        tag = None
        for clan in self.config.get('clans'):
            if query.lower() in [f.lower() for f in clan.get('filters', [])]:
                tag = clan.get('tag')
                break

        if tag is None:
            await self.bot.say("Cannot find clan tag")
            return

        await self.bot.say("Clan tag: {}".format(tag))
        cw = await api.fetch_clan_war(tag)
        cwd = Dict(cw)
        c = await api.fetch_clan(tag)
        cd = Dict(c)

        # tag to member name
        member_tag_to_name = {clean_tag(m.get('tag', '')): m.get('name', '') for m in cd.memberList}

        # helper: send message
        async def send_message(war_day="Collection Day", timedelta_human="0 minutes", discord_users=None):
            if discord_users:
                msg = "{mentions} {timedelta} til end of {war_day} and you have battles remaining!!".format(
                    war_day=war_day,
                    mentions=" ".join([u.mention for u in discord_users]),
                    timedelta=timedelta_human,
                    member_tags=", ".join(member_tags)
                )
                await self.bot.say(msg)

            if war_day == 'War Day':
                await self.bot.say("Note: we cannot detect members who have more than one battles to play.")

        # helper: not on discord:
        async def send_not_on_discord(member_tag):
            await self.bot.say(
                "{member_name} #{member_tag} is not on Discord.".format(
                    member_name=member_tag_to_name.get(member_tag, ''),
                    member_tag=member_tag
                )
            )

        # collection day nudge
        now = dt.datetime.utcnow()
        member_tags = []
        if cwd.state == 'collectionDay':
            # time remaining
            end_time = dt.datetime.strptime(cwd.collectionEndTime, '%Y%m%dT%H%M%S.%fZ')
            # end_time = dt.datetime.strptime('20190126T102716.230Z', '%Y%m%dT%H%M%S.%fZ')
            timedelta = end_time - now
            minutes = timedelta // dt.timedelta(minutes=1)
            timedelta_human = "{}".format(humanfriendly.format_timespan(dt.timedelta(minutes=minutes).total_seconds()))

            # battle remaining
            for p in cwd.participants:
                if p.collectionDayBattlesPlayed != 3:
                    member_tags.append(clean_tag(p.tag))

            # not yet participating
            participant_tags = [p.get('tag') for p in cwd.participants]
            for m in cd.memberList:
                if m.get('tag') not in participant_tags:
                    member_tags.append(clean_tag(m.get('tag')))

            # discord user
            discord_users = []
            tag2discord = {v.get('tag'): v.get('user_id') for k, v in self.players.items()}
            for member_tag in member_tags:
                if member_tag in tag2discord:
                    discord_id = tag2discord.get(member_tag)
                    discord_user = server.get_member(discord_id)
                    if discord_user is not None:
                        discord_users.append(discord_user)
                    else:
                        await send_not_on_discord(member_tag)

                else:
                    await send_not_on_discord(member_tag)

            await send_message(war_day="Collection Day", timedelta_human=timedelta_human, discord_users=discord_users)
            return

        if cwd.state == 'warDay':
            # time remaining
            end_time = dt.datetime.strptime(cwd.warEndTime, '%Y%m%dT%H%M%S.%fZ')
            timedelta = end_time - now
            minutes = timedelta // dt.timedelta(minutes=1)
            timedelta_human = "{}".format(humanfriendly.format_timespan(dt.timedelta(minutes=minutes).total_seconds()))

            # battles remaining
            for p in cwd.participants:
                if p.battlesPlayed == 0:
                    member_tags.append(clean_tag(p.tag))

            # discord user
            players = [self.players.get(member_tag) for member_tag in member_tags]
            players = [p for p in players if p]

            discord_users = []
            for player in players:
                discord_id = player.get('user_id')
                discord_user = server.get_member(discord_id)
                if discord_user is None:
                    member_tag = player.get('tag')
                    await send_not_on_discord(member_tag)
                else:
                    discord_users.append(discord_user)

            await send_message(war_day="War Day", timedelta_human=timedelta_human, discord_users=discord_users)
            return

        if cwd.state.lower() == 'matchmaking':
            await self.bot.say("Clan is matchmaking… aborted.")
            return

        if cwd.state.lower() == 'notinwar':
            await self.bot.say("Clan is not in war… aborted.")
            return

        # not in war or collection
        await self.bot.say("Clan is not in a known war state… aborted.")


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
    bot.loop.create_task(n.run_audit_task())
