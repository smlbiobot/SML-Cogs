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

import json
import os
import re
from collections import defaultdict

import aiohttp
import discord
import yaml
from __main__ import send_cmd_help
from box import Box
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "bands")
JSON = os.path.join(PATH, "settings.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Client():
    """BrawlStats async client."""

    def __init__(self, auth=None):
        """Init."""
        self.headers = {
            'Authorization': auth
        }

    def api_url(self, kind, tag):
        """Return clan api url"""
        if kind == "bands":
            return "https://api.brawlstats.io/v1/bands/" + tag

    async def get_band(self, tag):
        """Get a clan."""
        data = None
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(self.api_url("bands", tag)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
        except json.JSONDecodeError:
            return None

        return Box(data)

    async def get_bands(self, tags):
        data = []
        for tag in tags:
            d = await self.get_band(tag)
            if d is not None:
                data.append(d)
        return data


class Bands:
    """Auto parse band info and display requirements"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if self.bands_config is not None:
                self._client = Client(auth=self.bands_config.authorization)
        return self._client

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def bandsset(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @bandsset.command(name="config", pass_context=True, no_pm=True)
    async def bandsset_config(self, ctx):
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
    def bands_config(self):
        if os.path.exists(CONFIG_YAML):
            with open(CONFIG_YAML) as f:
                config = Box(yaml.load(f))
            return config
        return None

    def get_band_config(self, tag):
        for band in self.bands_config.bands:
            if band.tag == tag:
                return Box(band, default_box=True)
        return None

    @commands.command(pass_context=True, no_pm=True)
    async def bands(self, ctx, *args):
        """Display band info.

        [p]bands -m   Disable member count
        [p]bands -t   Disable band tag
        """
        await self.bot.type()
        config = self.bands_config
        band_tags = [band.tag for band in config.bands]
        bands = await self.client.get_bands(band_tags)
        color = getattr(discord.Color, config.color)()
        em = discord.Embed(
            title=config.name,
            description="Minimum trophies to join our Brawl Stars bands. Current trophies required.",
            color=color
        )
        show_member_count = "-m" not in args
        show_band_tag = "-t" not in args
        for band in bands:
            match = re.search('[\d,O]{3,}', band.description)
            pb_match = re.search('PB', band.description)
            name = band.name
            band_config = self.get_band_config(band.tag)
            trophies = 'N/A'
            if band_config.req:
                trophies = band_config.req
            elif match is not None:
                trophies = match.group(0)
                trophies = trophies.replace(',', '')
                trophies = trophies.replace('O', '0')
                trophies = '{:,}'.format(int(trophies))
            else:
                trophies = band.required_score
            pb = ''
            if pb_match is not None:
                pb = ' PB'
            member_count = ''
            if show_member_count:
                member_count = '{} / 100\n'.format(band.member_count)
            band_tag = ''
            if show_band_tag:
                band_tag = '#{}\n'.format(band.tag)
            value = '{band_tag}{member_count}{trophies}{pb}'.format(
                band_tag=band_tag,
                member_count=member_count,
                trophies=trophies,
                pb=pb)
            em.add_field(name=name, value=value)
            em.set_thumbnail(url=config.logo_url)
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
    n = Bands(bot)
    bot.add_cog(n)
