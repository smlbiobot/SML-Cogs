"""
Clan War Readiness
"""

import argparse
import itertools
import os
from collections import defaultdict
from random import choice

import discord
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context

PATH = os.path.join("data", "cwready")
JSON = os.path.join(PATH, "settings.json")


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class CWReadiness:
    """Clan War Readinesx"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))



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
    n = CWReadiness(bot)
    bot.add_cog(n)
