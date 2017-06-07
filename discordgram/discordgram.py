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
import re

from discord import Message
from discord.ext import commands

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "discordgram")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "CHANNEL": None,
    "MESSAGES": []
}


class DGMessage:
    """Discordgram message."""

    def __init__(self, message: Message, id, bot_msg: Message):
        """Init."""
        self.id = id
        self.message_id = message.id
        self.author_id = message.author.id
        self.bot_message_id = bot_msg.id

    @property
    def data(self):
        """Return json object."""
        return {
            "ID": self.id,
            "MESSAGE_ID": self.message_id,
            "AUTHOR_ID": self.author_id,
            "BOT_MESSAGE_ID": self.bot_message_id
        }


class Discordgram:
    """Discordgram utility functions."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True, aliases=['sdg'])
    async def setdiscordgram(self, ctx):
        """Set Discordgram settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setdiscordgram.command(name="channel", pass_context=True)
    async def setdiscordgram_channel(self, ctx):
        """Set Discordgram channel.

        Running in enabled channel will disable the channel.
        Running in another channel will replace the previous channel.
        """
        server = ctx.message.server
        channel = ctx.message.channel
        if server.id not in self.settings:
            self.settings[server.id] = SERVER_DEFAULTS
        channelid = self.settings[server.id]["CHANNEL"]
        if channelid is not None:
            previous_channel = self.bot.get_channel(channelid)
            await self.bot.say(
                "Removed Discordgram from {}".format(previous_channel.mention))
        if channelid == channel.id:
            self.settings[server.id]["CHANNEL"] = None
        else:
            self.settings[server.id]["CHANNEL"] = channel.id
            await self.bot.say(
                "Discordgram channel set to {}.".format(channel.mention))
        dataIO.save_json(JSON, self.settings)

    async def on_message(self, message):
        """Monitor activity if messages posted in Discordgram channel."""
        server = message.server
        channel = message.channel
        author = message.author
        attachments = message.attachments
        if server is None:
            return
        if server.id not in self.settings:
            return
        if channel.id != self.settings[server.id]["CHANNEL"]:
            return
        if author is server.me:
            return
        if not attachments:
            await self.bot.delete_message(message)
            # await self.bot.send_message(
            #     channel,
            #     "{} This channel is for image uploads only."
            #     " Message deleted.".format(
            #         author.mention))
            return

        dgm_id = len(self.settings[server.id]["MESSAGES"])

        footer_text = (
            ":: Type `!dgr {} <reply message>` "
            "to reply to {}’s post.".format(
                dgm_id, author.display_name)
        )

        bot_msg = await self.bot.send_message(channel, footer_text)

        dgm = DGMessage(message, dgm_id, bot_msg)
        self.settings[server.id]["MESSAGES"].append(dgm.data)
        dataIO.save_json(JSON, self.settings)

        # await self.bot.send_message(channel, embed=em)
        # await self.bot.delete_message(message)

        # await self.bot.send_message(
        #     channel,
        #     "Server: {}, Channel: {}, Author: {}".format(server, channel, author))

    @commands.command(
        pass_context=True,
        name="discordgramreply", aliases=["dgreply", "dgr"])
    async def discordgramreply(self, ctx, id, *, msg):
        """Reply to a Discordgram by ID."""
        author = ctx.message.author
        server = ctx.message.server

        if server.id not in self.settings:
            return
        if not id.isdigit():
            await self.bot.say("id must be a number.")
            return

        id = int(id)
        messages = self.settings[server.id]["MESSAGES"]
        if id >= len(messages):
            await self.bot.say("That is not a valid Discordgram id.")
            return
        message = messages[id]
        channel_id = self.settings[server.id]["CHANNEL"]
        channel = self.bot.get_channel(channel_id)

        bot_msg = await self.bot.get_message(
            channel, message["BOT_MESSAGE_ID"])

        transformations = {
            '@everyone': '@\u200beveryone',
            '@here': '@\u200bhere'
        }
        def repl2(obj):
            return transformations.get(obj.group(0), '')
        pattern = re.compile('|'.join(transformations.keys()))
        msg = pattern.sub(repl2, msg)

        comment = "**{}:** {}".format(author.display_name, msg)

        prev_content = bot_msg.clean_content.rsplit('::', 1)
        content = "{}\n{}\n\n::{}".format(
            prev_content[0].rstrip(),
            comment.rstrip(),
            prev_content[1].rstrip())
        await self.bot.edit_message(bot_msg, new_content=content)


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
    n = Discordgram(bot)
    bot.add_cog(n)
