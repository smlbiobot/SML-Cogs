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

from collections import OrderedDict
from collections import defaultdict

import aiohttp
import argparse
import asyncio
import discord
import json
import os
import re
import unidecode
import yaml
from discord.ext import commands
from tabulate import tabulate

from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, box, inline, underline
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "racf_audit")
JSON = os.path.join(PATH, "settings.json")
PLAYERS = os.path.join("data", "racf_audit", "player_db.json")


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

    async def fetch_clan_leaderboard(self, location=None):
        """Get clan leaderboard"""
        url = 'https://api.clashroyale.com/v1/locations/global/rankings/clans'
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

    async def set_player_tag(self, tag, member: discord.Member, force=False):
        """Allow external programs to set player tags. (RACF)"""
        await asyncio.sleep(0)
        players = self.players
        if tag in players.keys():
            if not force:
                return False
        players[tag] = {
            "tag": clean_tag(tag),
            "user_id": member.id,
            "user_name": member.display_name
        }
        dataIO.save_json(PLAYERS, players)
        return True

    async def get_player_tag(self, tag):
        await asyncio.sleep(0)
        return self.players.get(tag)

    async def rm_playr_tag(self, tag):
        """Remove player tag from settings."""

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

    async def family_member_models(self):
        """All family member models."""
        api = ClashRoyaleAPI(self.auth)
        tags = self.clan_tags()
        clan_models = await api.fetch_clan_list(tags)
        members = []
        for clan_model in clan_models:
            for member_model in clan_model.get('memberList'):
                member_model['tag'] = clean_tag(member_model.get('tag'))
                member_model['clan'] = clan_model
                members.append(member_model)
        return members

    @racfaudit.command(name="tag", pass_context=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_tag(self, ctx, member: discord.Member):
        """Find member tag in DB."""
        found = False
        for tag, m in self.players.items():
            if m["user_id"] == member.id:
                await self.bot.say("100T Audit database: `{}` is associated to `#{}`".format(member, tag))
                found = True

        if not found:
            await self.bot.say("100T Audit database: Member is not associated with any tags.")

    @racfaudit.command(name="rmtag", pass_context=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racfaudit_rm_tag(self, ctx, tag):
        """Remove tag in DB."""
        tag = clean_tag(tag)
        try:
            self.players.pop(tag, None)
        except KeyError:
            await self.bot.say("Tag not found in DB.")
        else:
            dataIO.save_json(PLAYERS, self.players)
            await self.bot.say("Removed tag from DB.")

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
    @checks.mod_or_permissions(manage_roles=True)
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
        parser = self.run_args_parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        option_debug = pargs.debug
        option_exec = pargs.exec

        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return
        else:
            await self.bot.say("**100T Family Audit**")
            # Show settings
            if pargs.settings:
                await ctx.invoke(self.racfaudit_config)

            server = ctx.message.server

            # associate Discord user to member
            for member_model in member_models:
                tag = clean_tag(member_model.get('tag'))
                try:
                    discord_id = self.players[tag]["user_id"]
                except KeyError:
                    pass
                else:
                    member_model['discord_member'] = server.get_member(discord_id)

            if option_debug:
                for member_model in member_models:
                    print(member_model.get('tag'), member_model.get('discord_member'))

            """
            Member processing.
    
            """
            audit_results = {
                "elder_promotion_req": [],
                "coleader_promotion_req": [],
                "leader_promotion_req": [],
                "no_discord": [],
                "no_clan_role": [],
                "no_member_role": [],
                "not_in_our_clans": [],
            }

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

            out = []
            for clan in self.config['clans']:
                await self.bot.type()
                await asyncio.sleep(0)

                display_output = False

                if pargs.clan:
                    for c in pargs.clan:
                        if c.lower() in clan['name'].lower():
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

            for page in pagify('\n'.join(out)):
                await self.bot.say(page)

            if option_exec:
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
                                await asyncio.sleep(0)
                                await self.bot.remove_roles(discord_member, role)
                                await self.bot.say("Remove {} from {}".format(role, discord_member))

                        role = discord.utils.get(server.roles, name=clan_role_name)
                        await asyncio.sleep(0)
                        await self.bot.add_roles(discord_member, role)
                        await self.bot.say("Add {} to {}".format(role.name, discord_member))
                    except KeyError:
                        pass

                member_role = discord.utils.get(server.roles, name='Member')
                visitor_role = discord.utils.get(server.roles, name='Visitor')
                for discord_member in audit_results["no_member_role"]:
                    try:
                        await asyncio.sleep(0)
                        await self.bot.add_roles(discord_member, member_role)
                        await self.bot.say("Add {} to {}".format(member_role, discord_member))
                        await self.bot.remove_roles(discord_member, visitor_role)
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
                    for role_name in ['Member', 'Tourney', 'Practice']:
                        if role_name in result_role_names:
                            to_remove_role_names.append(role_name)
                    to_remove_roles = [discord.utils.get(server.roles, name=rname) for rname in to_remove_role_names]
                    await asyncio.sleep(0)
                    await self.bot.remove_roles(result, *to_remove_roles)
                    await self.bot.say("Removed {} from {}".format(
                        ", ".join(to_remove_role_names), result)
                    )
                    await self.bot.add_roles(result, visitor_role)
                    await self.bot.say("Added Visitor to {}".format(result))

            await self.bot.say("Audit finished.")

    @racfaudit.command(name="rank", pass_context=True)
    async def racfaudit_rank(self, ctx, *names):
        """Look up member rank within the family."""
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        results = []

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)

        for index, member_model in enumerate(member_models, 1):
            # simple search
            for name in names:
                add_it = False
                if name.lower() in member_model.get('name').lower():
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

        limit = 10

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

    @checks.mod_or_permissions()
    @commands.command(name="racfaudit_top", aliases=["rtop"], pass_context=True)
    async def racfaudit_top(self, ctx, count: int):
        """Show top N members in family."""
        await self.bot.type()

        try:
            member_models = await self.family_member_models()
        except ClashRoyaleAPIError as e:
            await self.bot.say(e.status_message)
            return

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)
        results = member_models[:count]

        out = []

        for index, member in enumerate(results, 1):
            out.append('{:<4} {:>4} {:<8} {}'.format(
                index, member['trophies'], member['clan']['name'][5:], member['name']
            ))

        await self.bot.say(
            box('\n'.join(out), lang='python')
        )

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

        trophy_50 = 0

        ALPHA_CLAN_TAG = '#9PJ82CRC'

        member_models = sorted(member_models, key=lambda x: x['trophies'], reverse=True)

        alpha_trophies = [m.get('trophies') for m in member_models if m.get('clan', {}).get('tag') == ALPHA_CLAN_TAG]
        alpha_clan_trophies = self.calculate_clan_trophies(alpha_trophies)
        top50_trophies = [m.get('trophies') for m in member_models[:50]]
        top50_clan_trophies = self.calculate_clan_trophies(top50_trophies)

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
        o = [
            '50th in 100T = {:,} :trophy: '.format(trophy_50),
            'Alpha Clan Trophies: {:,} :trophy:'.format(alpha_clan_trophies),
            'Global Rank: {:,}'.format(alpha_global_rank),
            'Top 50 Clan Trophies: {:,} :trophy:'.format(top50_clan_trophies),
            'Possible Rank: {:,}'.format(possible_alpha_rank),
        ]

        await self.bot.say('\n'.join(o))

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
            clan_name = member.get('clan', {}).get('name').replace('100T', '').strip()
            trophies = member.get('trophies')
            delta = trophies - trophy_50
            if delta > 0:
                delta = '+{}'.format(delta)
            elif delta == 0:
                delta = ' {}'.format(delta)
            line = '{:<3} {: <15} {:<7} {:<4} {:<4}'.format(
                index,
                member.get('name')[:15],
                clan_name,
                trophies,
                delta
            )
            out.append(line)
            out_members.append(member)

        # top 50 not in alpha
        out = ['Top 50 not in Alpha']
        out_members = []
        for result in top50_results:
            append_result(result, out, out_members)

        for page in pagify('\n'.join(out)):
            await self.bot.say(box(page, lang='py'))

        # alphas not in top 50
        out_2 = ['Alphas not in top 50']
        out_2_members = []
        for result in non_top50_results:
            append_result(result, out_2, out_2_members)

        for page in pagify('\n'.join(out_2)):
            await self.bot.say(box(page, lang='py'))

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
                out = ['Top 50 not in tAlpha']
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
                    'Congratulations! You are top 50 in the 100T. '
                    'Please move to Alpha by end of season to help us with the global rank!'
                )

                for discord_member in non_top50_discord_members:
                    out.append(discord_member.mention)
                out.append(
                    'You are not within top 50 in the 100T right now. '
                    'Please move to Bravo unless you are certain that you can un-tilt.'
                )
                out.append(
                    '\n\nNote: If you are _very_ close to where the 50th is, you can stay put. '
                    'Just be conscious of that number. Thank you! :heart:'
                )
                for page in pagify(' '.join(out)):
                    await self.bot.say(page)


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
