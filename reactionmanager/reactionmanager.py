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
import datetime as dt
from collections import defaultdict
from discord.ext import commands

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, bold, escape_mass_mentions
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "reactionmanager")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ReactionManager:

    def __init__(self, bot):
        """Reaction Management."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(aliases=['rm'], pass_context=True, no_pm=True)
    async def reactionmanager(self, ctx):
        """Reaction Manager."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @reactionmanager.command(name='add', pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def rm_add(self, ctx, *args):
        """Add reactions to a message by message id.

        Add reactions to a specific message id
        [p]rm add 123456 :white_check_mark: :x: :zzz:

        Add reactions to the last message in channel
        [p]rm add :white_check_mark: :x: :zzz:
        """
        channel = ctx.message.channel

        if not len(args):
            await send_cmd_help(ctx)
            return

        has_message_id = args[0].isdigit()

        emojis = args[1:] if has_message_id else args
        message_id = args[0] if has_message_id else None

        if has_message_id:
            try:
                message = await self.bot.get_message(channel, message_id)
            except discord.NotFound:
                await self.bot.say("Cannot find message with that id.")
                return
        else:
            # use the 2nd last message because the last message would be the command
            messages = []
            async for m in self.bot.logs_from(channel, limit=2):
                messages.append(m)

            # messages = [m async for m in self.bot.logs_from(channel, limit=2)]
            message = messages[1]

        for emoji in emojis:
            try:
                await self.bot.add_reaction(message, emoji)
            except discord.HTTPException:
                # reaction add failed
                pass
            except discord.Forbidden:
                await self.bot.say(
                    "I don’t have permission to react to that message.")
                break
            except discord.InvalidArgument:
                await self.bot.say("Invalid arguments for emojis")
                break

        await self.bot.delete_message(ctx.message)

    @reactionmanager.command(name="remove", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def rm_remove(self, ctx, number: int):
        """Remove reactions from last X messages in the channel."""
        channel = ctx.message.channel
        author = ctx.message.author
        server = author.server
        has_permissions = channel.permissions_for(server.me).manage_messages
        to_manage = []

        if not has_permissions:
            await self.bot.say("I’m not allowed to remove reactions.")
            return

        async for message in self.bot.logs_from(channel, limit=number + 1):
            to_manage.append(message)

        await self.remove_reactions(to_manage)

    async def remove_reactions(self, messages):
        """Remove reactions."""
        for message in messages:
            await self.bot.clear_reactions(message)

    @reactionmanager.command(name="get", pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def rm_get(self, ctx, channel: discord.Channel, message_id, exclude_self=True):
        """Display list of reactions added by users."""
        message = await self.bot.get_message(channel, message_id)

        if message is None:
            await self.bot.say("Cannot find that message id.")
            return

        title = message.channel.name
        description = message.content

        out = [
            bold('Channel: {}'.format(title)),
            escape_mass_mentions(description)
        ]

        for reaction in message.reactions:
            if reaction.custom_emoji:
                # <:emoji_name:emoji_id>
                emoji = '<:{}:{}>'.format(
                    reaction.emoji.name,
                    reaction.emoji.id)
            else:
                emoji = reaction.emoji

            reaction_users = await self.bot.get_reaction_users(reaction)
            valid_users = []
            for u in reaction_users:
                if exclude_self and u == self.bot.user:
                    continue
                valid_users.append(u)
            users = ', '.join([u.display_name for u in valid_users])
            name = emoji
            count = len(valid_users)
            value = '{}: {}: {}'.format(emoji, count, users)

            out.append(value)

        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)

        # delete command
        await self.bot.delete_message(ctx.message)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = ReactionManager(bot)
    bot.add_cog(n)
