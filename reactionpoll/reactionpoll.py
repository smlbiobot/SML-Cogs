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

import datetime as dt
import discord
import os
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "reactionpoll")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ReactionPoll:
    """Archive activity.

    General utility used for archiving message logs
    from one channel to another.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def check_server_settings(self, server):
        """Verify settings have all the keys."""

    @checks.mod_or_permissions()
    @commands.group(aliases=['rep'], pass_context=True, no_pm=True)
    async def reactionpoll(self, ctx):
        """Reaction polling utility."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.serverowner_or_permissions()
    @reactionpoll.command(name="init", pass_context=True, no_pm=True)
    async def reactionpoll_init(self, ctx):
        """Initialize server settings."""
        self.settings[ctx.message.server.id]["messages"] = {}
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Server setttings initialized.")

    @reactionpoll.command(name="add", pass_context=True, no_pm=True)
    async def reactionpoll_add(
            self, ctx, channel: discord.Channel, message_id=None):
        """Add message to track.

        message_id: the message to track
        """
        if message_id is None:
            await self.send_cmd_help(ctx)
            return

        server = ctx.message.server
        message = await self.bot.get_message(channel, message_id)

        em = await self.reaction_embed(message)

        embed_message = await self.bot.say(embed=em)

        self.settings[server.id]["messages"][message_id] = {
            'channel_id': channel.id,
            'message_id': message_id,
            'embed_channel_id': ctx.message.channel.id,
            'embed_message_id': embed_message.id
        }
        dataIO.save_json(JSON, self.settings)

        # await self.bot.delete_message(ctx.message)

    @reactionpoll.command(name="addserver", pass_context=True, no_pm=True)
    async def reactionpoll_add(
            self, ctx, server_name, channel_name, message_id=None):
        """Add message to track.

        message_id: the message to track
        """
        if message_id is None:
            await self.bot.send_cmd_help(ctx)
            return

        server = None
        for bot_server in self.bot.servers:
            if bot_server.name == server_name:
                server = bot_server

        if server is None:
            await self.bot.say("Cannot find that server.")
            return

        channel = discord.utils.get(server.channels, name=channel_name)
        if server is None:
            await self.bot.say("Cannot find that channel on that server.")
            return

        message = await self.bot.get_message(channel, message_id)

        em = await self.reaction_embed(message)

        embed_message = await self.bot.say(embed=em)

        self.settings[server.id]["messages"][message_id] = {
            'channel_id': channel.id,
            'message_id': message_id,
            'embed_channel_id': ctx.message.channel.id,
            'embed_message_id': embed_message.id
        }
        dataIO.save_json(JSON, self.settings)

    @reactionpoll.command(name="del", pass_context=True, no_pm=True)
    async def reactionpoll_del(self, ctx, message_id=None):
        """Remove message from being tracked."""
        if message_id is None:
            await self.bot.send_cmd_help(ctx)
            return

        server = ctx.message.server

        del self.settings[server.id]["messages"][message_id]
        dataIO.save_json(JSON, self.settings)

    async def on_reaction_add(self, reaction, user):
        """Monitor reactions if tracked."""
        message = reaction.message
        server = message.server
        # print('Reaction add: {}: {}'.format(server.id, message.id))
        if message.id not in self.settings[server.id]['messages']:
            return

        await self.update_reation_embed(server, message)

    async def on_reaction_remove(self, reaction, user):
        """Monitor reactions if tracked."""
        message = reaction.message
        server = message.server
        # print('Reaction remove: {}: {}'.format(server.id, message.id))
        if message.id not in self.settings[server.id]['messages']:
            return

        await self.update_reation_embed(server, message)

    async def update_reation_embed(self, server, message):
        """Update reation embeds."""
        print('Reaction update: {}: {}'.format(server.id, message.id))
        m = self.settings[server.id]['messages'][message.id]

        embed_channel = server.get_channel(m["embed_channel_id"])
        embed_message = await self.bot.get_message(
            embed_channel,
            m["embed_message_id"])

        reaction_channel = server.get_channel(m["channel_id"])
        reaction_message = await self.bot.get_message(
            reaction_channel,
            m["message_id"])

        em = await self.reaction_embed(reaction_message)
        await self.bot.edit_message(
            embed_message,
            new_content=dt.datetime.utcnow().isoformat(),
            embed=em)

    async def reaction_embed(self, message: discord.Message):
        """Discord Embed of a message reaction."""
        title = message.channel.name
        description = message.content
        em = discord.Embed(
            title=title,
            description=description)

        for reaction in message.reactions:
            if reaction.custom_emoji:
                # <:emoji_name:emoji_id>
                emoji = '<:{}:{}>'.format(
                    reaction.emoji.name,
                    reaction.emoji.id)
            else:
                emoji = reaction.emoji

            reaction_users = await self.bot.get_reaction_users(reaction)
            users = ' '.join([m.mention for m in reaction_users])
            name = emoji
            count = reaction.count
            value = '{}: {}'.format(count, users)

            em.add_field(name=name, value=value, inline=True)

        em.set_footer(
            text='ID: {} | Updated: {}'.format(
                message.id,
                dt.datetime.utcnow().isoformat()))
        return em


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
    n = ReactionPoll(bot)
    # bot.add_listener(n.on_reaction_add, "on_reaction_add")
    # bot.add_listener(n.on_reaction_remove, "on_reaction_remove")
    bot.add_cog(n)
