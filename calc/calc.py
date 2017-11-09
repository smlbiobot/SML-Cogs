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
from __main__ import send_cmd_help
from cogs.utils.chat_formatting import box
from discord.ext import commands
from py_expression_eval import Parser


class Calc:
    """Simple Calculator"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot

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
            await send_cmd_help(ctx)
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
            await send_cmd_help(ctx)

    @calcfunc.command(name="simplify", pass_context=True, no_pm=True)
    async def calcfunc_simplify(self, ctx, *, expression):
        """Simplify an expression"""
        if not expression:
            await send_cmd_help(ctx)
            return
        try:
            parser = Parser()
            out = parser.parse(expression).simplify({}).toString()
            await self.bot.say(box(expression))
            await self.bot.say(box(out))
        except Exception as err:
            await self.bot.say(':warning:' + err)


def setup(bot):
    """Setup."""
    n = Calc(bot)
    bot.add_cog(n)
