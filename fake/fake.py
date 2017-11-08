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
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from faker import Faker

PATH = os.path.join("data", "fake")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Fake:
    """Generate fake data."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.locales = dataIO.load_json(os.path.join(PATH, "locales.json"))

    @commands.group(pass_context=True)
    async def fake(self, ctx):
        """Fake data generator."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @fake.command(name="locales", aliases=[], pass_context=True)
    async def fake_locales(self, ctx):
        """List locales"""
        locales = ["**{}**: {}".format(k, v) for k, v in self.locales.items()]
        await self.bot.say(", ".join(locales))

    @fake.command(name="name", pass_context=True)
    async def fake_name(self, ctx, locale=None):
        """Fake name."""
        print(locale)
        await self.bot.say(Faker(locale).name())

    @fake.command(name="ssn", pass_context=True)
    async def fake_ssn(self, ctx, locale=None):
        """Fake SSN."""

        await self.bot.say(Faker(locale).ssn())

    @fake.command(name="profile", aliases=[], pass_context=True)
    async def fake_profile(self, ctx, locale=None):
        """Profile."""
        em = discord.Embed(title="Fake Profile")
        order = [
            'name', 'sex',
            'birthdate', 'blood_group',
            'ssn', 'username',
            'job', 'company',
            'mail',
            'residence',
            'website'
        ]
        profile = Faker(locale).profile()
        for k in order:
            v = profile.get(k)
            if v is None:
                v = '__'
            elif isinstance(v, list):
                v = '\n'.join(v)
            em.add_field(name=k.title(), value=v)
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
    n = Fake(bot)
    bot.add_cog(n)
