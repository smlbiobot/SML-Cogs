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

import io
import os
from collections import defaultdict
from urllib.parse import urlparse

import aiohttp
from PIL import Image
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "imgutil")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ImgUtil:
    """Image utility."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(name="imgutil", aliases=["iu"], pass_context=True, no_pm=True)
    async def imgutil(self, ctx):
        """Image utility."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @imgutil.command(name="rotate", aliases=["r"], pass_context=True, no_pm=True)
    async def imgutil_rotate(self, ctx, degree, url):
        """Rotate image with URL.

        Degree: rotateion degrees counter-clockwise
        """
        a = urlparse(url)
        filename = os.path.basename(a.path)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                img = await resp.read()
                im = Image.open(io.BytesIO(img))
                im = im.rotate(float(degree), expand=True)

                with io.BytesIO() as f:
                    im.save(f, "JPEG")
                    f.seek(0)
                    message = await ctx.bot.send_file(
                        ctx.message.channel, f,
                        filename=filename, content="Rotated image:")


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
    n = ImgUtil(bot)
    bot.add_cog(n)
