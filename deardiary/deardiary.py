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
from discord import Message
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH_LIST = ['data', 'deardiary']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")

class DearDiary:
    """Dear Diary.

    Logs dear diary entries from chat.
    Logs in the bakcground automatically
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    async def on_message(self, message: Message):
        """Checks message for dear diary. Logs if found."""
        author = message.author
        server = message.server
        if server is None:
            return
        if author is server.me:
            return
        if "dear diary" not in message.content.lower():
            return
        if server.id not in self.settings:
            self.settings[server.id] = {
                "diary": {},
                "server_name": server.name,
                "server_id": server.id
            }
        timestamp = message.timestamp
        self.settings[server.id]["diary"][timestamp] = {
            "timestamp": str(message.timestamp),
            "author": message.author,
            "author_id": author.id,
            "author_name": author.display_name,
            "content": message.content
        }
        dataIO.save_json(JSON, self.settings)


def check_folders():
    if not os.path.exists(PATH):
        os.mkdir(PATH)

def check_files():
    if not dataIO.is_valid_json(JSON):
        defaults = {}
        dataIO.save_json(JSON, defaults)

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(DearDiary(bot))
