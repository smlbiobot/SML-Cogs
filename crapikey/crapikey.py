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

import json
import os
import urllib.parse as urlparse
from urllib.parse import urlencode

import aiohttp
import yaml
from __main__ import send_cmd_help
from box import Box
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "crapikey")
JSON = os.path.join(PATH, "settings.json")
YAML = os.path.join(PATH, "config.yaml")


def build_url(base, params):
    url_parts = list(urlparse.urlparse(base))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urlencode(query)
    return urlparse.urlunparse(url_parts)


class CRAPIKey:
    """Getting a developer key for cr-api.com"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Box(dataIO.load_json(JSON))
        self._config = None

    @property
    def config(self):
        if self._config is None:
            if os.path.exists(YAML):
                with open(YAML) as f:
                    self._config = Box(yaml.load(f), default_box=True)
        return self._config

    @checks.is_owner()
    @commands.group(pass_context=True, no_pm=False)
    async def crapikeyset(self, ctx):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @checks.is_owner()
    @crapikeyset.command(name="config", pass_context=True, no_pm=False)
    async def crapikeyset_config(self, ctx, cmd=None):
        """Upload or see config.

        cmd:None       show config via DM.
        cmd:upload     Upload config.yaml
        cmd:channel    Set channel for key issues
        """
        if cmd is None:
            await self.send_config(ctx)
        elif cmd == 'upload':
            await self.upload_config_prompt(ctx)

    async def send_config(self, ctx):
        """Send config as DM to user."""
        author = ctx.message.author
        if self.config is None:
            await self.bot.send_message(author, "Config is not set.")
            return
        o = [
            "CR-API Key Config",
            "New Key URL: {}".format(self.config.url.new_key),
            "Remove Key URL: {}".format(self.config.url.remove_key)
        ]
        await self.bot.send_message(ctx.message.channel, "Check your DM.")
        await self.bot.send_message(author, "\n".join(o))

    async def upload_config_prompt(self, ctx, timeout=60.0):
        """Prompt for upload config."""
        await self.bot.say(
            "Please upload family config yaml file. "
            "[Timeout: {} seconds]".format(timeout))
        attach_msg = await self.bot.wait_for_message(
            timeout=timeout,
            author=ctx.message.author)
        if attach_msg is None:
            await self.bot.say("Operation time out.")
            return
        if not len(attach_msg.attachments):
            await self.bot.say("Cannot find attachments.")
            return
        attach = attach_msg.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(YAML))

        self._config = None
        await self.send_config(ctx)

        if not attach_msg.channel.is_private:
            await self.bot.delete_message(attach_msg)

    @checks.is_owner()
    @crapikeyset.command(name="channel", pass_context=True, no_pm=False)
    async def crapikeyset_channel(self, ctx, channel=None):
        """Set a channel where keys can be issued."""
        self.settings["channel_id"] = ctx.message.channel.id
        self.settings["server_id"] = ctx.message.server.id
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Channel set.")

    @commands.group(pass_context=True)
    async def crapikey(self, ctx):
        """cr-api.com developer key"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @property
    def cmd_server_id(self):
        return self.settings.get("server_id")

    @property
    def cmd_channel_id(self):
        return self.settings.get("channel_id")

    async def validate_run_channel(self, ctx):
        """Validate command is run at desired channel."""
        server = ctx.message.server
        channel = ctx.message.channel
        if server.id != self.cmd_server_id:
            await self.bot.say("You cannot request a key from this server.")
            return False
        elif channel.id != self.cmd_channel_id:
            await self.bot.say(
                "You cannot request a key from this channel. "
                "Please run this command at {}".format(
                    self.bot.get_channel(self.cmd_channel_id).mention
                )
            )
            return False
        return True

    @crapikey.command(name="get", pass_context=True, no_pm=True)
    async def crapikey_get(self, ctx):
        """Get a key."""
        if not await self.validate_run_channel(ctx):
            return

        author = ctx.message.author

        params = {
            "id": author.id,
            "name": author.name
        }
        url = build_url(self.config.url.new_key, params)
        data = await self.fetch_json(url)

        if data is None:
            await self.bot.say("Error fetching key. Please try again later.")
        elif not data["success"]:
            await self.bot.say("Issuing key failed. Please contact support.")
        else:
            await self.bot.say("Key issued. Please check your DM.")
            await self.bot.send_message(
                author,
                "Your cr-api.com developer key is: ```{}```".format(data["key"])
            )

    @crapikey.command(name="remove", aliases=["rm"], pass_context=True, no_pm=True)
    async def crapikey_remove(self, ctx):
        """Remove a key."""
        if not await self.validate_run_channel(ctx):
            return

        author = ctx.message.author

        params = {
            "id": author.id,
            "name": author.name,
            "action": "drop"
        }
        url = build_url(self.config.url.new_key, params)
        data = await self.fetch_json(url)

        if data is None:
            await self.bot.say("Error fetching key. Please try again later.")
        elif not data["success"]:
            await self.bot.say("Key removal failed. Please contact support.")
        else:
            await self.bot.say("Key successfully removed.")

    async def fetch_json(self, url):
        data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
        except aiohttp.ClientError:
            pass
        except json.JSONDecodeError:
            pass
        return data


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
    n = CRAPIKey(bot)
    bot.add_cog(n)
