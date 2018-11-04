"""
The MIT License (MIT)

Copyright (c) 2018 SML

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
import itertools
import socket
import os
from collections import defaultdict
from random import choice

import discord
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
import aiohttp

PATH = os.path.join("data", "brawlstars")
JSON = os.path.join(PATH, "settings.json")

from box import Box


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)

def clean_tag(tag):
    """Clean supercell tag"""
    t = tag
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    t = t.replace('#', '')
    return t



class BSPlayer(Box):
    """Player model"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BSClan(Box):
    """Player model"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


async def api_fetch(url=None, auth=None):
    """Fetch from BS API"""
    conn = aiohttp.TCPConnector(
        family=socket.AF_INET,
        verify_ssl=False,
    )
    async with aiohttp.ClientSession(connector=conn) as session:
        async with session.get(url, headers=dict(Authorization=auth)) as resp:
            data = await resp.json()
    return data


async def api_fetch_player(tag=None, auth=None):
    """Fetch player"""
    url = 'https://brawlapi.cf/api/players/{}'.format(clean_tag(tag))
    data = await api_fetch(url=url, auth=auth)
    return BSPlayer(data)



class BrawlStars:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions()
    async def bsset(self, ctx):
        """Set Brawl Stars API settings.

        Require https://brawlapi.cf/api
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @bsset.command(name="init", pass_context=True)
    async def bsset_init(self, ctx):
        """Init BS Band settings."""
        server = ctx.message.server
        self.settings[server.id] = {}
        if self._save_settings:
            await self.bot.say("Server settings initialized.")

    @bsset.command(name="auth", pass_context=True)
    async def bsset_auth(self, ctx, token):
        """Authorization (token)."""
        self.settings['brawlapi_token'] = token
        if self._save_settings():
            await self.bot.say("Authorization (token) updated.")
        await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True, no_pm=True)
    async def bs(self, ctx):
        """Brawl Stars."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @bs.command(name="settag", alias=['st'], pass_context=True)
    async def bs_settag(self, ctx, tag):
        """Assign tag to self."""
        tag = clean_tag(tag)
        server = ctx.message.server
        author = ctx.message.author
        self.settings[server.id][author.id] = tag
        if self._save_settings():
            await self.bot.say("Tag saved.")


    @bs.command(name="profile", aliases=['p'], pass_context=True)
    async def bs_profile(self, ctx, tag=None):
        """BS Profile."""
        server = ctx.message.server
        author = ctx.message.author
        if tag is None:
            tag = self.settings.get(server.id, {}).get(author.id)
            if tag is None:
                await self.bot.say("Can’t find tag associated with user.")

        await self.bot.say(tag)
        player = await api_fetch_player(tag=tag, auth=self.settings.get('brawlapi_token'))
        await self.bot.say(player.name)


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
    n = BrawlStars(bot)
    bot.add_cog(n)
