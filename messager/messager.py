"""
Message utility:
- send message to channel.
"""

import asyncio
import os
from collections import defaultdict

import discord
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "messager")
JSON = os.path.join(PATH, "settings.json")

TASK_INTERVAL = 1


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Messager:
    """Allow user to send message to channel."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.loop = asyncio.get_event_loop()

    def __unload(self):
        """Remove task when unloaded."""
        pass

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)
        return True

    def get_emoji(self, name):
        for emoji in self.bot.get_all_emojis():
            if emoji.name == str(name):
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    @commands.command(aliases=["sendc"], pass_context=True, no_pm=True)
    async def send_channel(self, ctx, channel: discord.Channel, *, message: str = None):
        """Create timer.

        [p]timer 2019-08-31T18:00:00 "Sprint Event"
        """
        fr_channel = ctx.message.channel
        to_channel = channel

        em = discord.Embed(
            title="Message",
            description="From: {author} - {message}".format(
                author=ctx.message.author.mention,
                message=message,
            ),
            color=discord.Color.blue(),
        )
        em.set_footer(
            text="#{channel}".format(channel=fr_channel)
        )

        await self.bot.send_message(to_channel, embed=em)


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
    n = Messager(bot)
    bot.add_cog(n)
