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

import discord
from discord.ext import commands
from .utils import checks
from random import choice
from .utils.dataIO import dataIO
from .general import General
from __main__ import send_cmd_help
import os
import datetime


settings_path = "data/deck/settings.json"

cards = ['archers', 'arrows', 'baby-dragon', 'balloon', 'barbarian-hut', 
        'barbarians', 'battle-ram', 'bomb-tower', 'bomber', 'bowler',
        'cannon', 'clone', 'dark-prince', 'dart-goblin', 'electro-wizard',
        'elite-barbarians', 'elixir-collector', 'executioner', 'fire-spirits',
        'fireball', 'freeze', 'furnace', 'gems-1', 'gems-2', 'gems-3',
        'gems-4', 'gems-5', 'gems-6', 'gems', 'giant-skeleton', 'giant',
        'goblin-barrel', 'goblin-gang', 'goblin-hut', 'goblins', 'gold-1',
        'gold-2', 'gold-3', 'gold', 'golem', 'graveyard', 'guards', 'hog-rider', 
        'ice-golem', 'ice-spirit', 'ice-wizard', 'inferno-dragon',
        'inferno-tower', 'knight', 'lava-hound', 'lightning', 'lumberjack',
        'mega-minion', 'miner', 'mini-pekka', 'minion-horde', 'minions',
        'mirror', 'mortar', 'musketeer', 'pekka', 'poison', 'prince',
        'princess', 'rage', 'rocket', 'royal-giant', 'skeleton-army',
        'skeletons', 'soon', 'sparky', 'spear-goblins', 'tesla', 'the-log',
        'three-muskateers', 'tombstone', 'tornado', 'valkyrie', 'witch',
        'wizard', 'xbow', 'zap']


class Deck:
    """
    Saves a Clash Royale deck for a user and display them
    """

    def __init__(self, bot):
        self.bot = bot
        self.file_path = settings_path
        self.settings = dataIO.load_json(self.file_path)

    @commands.group(pass_context=True, no_pm=True)
    async def deck(self, ctx):
        """Clash Royale Decks"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @deck.command(name="set", pass_context=True, no_pm=True)
    async def _deck_set(self, ctx, *args):
        """Set a decklist for the user calling the command"""

        author = ctx.message.author
        server = ctx.message.server

        self.check_server_settings(server)
        self.check_member_settings(server, author)


        await.bot.say(str(set(args)))
        await.bot.say(str(set(cards)))
        
        if set(args) < set(cards):
            await self.bot.say("valid deck")
        else:
            await self.bot.say("invalid deck")




        

    def check_member_settings(self, server, member):
        """Init member section if necessary"""
        if member.id not in self.settings["Servers"][server.id]["Members"]:
            self.settings["Servers"][server.id]["Members"][member.id] = {
                "MemberID": member.id,
                "MemberDisplayName": member.display_name,
                "Decks": {} }
            self.save_settings()


    def check_server_settings(self, server):
        """Init server data if necessary"""
        if server.id not in self.settings["Servers"]:
            self.settings["Servers"][server.id] = { "ServerName": str(server),
                                                    "ServerID": str(server.id),
                                                    "Members": {} }
            self.save_settings()

    def save_settings(self):
        """Saves data to settings file"""
        dataIO.save_json(self.file_path, self.settings)

def check_folder():
    if not os.path.exists("data/deck"):
        print("Creating data/deck folder...")
        os.makedirs("data/deck")

def check_file():
    settings = {
        "Cards": cards,
        "Servers": {},
        "Decks": {}
    }
    f = settings_path
    if not dataIO.is_valid_json(f):
        print("Creating default deck settings.json...")
        dataIO.save_json(f, settings)

def setup(bot):
    check_folder()
    check_file()
    n = Deck(bot)
    bot.add_cog(n)

    
