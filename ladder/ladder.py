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
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from trueskill import Rating, rate_1vs1

PATH = os.path.join("data", "ladder")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "SERIES": {}
}


class Player:
    """Player in a game."""

    def __init__(self, discord_id, rating=None):
        if rating is None:
            rating = 1500
        self.rating = Rating(rating)
        self.discord_id = discord_id

    def to_dict(self):
        return {
            "rating": self.rating,
            "discord_id": self.discord_id
        }

    def from_dict(self, d):
        self.rating = d["rating"]
        self.discord_id = d["discord_id"]


class Game:
    """A match."""

    def __init__(self, player1=None, player2=None):
        self.player1 = player1
        self.player2 = player2

    def match_1vs1(self, winner: Player, loser: Player):
        """Match score reporting."""
        winner.rating, loser.rating = rate_1vs1(winner.rating, loser.rating)


class ServerSettings:
    """Server settings."""

    def __init__(self, server):
        """Server settings."""
        self.server = server
        self.ladders = []
        self._model = None

    @property
    def model(self):
        return self._model


class LadderException(Exception):
    pass


class SeriesExist(LadderException):
    pass


class NoSuchSeries(LadderException):
    pass


class NoSuchPlayer(LadderException):
    pass


class Settings:
    """Ladder settings."""
    server_default = {
        "series": {}
    }
    series_default = {
        "matches": {},
        "players": {}
    }

    def __init__(self, bot):
        self.bot = bot
        self.model = dataIO.load_json(JSON)

    def save(self):
        """Save settings to file."""
        dataIO.save_json(JSON, self.model)

    def server_model(self, server):
        """Return model by server."""
        self.check_server(server)
        return self.model[server.id]

    def check_server(self, server):
        """Create server settings if required."""
        if server.id not in self.model:
            self.model[server.id] = self.server_default
        self.save()

    def get_series(self, server, name):
        if name not in self.server_model(server)["series"]:
            raise NoSuchSeries
        return self.server_model(server)["series"][name]

    def get_player(self, server, name, player: discord.Member):
        """Check player settings."""
        self.check_server(server)
        try:
            series = self.get_series(server, name)
            if player.id not in series["players"]:
                return False
        except NoSuchSeries:
            raise NoSuchSeries

        return True

    def init_server(self, server):
        """Initialize server settings to default"""
        self.model[server.id] = self.server_default
        self.save()

    def create(self, server, name, *players: discord.Member):
        """Create new ladder by name"""
        series = self.server_model(server)["series"]
        if name in series:
            raise SeriesExist
        series[name] = self.series_default.copy()
        self.add_players(*players)
        self.save()

    def add_players(self, server, name, *players: discord.Member):
        series = self.get_series(server, name)
        for player in players:
            if player.id not in series["players"]:
                series["players"][player.id] = Player(player.id, rating=1000).to_dict()
        self.save()



class Ladder:
    """Ladder ranking system.

    Based on http://www.moserware.com/2010/03/computing-your-skill.html
    http://trueskill.org/

    Reuirements:
    pip3 install trueskill
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Settings(bot)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def ladderset(self, ctx):
        """Set ladder settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @ladderset.command(name="create", pass_context=True)
    async def ladderset_create(self, ctx, name, *players: discord.Member):
        """Create a new series.

        Creates a new ladder series and optionally initialize with players.
        """
        server = ctx.message.server
        try:
            self.settings.create(server, name, *players)
        except SeriesExist:
            await self.bot.say("There is an existing series with that name already.")
            return
        await self.bot.say("Series added.")

    @ladderset.command(name="addplayers", pass_context=True)
    async def ladderset_addplayers(self, ctx, name, *players: discord.Member):
        """Add players to an existing series."""
        server = ctx.message.server
        try:
            self.settings.add_players(server, name, *players)
        except NoSuchSeries:
            await self.bot.say("There is no series with that name.")
            return
        await self.bot.say("Successfully added players.")

    @commands.group(pass_context=True)
    async def ladder(self, ctx):
        """Ladder anking system using TrueSkills."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @ladder.command(name="register", pass_context=True)
    async def ladder_register(self, ctx, name):
        """Allow player to self-register to system."""
        server = ctx.message.server
        author = ctx.message.author
        self.check_player(server, author)


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
    n = Ladder(bot)
    bot.add_cog(n)
