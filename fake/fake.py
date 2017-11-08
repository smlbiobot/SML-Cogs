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

from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from faker import Faker
import discord

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
        self.faker = Faker()

    @commands.group(pass_context=True)
    async def fake(self, ctx):
        """Fake data generator."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @fake.command(name="name", pass_context=True, no_pm=True)
    async def fake_name(self, ctx):
        """Name."""
        await self.bot.say(self.faker.name())

    @fake.command(name="ssn", pass_context=True, no_pm=True)
    async def fake_name(self, ctx):
        """Name."""
        await self.bot.say(self.faker.ssn())

    @fake.command(name="profile", aliases=[], pass_context=True, no_pm=True)
    async def fake_profile(self, ctx):
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
        profile = self.faker.profile()
        for k in order:
            v = profile[k]
            if isinstance(v, list):
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
