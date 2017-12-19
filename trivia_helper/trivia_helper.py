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

import csv
import io
import os

import aiohttp
from cogs.utils import checks
from discord.ext import commands


class TriviaHelper:
    """Trivia Helper. Utilities for uploading categories to trivia."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.trivia_path = os.path.join("data", "trivia")

    @checks.mod_or_permissions()
    @commands.command(name="triviacsv", pass_context=True)
    async def triviacsv(self, ctx, category):
        """Upload CSV files for trivia"""
        msg = ctx.message
        url = msg.attachments[0]["url"]
        # await self.bot.say(url)
        trivia = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    trivia.append("{}`{}".format(
                        row["Question"], row["Answer"]
                    ))
        out_file = os.path.join(self.trivia_path, "{}.txt".format(category))
        with open(out_file, "w") as f:
            f.write('\n'.join(trivia))
        await self.bot.say("Data saved to {}".format(out_file))


def setup(bot):
    """Setup."""

    n = TriviaHelper(bot)
    bot.add_cog(n)
