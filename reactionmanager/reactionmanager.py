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
from cogs.utils import checks
from cogs.utils.chat_formatting import bold
from cogs.utils.chat_formatting import escape_mass_mentions
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands

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
            await self.bot.send_cmd_help(ctx)

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
            await self.bot.send_cmd_help(ctx)
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
    async def rm_get(self, ctx, channel: discord.Channel, message_id, *, args=None):
        """Display list of reactions added by users.

        Options:
        -id output ids
        """
        message = await self.bot.get_message(channel, message_id)

        if message is None:
            await self.bot.say("Cannot find that message id.")
            return

        output_id = False
        id_only = False
        if args:
            output_id = '-id' in args
            id_only = '--idonly' in args

        out = await self.get_reactions(message, exclude_self=True, output_id=output_id)

        # with open('/Users/sml/Desktop/emote_out.txt', 'w') as f:
        #     f.write('\n'.join(out))

        for page in pagify('\n'.join(out), shorten_by=100):
            # print(page)
            if page:
                await self.bot.say(page)

    @reactionmanager.command(name="getserver", pass_context=True, no_pm=True)
    @checks.is_owner()
    async def rm_getserver(self, ctx, server_name, channel_name, message_id, exclude_self=True):
        """Display list of reactions added by users."""
        server = discord.utils.get(self.bot.servers, name=server_name)
        channel = discord.utils.get(server.channels, name=channel_name)

        message = await self.bot.get_message(channel, message_id)
        if message is None:
            await self.bot.say("Cannot find that message id.")
            return

        out = await self.get_reactions(message, exclude_self=exclude_self)

        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)

    async def get_reactions(self, message, exclude_self=True, output_id=False):
        title = message.channel.name
        description = message.content

        out = [
            bold('Channel: {}'.format(title)),
            escape_mass_mentions(description)
        ]

        server = message.server

        total_count = 0

        reaction_votes = []

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

            valid_users = sorted(valid_users, key=lambda u: u.display_name.lower())
            user_ids = [u.id for u in valid_users]
            members = []
            for uid in user_ids:
                member = server.get_member(uid)
                if member:
                    members.append(member)
                    total_count += 1
            users_str = ', '.join([m.display_name for m in members])
            users_ids = ''
            if output_id:
                users_ids = ', '.join([m.id for m in members])
            count = len(valid_users)
            reaction_votes.append({
                "emoji": emoji,
                "count": count,
                "users_str": users_str,
                'users_ids': users_ids
            })

        for v in reaction_votes:
            emoji = v['emoji']
            count = v['count']
            ratio = count / total_count
            users_str = v['users_str']
            users_ids = v['users_ids']
            value = '{}: **{}** ({:.2%}): {}'.format(emoji, count, ratio, users_str)
            if output_id:
                value += '| {}'.format(users_ids)
            out.append(value)

        return out


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
