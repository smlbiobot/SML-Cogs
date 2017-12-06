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
import urllib

import aiohttp
import discord
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
    return base + '?' + urllib.parse.urlencode(params)


class CRAPIKeyError(Exception):
    """Generic error"""
    pass


class ServerResponseError(CRAPIKeyError):
    """Server didn’t respond with valid json."""
    pass


class KeyIssueFailed(CRAPIKeyError):
    """Failed to issue key."""
    pass


class KeyRemoveFailed(CRAPIKeyError):
    """Failed to delete key."""


class ErrorMessages:
    """Error messages."""
    server_response_error = "No response from server. Please try again later."
    key_issue_failed = "Issuing key failed. Please contact support."
    server_invalid_error = "You cannot request a key from this server."
    key_remove_failed = "Removing key failed. Please contact support."


class MessageTemplates:
    """System messages."""
    key_renewed = "Key renewed for {member}. Please check your DM."
    key_found = "Key Found for {member}. Please check your DM."
    key_found_dm = "The cr-api.com developer key for {member} is: ```{key}```"
    channel_invalid = "You cannot request a key from this channel. Please run this command at {channel}."
    key_removed = "Key removed for {member} with token `{token}`."


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
            "New Key URL: {}".format(self.config.url.retrieve),
            "Renew key URL: {}".format(self.config.url.renew),
            "Drop Key URL: {}".format(self.config.url.drop),
            "Token: {}".format(self.config.token),
            "Discord server id: {}".format(self.config.server_id)
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

    async def get_user_key(self, member: discord.Member):
        """Retrieve token of a Discord member."""
        params = {
            "id": member.id,
            "name": member.name,
            "open_sesame": self.config.token
        }
        url = build_url(self.config.url.retrieve, params)
        data = await self.fetch_json(url)

        if data is None:
            raise ServerResponseError
        elif not data["success"]:
            raise KeyIssueFailed
        elif not data["token"]:
            raise KeyIssueFailed
        else:
            return data["token"]

    async def remove_user_key(self, token):
        """Retrieve token of a Discord member."""
        params = {
            "open_sesame": self.config.token,
            "token": token
        }
        url = build_url(self.config.url.drop, params)
        data = await self.fetch_json(url)

        if data is None:
            raise ServerResponseError
        else:
            print(data)
            return data

    async def renew_user_key(self, member: discord.Member, token):
        """Renew, replace existing, or unblock blacklised."""
        params = {
            "open_sesame": self.config.token,
            "id": member.id,
            "token": token,
            "action": "renew"
        }
        url = build_url(self.config.url.renew, params)
        data = await self.fetch_json(url)

        if data is None:
            raise ServerResponseError
        elif not data["success"]:
            raise KeyIssueFailed
        elif not data["token"]:
            raise KeyIssueFailed
        else:
            return data["token"]

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
            await self.bot.say(ErrorMessages.server_invalid_error)
            return False
        elif channel.id != self.cmd_channel_id:
            await self.bot.say(MessageTemplates.channel_invalid.format(
                channel=self.bot.get_channel(self.cmd_channel_id).mention))
            return False
        return True

    @crapikey.command(name="get", pass_context=True, no_pm=True)
    async def crapikey_get(self, ctx):
        """Get a key."""
        if not await self.validate_run_channel(ctx):
            return

        author = ctx.message.author
        try:
            key = await self.get_user_key(author)
        except ServerResponseError:
            await self.bot.say(ErrorMessages.server_response_error)
            return
        except KeyIssueFailed:
            await self.bot.say(ErrorMessages.key_issue_failed)
            return
        await self.bot.say(MessageTemplates.key_found.format(member=author))
        await self.bot.send_message(
            author,
            MessageTemplates.key_found_dm.format(member=author, key=key))

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="getuser", pass_context=True, no_pm=False)
    async def crapikey_getuser(self, ctx, member: discord.Member):
        """Retrieve the token of a Discord member."""
        try:
            key = await self.get_user_key(member)
        except ServerResponseError:
            await self.bot.say(ErrorMessages.server_response_error)
            return
        except KeyIssueFailed:
            await self.bot.say(ErrorMessages.key_issue_failed)
            return
        await self.bot.say(MessageTemplates.key_found.format(member=member))
        await self.bot.send_message(
            ctx.message.author,
            MessageTemplates.key_found_dm.format(member=member, key=key))

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="blacklist", pass_context=True, no_pm=False)
    async def crapikey_blacklist(self, ctx, member: discord.Member):
        """Black list a member’s token."""
        # Fetch token by member
        try:
            key = await self.get_user_key(member)
        except ServerResponseError:
            await self.bot.say(ErrorMessages.server_response_error)
            return
        except KeyIssueFailed:
            await self.bot.say(ErrorMessages.key_issue_failed)
            return

        # Remove token
        try:
            data = await self.remove_user_key(key)
        except CRAPIKeyError:
            await self.bot.say("Error.")
            return
        await self.bot.say(MessageTemplates.key_removed.format(member=member, token=key))

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="renew", pass_context=True, no_pm=False)
    async def crapikey_renew(self, ctx, member: discord.Member, key):
        """Renew a member’s token."""
        try:
            key = await self.renew_user_key(member, key)
        except ServerResponseError:
            await self.bot.say(ErrorMessages.server_response_error)
            return
        except KeyIssueFailed:
            await self.bot.say(ErrorMessages.key_issue_failed)
            return
        await self.bot.say(MessageTemplates.key_renewed.format(member=member))
        await self.bot.send_message(
            ctx.message.author,
            MessageTemplates.key_found_dm.format(member=member, key=key))

    async def fetch_json(self, url):
        data = None
        # print(url)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
        except aiohttp.ClientError:
            pass
        except json.JSONDecodeError:
            pass
        return data

    async def on_member_remove(self, member:discord.Member):
        """Remove key when member leaves"""
        # remove only if it happens on crapi server
        if str(member.server.id) != str(self.config.server_id):
            return
        try:
            key = await self.get_user_key(member)
        except ServerResponseError:
            print("Server response error.")
            return
        except KeyIssueFailed:
            print("Key issue failed.")
            return
        # Remove token
        try:
            data = await self.remove_user_key(key)
        except CRAPIKeyError:
            await self.bot.say("Error.")
            return
        print("Key for {} removed.".format(member))


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
