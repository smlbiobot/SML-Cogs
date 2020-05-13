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
import asyncio
import os
from collections import defaultdict

import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "todo")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ToDoCog:
    """SML utilities"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @checks.is_owner()
    @commands.group(pass_context=True)
    async def todoset(self, ctx):
        """ToDo Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @todoset.command(name="channel", pass_context=True)
    async def todoset_channel(self, ctx, channel: discord.Channel = None):
        """Set channel for tasks"""
        if channel is None:
            channel = ctx.message.channel
        self.settings["task_channel_id"] = channel.id
        dataIO.save_json(JSON, self.settings)
        message = await self.bot.say("Channel set")
        await asyncio.sleep(5)
        await self.bot.delete_message(ctx.message)
        await self.bot.delete_message(message)

    @checks.mod_or_permissions()
    @commands.command(name="todo", pass_context=True)
    async def todo(self, ctx, *, message):
        """
        Add a todo item
        :param message:
        :return:
        """
        channel_id = self.settings.get('task_channel_id')
        server = ctx.message.server
        channel = server.get_channel(channel_id)

        em = discord.Embed(
            title=message,
            color=discord.Color.blue()
        )
        message = await self.bot.send_message(channel, embed=em)
        await self.bot.add_reaction(message, "✅")

    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        if message.channel.id != self.settings.get('task_channel_id'):
            return

        if user.bot:
            return

        if reaction.emoji != "✅":
            return

        em = message.embeds[0]
        new_embed = discord.Embed.from_data(em)
        new_embed.color = discord.Color.green()

        await self.bot.edit_message(
            message, embed=new_embed
        )


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
    n = ToDoCog(bot)
    bot.add_cog(n)
