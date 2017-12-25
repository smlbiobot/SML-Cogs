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

import datetime as dt
import json
import os
import pprint
from random import choice

import aiohttp
import discord
import yaml
from box import Box
from cogs.utils import checks
from cogs.utils.chat_formatting import box, bold
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "crapikey")
JSON = os.path.join(PATH, "settings.json")
YAML = os.path.join(PATH, "config.yaml")


def build_url(base, endpoint, params):
    """Build URL using base, endpoint and params.

    Args
     :endpoint: text format string
     :params: dict
    """
    url = base + endpoint.format(params)
    return url


def random_discord_color():
    """Return random color as an integer."""
    color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
    color = int(color, 16)
    return discord.Color(value=color)


class CRAPIKeyError(Exception):
    """Generic error"""
    pass


class ServerError(CRAPIKeyError):
    """Non 200 responses"""

    def __init__(self, data=None):
        self.data = data


class ServerResponseError(CRAPIKeyError):
    """Server didn’t respond with valid json."""
    pass


class KeyIssueFailed(CRAPIKeyError):
    """Failed to issue key."""
    pass


class KeyRemoveFailed(CRAPIKeyError):
    """Failed to delete key."""


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
            await self.bot.send_cmd_help(ctx)

    async def send_config(self, ctx):
        """Send config as DM."""
        author = ctx.message.author
        if self.config is None:
            await self.bot.send_message(author, "Config is not set.")
            return

        pp = pprint.PrettyPrinter(indent=2)
        await self.bot.send_message(author, box(pp.pformat(self.config)))
        await self.bot.send_message(ctx.message.channel, "Check your DM.")

    @checks.is_owner()
    @crapikeyset.command(name="config", pass_context=True, no_pm=False)
    async def crapikeyset_config(self, ctx):
        """Show config via DM."""
        await self.send_config(ctx)

    @checks.is_owner()
    @crapikeyset.command(name="uploadconfig", pass_context=True, no_pm=False)
    async def crapikeyset_uploadconfig(self, ctx):
        """Upload config."""
        attachments = ctx.message.attachments
        if len(attachments) == 0:
            await self.bot.say("You must send config as attachment with the command.")
            return

        url = attachments[0]["url"]
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(YAML))

        self._config = None
        await self.send_config(ctx)

        if not ctx.message.channel.is_private:
            await self.bot.delete_message(ctx.message)

    async def fetch_json(self, url):
        """Request json from url."""
        data = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        raise ServerError(data)
        except aiohttp.ClientError:
            raise ServerError(data)
        except json.JSONDecodeError:
            raise ServerError(data)
        return data

    async def key_create(self, member: discord.Member):
        """Retrieve token of a Discord member."""
        params = {
            "discord_id": member.id,
            "open_sesame": self.config.open_sesame
        }
        url = build_url(self.config.base, self.config.endpoints.create, params)

        data = await self.fetch_json(url)
        return data

    async def key_renew(self, member: discord.Member):
        """Retrieve token of a Discord member."""
        params = {
            "discord_id": member.id,
            "open_sesame": self.config.open_sesame
        }
        url = build_url(self.config.base, self.config.endpoints.renew, params)
        data = await self.fetch_json(url)
        return data

    async def key_token2id(self, token):
        """Convert token to discord id"""
        params = {
            "token": token,
            "open_sesame": self.config.open_sesame
        }
        url = build_url(self.config.base, self.config.endpoints.token2id, params)
        data = await self.fetch_json(url)
        return data

    async def key_delete(self, token):
        """Delete token of a Discord member."""
        params = {
            "open_sesame": self.config.open_sesame,
            "token": token
        }
        url = build_url(self.config.base, self.config.endpoints.delete, params)
        data = await self.fetch_json(url)
        return data

    async def key_blacklist(self, token):
        """Blacklist a token"""
        params = {
            "open_sesame": self.config.open_sesame,
            "token": token
        }
        url = build_url(self.config.base, self.config.endpoints.blacklist, params)
        data = await self.fetch_json(url)
        return data

    async def key_listall(self):
        """List all keys."""
        params = {
            "open_sesame": self.config.open_sesame
        }
        url = build_url(self.config.base, self.config.endpoints.listall, params)
        data = await self.fetch_json(url)
        return data

    @commands.group(pass_context=True)
    async def crapikey(self, ctx):
        """cr-api.com developer key"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    def valid_server(self, server):
        """Return true if comamnd can be run."""
        for server_id in self.config.server_ids:
            if str(server.id) == str(server_id):
                return True
        return False

    def valid_channel(self, channel):
        """Return true if command can be run on channel."""
        return channel.name == self.config.channels.endusers

    async def validate_run_channel(self, ctx):
        """Validate command is run at desired channel."""
        server = ctx.message.server
        channel = ctx.message.channel

        if not self.valid_server(server):
            await self.bot.say("You cannot request a key from this server.")
            return False
        elif not self.valid_channel(channel):
            channel = discord.utils.get(server.channels, name=self.config.channels.endusers)
            await self.bot.say(
                "You cannot request a key from this channel. "
                "Please run this command at {channel}.".format(
                    channel=channel.mention))
            return False
        return True

    async def server_log(self, ctx, action, data=None):
        """Send server log to designated channel."""
        if data is None:
            data = '_'
        em = discord.Embed(title="CRAPIKey", description=action, color=discord.Color.red())
        if ctx is not None:
            em.add_field(name="Author", value=ctx.message.author)
            em.add_field(name="Author ID", value=ctx.message.author.id)
            em.add_field(name="Channel", value=ctx.message.channel.mention)
        em.add_field(name="Response", value=data)
        channel = discord.utils.get(ctx.message.server.channels, name=self.config.channels.log)
        await self.bot.send_message(channel, embed=em)

    @crapikey.command(name="get", pass_context=True, no_pm=True)
    async def crapikey_get(self, ctx):
        """Get a key."""
        if not await self.validate_run_channel(ctx):
            return

        author = ctx.message.author
        data = None
        try:
            data = await self.key_create(author)
            token = data['token']
            await self.bot.say("Key found for {member}. Please check your DM.".format(member=author))
            await self.bot.send_message(
                author,
                "The cr-api.com developer key for {member} is: ```{token}```".format(
                    member=author, token=token))
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Get Key", data)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="getuser", pass_context=True, no_pm=False)
    async def crapikey_getuser(self, ctx, member: discord.Member):
        """Retrieve the token of a Discord member."""
        author = ctx.message.author
        data = None
        try:
            data = await self.key_create(member)
            token = data['token']
            await self.bot.say("Key found for {member}. Please check your DM.".format(member=member))
            await self.bot.send_message(
                author,
                "The cr-api.com developer key for {member} is: ```{token}```".format(
                    member=member, token=token))
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Get User’s Key: {} ({})".format(member, member.id), data)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="renew", pass_context=True, no_pm=False)
    async def crapikey_renew(self, ctx, member: discord.Member):
        """Rnew the token of a Discord member."""
        author = ctx.message.author
        data = None
        try:
            data = await self.key_renew(member)
            token = data['token']
            await self.bot.say("Key renewed for {member}. Please check your DM.".format(member=member))
            await self.bot.send_message(
                author,
                "The cr-api.com developer key for {member} is: ```{token}```".format(
                    member=member, token=token))
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Renew User’s Key: {} ({})".format(member, member.id), data)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="delete", pass_context=True, no_pm=False)
    async def crapikey_delete(self, ctx, token):
        """Delete token."""
        data = None
        try:
            data = await self.key_delete(token)
            if data.get('success'):
                await self.bot.say("Key deleted.")
            else:
                await self.send_error_message(ctx, data)
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Delete Token: {}".format(token), data)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="blacklist", pass_context=True, no_pm=False)
    async def crapikey_blacklist(self, ctx, token):
        """Black list a token."""
        data = None
        try:
            data = await self.key_blacklist(token)
            if data.get('success'):
                await self.bot.say("Key blacklisted.")
            else:
                await self.send_error_message(ctx, data)
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Blacklist Token: {}".format(token), data)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="token2user", pass_context=True, no_pm=False)
    async def crapikey_token2user(self, ctx, token):
        """Convert a token to a user."""
        data = None
        try:
            data = await self.key_token2id(token)
            id = data['id']
            member = ctx.message.server.get_member(id)
            await self.bot.say(
                "{member} ({id}) is assigned with this token `{token}`".format(
                    member=member.mention,
                    token=token,
                    id=id,
                )
            )
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.server_log(ctx, "Token2User: {}".format(token), data)

    def key_display_str(self, key, member, show_token=False):
        """Return formatted output of a key."""
        default = '-'

        out = []

        out.append("{member} ({id})".format(
            member=bold(member),
            id=key.get('id', default)))

        registered = key.get('registered', default)
        if isinstance(registered, int):
            registered_iso = dt.datetime.utcfromtimestamp(registered / 1000).isoformat()
            registered_str = "{} / {}".format(registered, registered_iso)
        else:
            registered_str = '-'
        out.append("Registered: {}".format(registered_str))

        out.append("Last Request: {}".format(key.get('lastRequest', default)))
        out.append("Blacklisted: {}".format(key.get('blacklisted', default)))

        if show_token:
            out.append("Token: {}".format(key.get('token', default)))

        request_count = key.get('requestCount', default)
        request_count_str = ''
        if isinstance(request_count, dict):
            request_count_str = box('\n'.join(["{} : {:>10,}".format(k, v) for k, v in request_count.items()]), lang='python')

        out.append('Request Count: {}'.format(request_count_str))

        return '\n'.join(out)

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="listall", pass_context=True, no_pm=False)
    async def crapikey_listall(self, ctx):
        """List all keys."""
        data = None
        server = ctx.message.server
        try:
            data = await self.key_listall()
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        await self.bot.say('All CR-API Keys')

        default = '_'
        for key in data:

            id = key.get('id', default)
            if id == default:
                member = default
            else:
                member = server.get_member(id)

            await self.bot.say(self.key_display_str(key, member))

        await self.server_log(ctx, "List all")

    @checks.serverowner_or_permissions(manage_server=True)
    @crapikey.command(name="stats", pass_context=True, no_pm=False)
    async def crapikey_stats(self, ctx, member: discord.Member = None, show_token=False):
        """List stats of keys.

        [p]crapikey stats        | Total count
        [p]crapikey stats @SML   | Stats of a user
        [p]crapikey stats @SML 1 | Stats of a user w/ token
        """
        data = None
        try:
            data = await self.key_listall()
        except ServerError as e:
            await self.send_error_message(ctx, e.data)

        if member is None:
            await self.crapikey_stats_all(ctx, data)
        else:
            await self.crapikey_stats_member(ctx, data, member, show_token=show_token)

    async def crapikey_stats_all(self, ctx, data):
        """Show all stats."""
        total_keys = len(data)
        blacklisted = 0
        for key in data:
            if key.get('blacklisted'):
                blacklisted += 1

        await self.bot.say(
            "Total keys: {total_keys}\n"
            "Blacklisted: {blacklisted} ({blacklisted_ratio:.2%})".format(
                total_keys=total_keys,
                blacklisted=blacklisted,
                blacklisted_ratio=blacklisted / total_keys
            )
        )
        await self.server_log(ctx, "Stats")

    async def crapikey_stats_member(self, ctx, data, member: discord.Member, show_token=False):
        """Show stats about a member."""
        found_key = None
        for key in data:
            if key['id'] == member.id:
                found_key = key
                break

        if found_key is None:
            await self.bot.say("Cannot find associated key with {}".format(member))
            return

        await self.bot.say(self.key_display_str(found_key, member, show_token=show_token))

    async def send_error_message(self, ctx, data=None):
        """Send error message to channel."""
        if data is None:
            await self.bot.say("Unknown server error.")
            return
        code = data.get('code')
        message = data.get('message')
        if code is None:
            code = 'Unknown'
        if message is None:
            message = '_'
        message = message.replace('http://discord.me/cr_api', '<http://discord.me/cr_api>')
        await self.bot.say(
            "Error \n"
            "Code: {code}\n"
            "Message: {message}".format(code=code, message=message)
        )

    async def on_member_remove(self, member: discord.Member):
        """Remove key when member leaves"""
        # remove only if it happens on crapi server
        if str(member.server.id) != str(self.config.crapi_server_id):
            return
        try:
            data = await self.key_create(member)
            token = data['token']
            # Remove token
            try:
                data = await self.key_delete(token)
                if data['success']:
                    print("Key for {} removed.".format(member))
                await self.server_log(None, "Member left: delete key", data)
            except ServerError:
                print("Server error.")
        except ServerError:
            print("Server error.")


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
