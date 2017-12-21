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
import json
import os
import re
from collections import defaultdict

import aiohttp
import discord
import yaml
from box import Box
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "clans")
JSON = os.path.join(PATH, "settings.json")
CACHE = os.path.join(PATH, "cache.json")
SAVE_CACHE = os.path.join(PATH, "save_cache.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")
BADGES = os.path.join(PATH, "alliance_badges.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Clans:
    """Auto parse clan info and display requirements"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.badges = dataIO.load_json(BADGES)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def clansset(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)(ctx)

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

    @property
    def clans_config(self):
        if os.path.exists(CONFIG_YAML):
            with open(CONFIG_YAML) as f:
                config = Box(yaml.load(f))
            return config
        return None

    @property
    def auth(self):
        return self.clans_config.get('auth')

    async def get_clan(self, tag):
        """Return dict of clan"""
        url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
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

    async def get_clans(self, tags):
        """Return list of clans"""
        clans = []
        for tag in tags:
            clan = await self.get_clan(tag)
            clans.append(clan)
        return clans

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
            member_count = ''
            if show_member_count:
                member_count = ', {} / 50'.format(clan.get('members'))
            clan_tag = ''
            if show_clan_tag:
                clan_tag = ', {}'.format(clan.get('tag'))
            value = '`{trophies}{pb}{member_count}{clan_tag}`'.format(
                clan_tag=clan_tag,
                member_count=member_count,
                trophies=trophies,
                pb=pb)
            em.add_field(name=name, value=value, inline=False)

            if badge_url is None:
                badge_id = clan.get('badgeId')
                for badge in self.badges:
                    if badge['badge_id'] == badge_id:
                        name = badge['name']
                        badge_url = 'https://cr-api.github.io/cr-api-assets/badge/{}.png'.format(name)
                        break

        if badge_url is not None:
            em.set_thumbnail(url=badge_url)

        for inf in config.info:
            em.add_field(
                name=inf.name,
                value=inf.value
            )
        await self.bot.say(embed=em)


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
