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

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO



try:
    import google
except ImportError:
    raise ImportError("Please install the google package.") from None

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install the aiohttp package.") from None

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Please install the BeautifulSoup4 package.") from None

try:
    from imgurpython import ImgurClient
    from imgurpython.helpers import GalleryAlbum
except ImportError:
    raise ImportError("Please install the imgurpython package.") from None


PATH = os.path.join("data", "search")
JSON = os.path.join(PATH, "settings.json")


class Search:
    """Google API."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setsearch(self, ctx: Context):
        """Set search settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setsearch.group(name="imgur", pass_context=True)
    async def setsearch_imgur(self, ctx: Context):
        """Set imgur api settings."""
        if ctx.invoked_subcommand is None or\
                isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @setsearch_imgur.command(name="id", pass_context=True)
    async def setsearch_imgur_id(self, ctx: Context, id: str):
        """Set imgur client id."""
        if "imgur" not in self.settings:
            self.settings["imgur"] = {}
        self.settings["imgur"]["id"] = id
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Imgur client id set.")

    @setsearch_imgur.command(name="secret", pass_context=True)
    async def setsearch_imgur_secret(self, ctx: Context, secret: str):
        """Set imgur client secret."""
        if "imgur" not in self.settings:
            self.settings["imgur"] = {}
        self.settings["imgur"]["secret"] = secret
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Imgur client secret set.")

    @commands.group(pass_context=True, no_pm=True)
    async def search(self, ctx: Context):
        """Google."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @search.command(name="google", pass_context=True, no_pm=True)
    async def search_google(
            self, ctx: Context, search_str: str, lang='english', stop=1):
        """Google search and return URL results."""
        out = []
        await self.bot.send_typing(ctx.message.channel)
        for url in google.search(search_str, num=5, stop=stop):
            await self.bot.send_typing(ctx.message.channel)
            async with aiohttp.get(url) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")
                out.append(soup.title.string)
            out.append("<{}>\n".format(url))
            # out.append(gout)
        for page in pagify('\n'.join(out)):
            await self.bot.say(page)

    @search.command(name="googleimages", aliases=["image", "img"],
                    pass_context=True, no_pm=True)
    async def search_google_images(
            self, ctx: Context, search_str: str, stop=1):
        """Google search images."""
        out = []
        await self.bot.send_typing(ctx.message.channel)
        for url in google.search_images(search_str, num=5, stop=stop):
            await self.bot.send_typing(ctx.message.channel)
            async with aiohttp.get(url) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")
                out.append(soup.title.string)
            out.append("<{}>\n".format(url))
            # out.append(gout)
        for page in pagify('\n'.join(out)):
            await self.bot.say(page)

    @search.command(name="imgur", pass_context=True, no_pm=True)
    async def search_imgur(self, ctx: Context, query: str):
        """Imgur search."""
        search_id = 0

        try:
            client_id = self.settings["imgur"]["id"]
            client_secret = self.settings["imgur"]["secret"]
        except KeyError:
            await self.bot.say("Please set imgur id and secret.")
            return

        try:
            search_id = self.settings["imgur"]["search_id"]
        except KeyError:
            self.settings["imgur"]["search_id"] = 0

        count = 0
        max = 3
        client = ImgurClient(client_id, client_secret)
        results = client.gallery_search(query)
        for result in results:
            # await self.bot.say(str(dir(album)))
            count += 1
            if count < search_id:
                continue

            search_id = count + 1

            if result.is_album:
                img = client.get_image(result.cover)
            else:
                img = result
            await self.bot.say(str(img.link))
            self.settings["imgur"]["search_id"] = search_id
            dataIO.save_json(JSON, self.settings)
            break


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check file."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    bot.add_cog(Search(bot))
