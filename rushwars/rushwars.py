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

import os
from collections import defaultdict

import discord
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "rushwars")
JSON = os.path.join(PATH, "settings.json")
BAND_CONFIG_YML = os.path.join(PATH, "club.config.yml")
CACHE_PATH = os.path.join(PATH, "cache")
CACHE_PLAYER_PATH = os.path.join(CACHE_PATH, "player")
CACHE_CLUB_PATH = os.path.join(CACHE_PATH, "club")

MANAGE_ROLE_ROLES = ['Bot Commander']


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


class BrawlStars:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._team_config = None

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    def get_emoji(self, name):
        for emoji in self.bot.get_all_emojis():
            if emoji.name == str(name):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    async def _get_server_config(self, server_id=None):
        cfg = await self._get_club_config()
        for server in cfg.get('servers', []):
            if str(server.get('id')) == str(server_id):
                return server
        return None

    @commands.group(pass_context=True, no_pm=True)
    async def rw(self, ctx):
        """Rush Wars."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @rw.command(name="verify", aliases=['v'], pass_context=True)
    @commands.has_any_role(*MANAGE_ROLE_ROLES)
    async def bs_verify(self, ctx, member: discord.Member, tag=None):
        tag = clean_tag(tag)
        ctx_server = ctx.message.server

        self.settings[ctx_server.id][member.id] = tag
        self._save_settings()
        await self.bot.say("Associated {tag} with {member}".format(tag=tag, member=member))

        to_add_roles = ['Rush-Wars', 'RW-Member']

        # add roles
        try:
            roles = [r for r in ctx_server.roles if r.name in to_add_roles]
            if roles:
                await self.bot.add_roles(member, *roles)
                await self.bot.say(
                    "Added {roles} to {member}".format(roles=", ".join(to_add_roles), member=member))
        except discord.errors.Forbidden:
            await self.bot.say("Error: I don’t have permission to add roles.")

        # welcome user
        channel = discord.utils.get(ctx.message.server.channels, name="family-chat")

        if channel is not None:
            await self.bot.say(
                "{} Welcome! You may now chat at {} — enjoy!".format(
                    member.mention, channel.mention))


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)
    os.makedirs(CACHE_PATH, exist_ok=True)
    os.makedirs(CACHE_PLAYER_PATH, exist_ok=True)
    os.makedirs(CACHE_CLUB_PATH, exist_ok=True)


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
