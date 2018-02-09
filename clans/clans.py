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
import asyncio
import json
import os
import re
from collections import defaultdict

import aiohttp
import discord
import unidecode
import yaml
from box import Box
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "clans")
JSON = os.path.join(PATH, "settings.json")
CACHE = os.path.join(PATH, "cache.json")
SAVE_CACHE = os.path.join(PATH, "save_cache.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")
AUTH_YAML = os.path.join(PATH, "auth.yml")
BADGES = os.path.join(PATH, "alliance_badges.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)

class APIError(Exception):
    def __init__(self, message):
        self.message = message


class Clans:
    """Auto parse clan info and display requirements"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.badges = dataIO.load_json(BADGES)
        self._auth = None

        provider = self.settings.get('provider')
        if provider is None:
            provider = 'cr-api'

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def clansset(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @clansset.command(name="api", pass_context=True, no_pm=True)
    async def clansset_api(self, ctx, provider):
        """Set API provider.

        Possible values: cr-api, official
        """
        if provider == 'cr-api':
            self.settings['provider'] = 'cr-api'
        elif provider == 'official':
            self.settings['provider'] = 'official'

        dataIO.save_json(JSON, self.settings)
        await self.bot.say("API Provider updated.")

    @checks.mod_or_permissions()
    @clansset.command(name="config", pass_context=True, no_pm=True)
    async def clansset_config(self, ctx):
        """Upload config yaml file. See config.example.yml for how to format it."""
        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(CONFIG_YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(CONFIG_YAML))

        self.settings['config'] = CONFIG_YAML
        dataIO.save_json(JSON, self.settings)

        await self.bot.delete_message(ctx.message)

    @checks.mod_or_permissions()
    @clansset.command(name="auth", pass_context=True, no_pm=True)
    async def clansset_auth(self, ctx):
        """Upload auth yaml file. See auth.example.yml for how to format it."""
        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(AUTH_YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(AUTH_YAML))

        await self.bot.delete_message(ctx.message)

    @property
    def clans_config(self):
        if os.path.exists(CONFIG_YAML):
            with open(CONFIG_YAML) as f:
                config = Box(yaml.load(f))
            return config
        return None

    @property
    def auth(self):
        if self._auth is None:
            if os.path.exists(AUTH_YAML):
                with open(AUTH_YAML) as f:
                    config = yaml.load(f)
                    if self.api_provider == 'cr-api':
                        self._auth = config.get('cr_api_token')
                    else:
                        self._auth = config.get('official_token')
        return self._auth

    @property
    def api_provider(self):
        if self.settings.get('provider') == 'official':
            return 'official'
        return 'cr-api'

    async def get_clan(self, tag):
        """Return dict of clan"""
        try:
            if self.api_provider == 'official':
                url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
                headers = {'Authorization': 'Bearer {}'.format(self.auth)}
            else:
                url = 'http://api.cr-api.com/clan/{}'.format(tag)
                headers = {'auth': self.auth}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise APIError('json.decoder.JSONDecodeError')
        except asyncio.TimeoutError:
            raise APIError('asyncio.TimeoutError')
        except aiohttp.client_exceptions.ContentTypeError:
            raise APIError('aiohttp.client_exceptions.ContentTypeError')
        else:
            return data

    async def get_clans(self, tags):
        """Return list of clans"""
        try:
            if self.api_provider == 'official':
                urls = ['https://api.clashroyale.com/v1/clans/%23{}'.format(tag) for tag in tags]
                headers = {'Authorization': 'Bearer {}'.format(self.auth)}
                data = []
                async with aiohttp.ClientSession() as session:
                    for url in urls:
                        async with session.get(url, headers=headers, timeout=30) as resp:
                            await asyncio.sleep(0)
                            data.append(await resp.json())
            else:
                url = 'http://api.cr-api.com/clan/{}'.format(",".join(tags))
                headers = {'auth': self.auth}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=30) as resp:
                        data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise APIError('json.decoder.JSONDecodeError')
        except asyncio.TimeoutError:
            raise APIError('asyncio.TimeoutError')
        except aiohttp.client_exceptions.ContentTypeError:
            raise APIError('aiohttp.client_exceptions.ContentTypeError')
        else:
            return data

    @commands.command(pass_context=True, no_pm=True)
    async def clans(self, ctx, *args):
        """Display clan info.

        [p]clans -m   Disable member count
        [p]clans -t   Disable clan tag
        """
        await self.bot.type()
        config = self.clans_config
        clan_tags = [clan.tag for clan in config.clans]

        use_cache = False
        clans = []
        try:
            clans = await self.get_clans(clan_tags)
            dataIO.save_json(CACHE, clans)
        except json.decoder.JSONDecodeError:
            use_cache = True
        except asyncio.TimeoutError:
            use_cache = True

        if use_cache:
            data = dataIO.load_json(CACHE)
            clans = data
            await self.bot.say("Cannot load from API. Loading info from cache.")

        em = discord.Embed(
            title=config.name,
            description=config.description,
            color=discord.Color(int(config.color, 16))
        )
        badge_url = None
        show_member_count = "-m" not in args
        show_clan_tag = "-t" not in args

        for clan in clans:
            desc = clan.get('description')
            match = re.search('[\d,O]{4,}', desc)
            pb_match = re.search('PB', desc)
            psf_match = re.search('PSF', desc)
            name = clan.get('name')
            if match is not None:
                trophies = match.group(0)
                trophies = trophies.replace(',', '')
                trophies = trophies.replace('O', '0')
                trophies = '{:,}'.format(int(trophies))
            else:
                trophies = clan.required_score
            pb = ''
            if pb_match is not None:
                pb = ' PB'
            psf = ''
            if psf_match is not None:
                psf = ' PSF'
            member_count = ''
            if show_member_count:
                if self.api_provider == 'official':
                    member_count = clan.get('members')
                else:
                    member_count = len(clan.get('members'))

                member_count = ', {} / 50'.format(member_count)

            clan_tag = ''
            if show_clan_tag:
                clan_tag = ', {}'.format(clan.get('tag'))
            value = '`{trophies}{pb}{psf}{member_count}{clan_tag}`'.format(
                clan_tag=clan_tag,
                member_count=member_count,
                trophies=trophies,
                pb=pb,
                psf=psf)
            em.add_field(name=name, value=value, inline=False)

            if badge_url is None:
                if self.api_provider == 'official':
                    for badge in self.badges:
                        if badge.get('id') == clan.get('badgeId'):
                            badge_url = 'https://cr-api.github.io/cr-api-assets/badges/{}.png'.format(badge.get('name'))
                else:
                    badge_url = clan['badge']['image']

        if badge_url is not None:
            em.set_thumbnail(url=badge_url)

        for inf in config.info:
            em.add_field(
                name=inf.name,
                value=inf.value
            )
        await self.bot.say(embed=em)

    def search_args_parser(self):
        """Search arguments parser."""
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

    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True)
    async def clanmembersearch(self, ctx, *args):
        """Search for member.

        usage: [p]crmembersearch [-h] [-t TAG] name

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

        await self.bot.type()
        config = self.clans_config
        clan_tags = [clan.tag for clan in config.clans]

        api_error = False
        clans = []
        try:
            clans = await self.get_clans(clan_tags)
            dataIO.save_json(CACHE, clans)
        except json.decoder.JSONDecodeError:
            api_error = True
        except asyncio.TimeoutError:
            api_error = True

        if api_error:
            await self.bot.say("Cannot load clans from API.")
            return

        members = []
        for clan in clans:
            for member in clan.get('members'):
                member = Box(member)
                member.clan = clan
                members.append(member)

        results = []

        if pargs.name != '_':
            for member in members:
                # simple search
                if pargs.name.lower() in member['name'].lower():
                    results.append(member)
                else:
                    # unidecode search
                    s = unidecode.unidecode(member['name'])
                    s = ''.join(re.findall(r'\w', s))
                    if pargs.name.lower() in s.lower():
                        results.append(member)
        else:
            results = members
            print(len(results))

        # filter by clan name
        if pargs.clan:
            results = [m for m in results if pargs.clan.lower() in m.clan.name.lower()]

        # filter by trophies
        results = [m for m in results if pargs.min <= m['trophies'] <= pargs.max]

        limit = 10
        if len(results) > limit:
            await self.bot.say(
                "Found more than {0} results. Returning top {0} only.".format(limit)
            )
            results = results[:limit]

        roles = {
            'leader': 'Leader',
            'coleader': 'Co-Leader',
            'elder': 'Elder',
            'member': 'Member'
        }

        if len(results):
            out = []
            for member_model in results:
                member_model['role_name'] = roles[member_model['role'].lower()]
                out.append("**{0.name}** #{0.tag}, {0.clan.name}, {0.role_name}, {0.trophies}".format(member_model))
                if pargs.link:
                    out.append('http://cr-api.com/player/{}'.format(member_model.tag))
            for page in pagify('\n'.join(out)):
                await self.bot.say(page)
        else:
            await self.bot.say("No results found.")


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
    n = Clans(bot)
    bot.add_cog(n)
