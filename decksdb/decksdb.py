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

from collections import defaultdict

import aiohttp
import os
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
import aiofiles
from ruamel.yaml import YAML
from elasticsearch_async import AsyncElasticsearch

PATH = os.path.join("data", "decksdb")
JSON = os.path.join(PATH, "settings.json")

CONFIG_YAML = os.path.join(PATH, "config.yml")

yaml=YAML(typ='safe')

def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class DecksDB:
    """Clash Royale Decks database. Mostly for 12-win GC Decks search."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    async def es(self):
        """Return ES instance based on config"""
        async with aiofiles.open(CONFIG_YAML, mode="r") as f:
            doc = await f.read()
            data = yaml.load(doc)
        return AsyncElasticsearch(hosts=data.get('es_hosts', []))

    @commands.group(pass_context=True)
    async def decksdbset(self, ctx):
        """GC Decks Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @decksdbset.command(name="config", pass_context=True, no_pm=True)
    async def decksdbset_config(self, ctx):
        """Upload config yaml file. See config.example.yml for how to format it."""
        if len(ctx.message.attachments) == 0:
            await self.bot.say(
                "Please attach config yaml with this command. "
                "See config.example.yml for how to format it."
            )
            return

        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(CONFIG_YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(CONFIG_YAML))

        self.settings['config'] = CONFIG_YAML
        dataIO.save_json(JSON, self.settings)

        await self.bot.delete_message(ctx.message)

    @commands.group(pass_context=True)
    async def decksdb(self, ctx):
        """GC Decks"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @decksdb.command(name="gc12wins", aliases=[], pass_context=True, no_pm=True)
    async def decksdb_gc12wins(self, ctx):
        """GC Decks."""
        es = await self.es()
        await self.bot.say(await es.info())







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
    n = DecksDB(bot)
    bot.add_cog(n)
