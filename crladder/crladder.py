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
from box import Box
from cogs.utils import checks
from cogs.utils.chat_formatting import inline, bold
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from trueskill import Rating, rate_1vs1

PATH = os.path.join("data", "crladder")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "SERIES": {}
}


def normalize_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    return t


class Player:
    """Player in a game."""

    def __init__(self, discord_id=None, tag=None, rating=1500):
        """
        Player.
        :param discord_id: Discord user id.
        :param tag: Clash Royale player tag.
        :param rating: Initial rating.
        """
        if isinstance(rating, dict):
            self.rating = Rating(**rating)
        elif isinstance(rating, int):
            self.rating = Rating(mu=rating)
        elif isinstance(rating, float):
            self.rating = Rating(mu=rating)
        else:
            self.rating = Rating()
        self.discord_id = discord_id
        self.tag = normalize_tag(tag)

    def to_dict(self):
        return {
            "rating": {
                "mu": self.rating.mu,
                "sigma": self.rating.sigma,
            },
            "discord_id": self.discord_id,
            "tag": self.tag
        }

    @staticmethod
    def from_dict(d):
        # db = Box(d, default_box=True)
        if isinstance(d, dict):
            p = Player(**d)
        else:
            p = Player()
        print("dict", isinstance(d, dict))
        print("str", isinstance(d, str))
        # p = Player(discord_id=d.get('discord_id'), tag=d.get('tag'))
        # p.discord_id = db.discord_id
        # p.tag = db.tag
        # rating = db.rating
        # if rating:
        #     p.rating = Rating(mu=rating.mu, sigma=rating.sigma)
        return p


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
        self.crladders = []
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


class CannotFindPlayer(LadderException):
    pass


class ClashRoyaleAPI:
    def __init__(self, token):
        self.token = token


class Settings:
    """CRLadder settings."""
    server_default = {
        "series": {}
    }
    series_default = {
        "matches": {},
        "players": {},
        "status": "inactive"
    }
    series_status = ['active', 'inactive', 'completed']

    def __init__(self, bot):
        self.bot = bot
        model = dataIO.load_json(JSON)
        self.model = Box(model, default_box=True)

    def save(self):
        """Save settings to file."""
        dataIO.save_json(JSON, self.model)

    @property
    def auth(self):
        """cr-api.com Authentication token."""
        return self.model.auth

    @auth.setter
    def auth(self, value):
        self.model.auth = value
        self.save()

    def server_model(self, server):
        """Return model by server."""
        self.check_server(server)
        return self.model[server.id]

    def check_server(self, server):
        """Create server settings if required."""
        if server.id not in self.model:
            self.model[server.id] = self.server_default
        self.save()

    def get_all_series(self, server):
        """Get all series."""
        return self.server_model(server)["series"]

    def get_series(self, server, name):
        series = self.server_model(server)["series"].get(name)
        if series is None:
            raise NoSuchSeries
        else:
            return series
            # if name not in self.server_model(server)["series"]:
            #     raise NoSuchSeries
            # return self.server_model(server)["series"][name]

    def set_series_status(self, server, name, status):
        """
        Set series status.
        :param server: discord.Server instance.
        :param name: name of the series.
        :return:
        """
        series = self.get_series(server, name)
        series['status'] = status
        self.save()

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

    def create(self, server, name):
        """Create new series by name."""
        series = self.server_model(server)["series"]
        if name in series:
            raise SeriesExist
        series[name] = self.series_default.copy()
        self.save()

    def remove_series(self, server, name):
        """Remove series."""
        try:
            series = self.get_series(server, name)
        except NoSuchSeries:
            raise
        else:
            all_series = self.get_all_series(server)
            all_series.pop(name)
            self.save()

    def add_player(self, server, name, player: discord.Member, player_tag=None):
        """Add a player to a series."""
        series = self.get_series(server, name)
        if player.id not in series["players"]:
            series["players"][player.id] = Player(player.id, tag=player_tag, rating=1000).to_dict()
        self.save()

    def add_players(self, server, name, *players: discord.Member):
        series = self.get_series(server, name)
        for player in players:
            if player.id not in series["players"]:
                series["players"][player.id] = Player(player.id, rating=1000).to_dict()
        self.save()

    def get_player_tag(self, server, player: discord.Member):
        """Search crprofile cog for Clash Royale player tag."""
        cps = Box(
            dataIO.load_json(os.path.join("data", "crprofile", "settings.json")),
            default_box=True, default_box_attr=None)
        cps_players = cps.servers[server.id].players
        player_tag = cps_players.get(player.id)
        if player_tag is None:
            raise CannotFindPlayer
        else:
            return player_tag


class CRLadder:
    """CRLadder ranking system.

    Based on http://www.moserware.com/2010/03/computing-your-skill.html
    http://trueskill.org/

    Reuirements:
    pip3 install trueskill
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = Settings(bot)

    @commands.group(pass_context=True)
    async def crladderset(self, ctx):
        """Set crladder settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.is_owner()
    @crladderset.command(name="auth", pass_context=True)
    async def crladderset_auth(self, ctx, token):
        """Authentication key for cr-api.com"""
        self.settings.auth = token
        await self.bot.say("Token saved.")
        await self.bot.delete_message(ctx.message)

    @checks.mod_or_permissions()
    @crladderset.command(name="create", pass_context=True)
    async def crladderset_create(self, ctx, name):
        """Create a new series.

        Creates a new crladder series and optionally initialize with players.
        """
        server = ctx.message.server
        try:
            # self.settings.create(server, name, *players)
            self.settings.create(server, name)
        except SeriesExist:
            await self.bot.say("There is an existing series with that name already.")
            return
        await self.bot.say("Series added.")

    @checks.mod_or_permissions()
    @crladderset.command(name="remove", aliases=['del', 'd', 'delete', 'rm'], pass_context=True)
    async def crladderset_remove(self, ctx, name):
        """Remove a series."""
        server = ctx.message.server
        try:
            self.settings.remove_series(server, name)
        except NoSuchSeries:
            await self.bot.say("Cannot find series named {}".format(name))
        else:
            await self.bot.say("Removed series named {}".format(name))

    @checks.mod_or_permissions()
    @crladderset.command(name="status", pass_context=True)
    async def crladderset_status(self, ctx, name, status):
        """Set or get series status."""
        server = ctx.message.server

        if status is not None:
            if status not in Settings.series_status:
                await self.bot.say('Status must be one of the following: '.format(', '.join(Settings.series_status)))
                return

            try:
                self.settings.set_series_status(server, name, status)
            except NoSuchSeries:
                await self.bot.say("Cannot find a series named {}".format(name))
            else:
                await self.bot.say("Status for {} set to {}.".format(name, status))

    @checks.mod_or_permissions()
    @crladderset.command(name="addplayer", aliases=['ap'], pass_context=True)
    async def crladderset_addplayer(self, ctx, name, player: discord.Member, player_tag=None):
        """Add player to series.

        :param ctx:
        :param name: Name of the series.
        :param player: Discord member.
        :param player_tag: Clash Royale player tag.
        :return:
        """
        server = ctx.message.server

        # Fetch player tag from crprofile
        if player_tag is None:
            player_tag = self.settings.get_player_tag(server, player)
            if player_tag is None:
                await self.bot.say("Cannot find player tag in system. Aborting…")
                return

        try:
            self.settings.add_player(server, name, player, player_tag)
        except NoSuchSeries:
            await self.bot.say("There is no such series with that name.")
        else:
            await self.bot.say("Successfully added player {} with CR tag: #{}.".format(player, player_tag))

    @checks.mod_or_permissions()
    @crladderset.command(name="addplayers", pass_context=True)
    async def crladderset_addplayers(self, ctx, name, *players: discord.Member):
        """Add players to series."""
        server = ctx.message.server
        try:
            self.settings.add_players(server, name, *players)
        except NoSuchSeries:
            await self.bot.say("There is no series with that name.")
            return
        else:
            await self.bot.say("Successfully added players.")

    @commands.group(pass_context=True)
    async def crladder(self, ctx):
        """CRLadder anking system using TrueSkills."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @crladder.command(name="series", aliases=['x'], pass_context=True)
    async def crladder_series(self, ctx):
        """List all series."""
        server = ctx.message.server
        series = self.settings.get_all_series(server)
        names = [k for k in series.keys()]
        names = sorted(names, key=lambda x: x.lower())
        names_str = '\n+ '.join(names)
        await self.bot.say(
            "Available series on this server are:\n+ {}".format(names_str))

    @crladder.command(name="register", pass_context=True)
    async def crladder_register(self, ctx, name):
        """Allow player to self-register to system."""
        server = ctx.message.server
        author = ctx.message.author
        try:
            series = self.settings.get_series(server, name)
        except NoSuchSeries:
            await self.bot.say(
                "There is no such series in that name. "
                "Type `{}crladder series` to find out all the series".format(
                    ctx.prefix
                ))
        else:
            try:
                player_tag = self.settings.get_player_tag(server, author)
            except CannotFindPlayer:
                await self.bot.say("Cannot find player tag in system. Aborting…")
            else:
                self.settings.add_player(server, name, author, player_tag)
                await self.bot.say("Added {} with tag #{} to series {}".format(
                    author,
                    player_tag,
                    name
                ))

    @crladder.command(name="info", pass_context=True)
    async def crladder_info(self, ctx, name):
        """Info about a series."""
        server = ctx.message.server
        await self.bot.type()

        try:
            series = self.settings.get_series(server, name)
        except NoSuchSeries:
            await self.bot.say("Cannot find a series named {}", format(name))
        else:
            em = discord.Embed(
                title=name, description="Clash Royale ladder series.",
                color=discord.Color.red())
            em.add_field(name="Status", value=series.get('status', '_'))

            player_list = []
            players = [p for id_, p in series.players.items()]
            players = sorted(players, key=lambda p: p.rating.mu)
            for p in players:
                player = Player.from_dict(p)
                member = await self.bot.get_user_info(player.discord_id)
                player_list.append("{} #{}".format(bold(member.display_name), player.tag))
                player_list.append(inline("{:10.2f} {:5.2f}".format(player.rating.mu, player.rating.sigma)))
            em.add_field(name="Players", value='\n'.join(player_list), inline=False)

            await self.bot.say(embed=em)


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
    n = CRLadder(bot)
    bot.add_cog(n)
