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
import time

import discord
import humanfriendly
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "remindme_ext")
JSON = os.path.join(PATH, "settings.json")


class RemindmeExt:
    """Remind me extension."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.reminders = dataIO.load_json(os.path.join("data", "remindme", "reminders.json"))

    @commands.command(name='futureme', pass_context=True)
    async def futureme(self, ctx):
        """Return list of future events set by remindme."""
        author = ctx.message.author
        author_reminders = []
        for r in self.reminders:
            if r["ID"] == author.id:
                if r["FUTURE"] >= int(time.time()):
                    author_reminders.append(r)
        if len(author_reminders) == 0:
            await self.bot.say("You have no future evnets.")
            return

        author_reminders = sorted(author_reminders, key=lambda x: x["FUTURE"])
        out = ["Here are your list of reminders:"]
        for i, r in enumerate(author_reminders, 1):
            out.append("**{}. {}**\n{}".format(
                i,
                humanfriendly.format_timespan(r["FUTURE"] - time.time()),
                r["TEXT"]
            ))
        try:
            await self.bot.send_message(
                author,
                "\n".join(out))
            await self.bot.say("Check your DM for all your future events.")
        except (discord.errors.Forbidden, discord.errors.NotFound):
            await self.bot.say("\n".join(out))
        except discord.errors.HTTPException:
            pass


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
    n = RemindmeExt(bot)
    bot.add_cog(n)
