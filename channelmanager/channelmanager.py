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
from collections import defaultdict

import discord
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from discord import InvalidArgument, Forbidden, HTTPException
from discord.ext import commands

PATH = os.path.join("data", "channelmanager")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ChannelManager:
    """Channel Manager."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(aliases=['chm'], pass_context=True)
    @checks.mod_or_permissions()
    async def channelman(self, ctx):
        """Channel Manager."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @channelman.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_channels=True)
    async def create(self, ctx):
        """Create Channel."""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @create.command(name="user", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_channels=True)
    async def create_user(self, ctx, name, user: discord.Member, after: discord.Channel = None):
        """User specific channel.

        Everyone can read but only one person can write.
        """
        server = ctx.message.server
        channel = await self.bot.create_channel(
            server,
            name,
            discord.ChannelPermissions(
                target=server.default_role,
                overwrite=discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False
                )
            ),
            discord.ChannelPermissions(
                target=user,
                overwrite=discord.PermissionOverwrite(
                    send_messages=True
                )
            ),
            type=discord.ChannelType.text
        )

        await self.bot.say("Channel created.")

    @channelman.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_channels=True)
    async def move(self, ctx):
        """Move channel."""
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @move.command(name="after", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_channels=True)
    async def move_after(self, ctx, channel: discord.Channel, after_channel: discord.Channel):
        """Move channel after a channel."""
        try:
            await self.bot.move_channel(channel, after_channel.position + 1)
            await self.bot.say("Channel moved.")
        except (InvalidArgument, Forbidden, HTTPException) as err:
            await self.bot.say("Move channel failed. " + str(err))


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
    n = ChannelManager(bot)
    bot.add_cog(n)
