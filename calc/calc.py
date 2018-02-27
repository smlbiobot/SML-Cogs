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

from cogs.utils.chat_formatting import box
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from py_expression_eval import Parser

PATH = os.path.join("data", "calc")
JSON = os.path.join(PATH, "settings.json")


class Calc:
    """Simple Calculator"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.config = dataIO.load_json(JSON)

    @commands.group(pass_context=True)
    async def calcset(self, ctx):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @calcset.command(name="wolframalpha", pass_context=True, no_pm=True)
    async def calcset_wolframalpha(self, ctx, value=None):
        """Wolfram Alpha AppID."""
        if value is None:
            await self.bot.say(self.wolframalpha_appid)
        else:
            self.wolframalpha_appid = value
            await self.bot.say("Settings saved.")

    @commands.command(name="calc", pass_context=True)
    async def calc(self, ctx, *, input):
        """Calculator.

        Expression | Example    | Output
        ---------- | -------    | ------
        +          | 2 + 2      | 4.0
        -          | 3 - 1      | 2.0
        *.         | 2 * 3      | 6.0
        /          | 5 / 2      | 2.5
        %          | 5 % 2      | 1.0
        ^          | 5 ^ 2      | 25.0
        PI         | PI         | 3.14159265
        E          | E          | 2.71828182
        sin(x)     | sin(0)     | 0.0
        cos(x)     | cos(PI)    | - 1.0
        tan(x)     | tan(0)     | 0.0
        asin(x)    | asin(0)    | 0.0
        acos(x)    | acos(-1)   | 3.14159265
        atan(x)    | atan(PI)   | 1.26262725
        log(x)     | log(1)     | 0.0
        abs(x)     | abs(-1)    | 1.0
        ceil(x)    | ceil(2.7)  | 3.0
        floor(x)   | floor(2.7) | 2.0
        round(x)   | round(2.7) | 3.0
        exp(x)     | exp(2)     | 7.38905609
        """
        if not input:
            await self.bot.send_cmd_help(ctx)
            return

        await self.bot.say(box(input))

        parser = Parser()
        try:
            out = parser.parse(input).evaluate({})
        except ZeroDivisionError:
            await self.bot.say(":warning: Zero division error")
            return
        except OverflowError:
            await self.bot.say(":warning: Overflow error")
            return
        except FloatingPointError:
            await self.bot.say(":warning: floating point error.")
            return

        await self.bot.say(box(out))

    @commands.group(pass_context=True)
    async def calcfunc(self, ctx):
        """Calculating functions"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @calcfunc.command(name="simplify", pass_context=True, no_pm=True)
    async def calcfunc_simplify(self, ctx, *, expression):
        """Simplify an expression"""
        if not expression:
            await self.bot.send_cmd_help(ctx)
            return
        try:
            parser = Parser()
            exp = parser.parse(expression)
            out = exp.simplify({}).toString()
            await self.bot.say(box(expression))
            await self.bot.say(box(out))
        except Exception as err:
            await self.bot.say(':warning:' + str(err))


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = Calc(bot)
    bot.add_cog(n)
