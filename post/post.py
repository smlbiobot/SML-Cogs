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

from collections import defaultdict

import aiohttp
import argparse
import discord
import os
import re
import yaml
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from io import StringIO

PATH = os.path.join("data", "post")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Post:
    """Post things from somewhere."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def parser(self):
        p = argparse.ArgumentParser('[p]post')

        p.add_argument(
            "--path",
            action="store",
            dest="path"
        )

        p.add_argument(
            "--url",
            action="store",
            dest="url"
        )

        p.add_argument(
            "--data",
            action="store",
            dest="data"
        )

        return p

    def parse_mentions(self, value, server=None):
        """Parse channel mentions"""
        if value is None:
            return None

        def channel_repl(matchobj):
            name = matchobj.group(1)
            channel = discord.utils.get(server.channels, name=name)
            if channel:
                return channel.mention
            else:
                return "#{}".format(name)

        return re.sub('#([A-Za-z0-9\-]+)', channel_repl, value)

    def parse_emoji(self, value):
        """Parse emojis."""
        if value is None:
            return None

        def emoji_repl(matchobj):
            name = matchobj.group(1)

            s = ':{}:'.format(name)

            for emoji in self.bot.get_all_emojis():
                if emoji.name == name:
                    s = '<:{}:{}>'.format(emoji.name, emoji.id)
                    break
            return s

        return re.sub(':([A-Za-z0-9\-_]+):', emoji_repl, value)



    @checks.mod_or_permissions()
    @commands.command(name="post", pass_context=True, no_pm=True)
    async def post(self, ctx, channel: discord.Channel, *args):
        """Post things to channel"""
        parser = self.parser()

        try:
            pa = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        data = None
        if pa.data:
            with open(os.path.join(PATH, pa.data)) as f:
                data = yaml.load(f)

        elif pa.url:
            async with aiohttp.ClientSession() as session:
                async with session.get(pa.url) as resp:
                    s = await resp.text()
                    with StringIO(s) as f:
                        data = yaml.load(f)

        elif pa.path:
            with open(pa.path) as f:
                data = yaml.load(f)

        if not data:
            await self.bot.say("No data found.")
            return

        for d in data.get('embeds', []):
            title = self.parse_emoji(d.get('title'))
            description = self.parse_emoji(d.get('description'))

            em = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.dark_blue()
            )

            image_url = d.get('image', {}).get('url')
            if image_url:
                em.set_image(url=image_url)

            fields = d.get('fields', [])
            if fields:
                for f in fields:
                    name = f.get('name')
                    value = f.get('value')
                    name = self.parse_emoji(name)
                    value = self.parse_mentions(value, server=ctx.message.server)
                    em.add_field(name=name, value=value)

            try:
                await self.bot.send_message(channel, embed=em)
            except Exception as e:
                print(e)


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
    n = Post(bot)
    bot.add_cog(n)
