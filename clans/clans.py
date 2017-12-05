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
import re
from collections import defaultdict

import aiohttp
import crapipy
import discord
import yaml
import pprint
from __main__ import send_cmd_help
from box import Box, BoxList
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "clans")
JSON = os.path.join(PATH, "settings.json")
CACHE = os.path.join(PATH, "cache.json")
SAVE_CACHE = os.path.join(PATH, "save_cache.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")


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

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def clansset(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @clansset.command(name="config", pass_context=True, no_pm=True)
    async def clansset_config(self, ctx):
        """Upload config yaml file. See config.example.yml for how to format it."""
        TIMEOUT = 60.0
        await self.bot.say(
            "Please upload family config yaml file. "
            "[Timeout: {} seconds]".format(TIMEOUT))
        attach_msg = await self.bot.wait_for_message(
            timeout=TIMEOUT,
            author=ctx.message.author)
        if attach_msg is None:
            await self.bot.say("Operation time out.")
            return
        if not len(attach_msg.attachments):
            await self.bot.say("Cannot find attachments.")
            return
        attach = attach_msg.attachments[0]
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

    @commands.command(pass_context=True, no_pm=True)
    async def clans(self, ctx, *args):
        """Display clan info.

        [p]clans -m   Disable member count
        [p]clans -t   Disable clan tag
        """
        await self.bot.type()
        client = crapipy.AsyncClient()
        config = self.clans_config
        clan_tags = [clan.tag for clan in config.clans]

        try:
            clans = await client.get_clans(clan_tags)
            dataIO.save_json(CACHE, clans)
        except crapipy.exceptions.APIError:
            data = dataIO.load_json(CACHE)
            clans = [crapipy.models.Clan(d) for d in data]

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
            match = re.search('[\d,O]{4,}', clan.description)
            pb_match = re.search('PB', clan.description)
            name = clan.name
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
                member_count = ', {} / 50'.format(clan.member_count)
            clan_tag = ''
            if show_clan_tag:
                clan_tag = ', #{}'.format(clan.tag)
            value = '`{trophies}{pb}{member_count}{clan_tag}`'.format(
                clan_tag=clan_tag,
                member_count=member_count,
                trophies=trophies,
                pb=pb)
            em.add_field(name=name, value=value, inline=False)
            if badge_url is None:
                badge_url = 'https://cr-api.github.io/cr-api-assets/badge/{}.png'.format(clan.badge.key)
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
