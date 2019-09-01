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

import asyncio
import datetime as dt
import os
from collections import defaultdict

import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "timer")
JSON = os.path.join(PATH, "settings.json")

MANAGE_ROLE_ROLES = ['Bot Commander']

TASK_INTERVAL = 1


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Timer:
    """Brawl Stars API"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._team_config = None
        self.loop = asyncio.get_event_loop()
        self.task = self.loop.create_task(self.auto_tasks())

    def __unload(self):
        """Remove task when unloaded."""
        try:
            self.task.cancel()
        except Exception:
            pass

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    def get_emoji(self, name):
        for emoji in self.bot.get_all_emojis():
            if emoji.name == str(name):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    async def auto_tasks(self):
        try:
            while True:
                if self == self.bot.get_cog("Timer"):
                    self.loop.create_task(
                        self.update_timers()
                    )
                    await asyncio.sleep(TASK_INTERVAL)
        except asyncio.CancelledError:
            pass

    async def update_timers(self):
        """Update timers per config"""

    @checks.mod_or_permissions()
    @commands.command()
    async def timer(self, til: str, name: str = None):
        """Create timer.

        [p]timer 2019-08-31T18:00:00 "Sprint Event"
        """
        try:
            til = dt.datetime.strptime(til, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            await self.bot.send("Invalid format for time. Must be `2019-08-31T18:00:00` format")
            return

        now = dt.datetime.utcnow()

        if now > til:
            await self.bot.send("TIL has already past. Please specify a time in the future.")
            return

        em = discord.Embed(
            title=name or "Countdown",
            description=til.strftime('%Y-%m-%dT%H:%M:%S')
        )

        delta = til - now
        total = int(delta.total_seconds())

        days, remainder = divmod(total, 3600 * 24)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        em.add_field(
            name="Left",
            value="{days} days {hours} hours {minutes} minutes {seconds} seconds".format(
                days=days, hours=hours, minutes=minutes, seconds=seconds,
            )
        )

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
    n = Timer(bot)
    bot.add_cog(n)
