# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2019 SML

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
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "message_quote")
JSON = os.path.join(PATH, "settings.json")


class MessageQuote:
    """Member Management plugin for Red Discord bot."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot

    @commands.command(name="mq", pass_context=True)
    async def message_quote(self, ctx, message_id, channel: discord.Channel = None):
        """Quote a message by ID

        !mq 582794656560054272 #family-chat
        If channel is omitted, use current channel
        """
        if channel is None:
            channel = ctx.message.channel

        try:
            msg = await self.bot.get_message(channel, message_id)
        except discord.NotFound:
            await self.bot.say("Message not found.")
            return
        except discord.Forbidden:
            await self.bot.say("I do not have permissions to fetch the message")
            return
        except discord.HTTPException:
            await self.bot.say("Retrieving message failed")
            return

        if not msg:
            return

        ts = msg.timestamp

        out = [
            msg.content or '',
            "— {}, {}".format(
                msg.author.mention,
                ts.isoformat(sep=" ")
            )
        ]

        link = 'https://discordapp.com/channels/{server_id}/{channel_id}/{message_id}'.format(
            server_id=msg.server.id,
            channel_id=msg.channel.id,
            message_id=msg.id
        )

        em = discord.Embed(
            title="Quote",
            description="\n".join(out),
            url=link
        )

        if msg.attachments:
            url = msg.attachments[0].get('url')
            if url:
                em.set_image(url=url)

        em.set_footer(
            text=msg.server.name,
            icon_url=msg.server.icon_url
        )

        await self.bot.say(embed=em)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = MessageQuote(bot)
    bot.add_cog(n)
