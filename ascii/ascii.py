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

import random

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify

try:
    from pyfiglet import Figlet
    from pyfiglet import FigletFont
    from pyfiglet import FontNotFound
except ImportError:
    raise ImportError("Please install the pyfiglet package.") from None

try:
    import ascii
except ImportError:
    raise ImportError("Please install the ascii pacage.") from None


class Ascii:
    """Ascii art generator."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot


    @commands.command(pass_context=True, no_pm=True)
    async def figletfonts(self, ctx: Context):
        """List all fonts."""
        await self.bot.say("List of supported fonts:")
        out = FigletFont.getFonts()
        for page in pagify(', '.join(out), shorten_by=24):
            await self.bot.say(box(page))

    @commands.command(pass_context=True, no_pm=True)
    async def figlet(self, ctx: Context, text: str, font=None):
        """Convert text to ascii art."""
        if font is None:
            font = 'slant'
        if font == 'random':
            fonts = FigletFont.getFonts()
            font = random.choice(fonts)

        f = Figlet(font=font)
        out = f.renderText(text)
        for page in pagify(out, shorten_by=24):
            await self.bot.say(box(page))

    @commands.command(pass_context=True, no_pm=True)
    async def figletrandom(self, ctx: Context, text: str):
        """Convert text to ascii art using random font."""
        font = random.choice(FigletFont.getFonts())
        f = Figlet(font=font)
        out = f.renderText(text)
        for page in pagify(out, shorten_by=24):
            await self.bot.say(box(page))
        await self.bot.say("Font: {}".format(font))

    @commands.command(pass_context=True, no_pm=True)
    async def img2txt(self, ctx: Context, url: str=None, columns=30):
        """Convert image as URL to ascii."""
        if url is None:
            await send_cmd_help(ctx)
            return
        output = ascii.loadFromUrl(url, columns=columns, color=False)
        for page in pagify(output, shorten_by=24):
            await self.bot.say(box(page))



def setup(bot):
    bot.add_cog(Ascii(bot))
