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

import datetime as dt
import os

import aiohttp
import discord
from box import Box
from cogs.utils import checks
from cogs.utils.chat_formatting import inline, bold, box
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from trueskill import TrueSkill, Rating, rate_1vs1, quality_1vs1

PATH = os.path.join("data", "crladder")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "SERIES": {}
}

# recommneded formula
RATING = 1000
SIGMA = RATING / 3
BETA = SIGMA / 2
TAU = BETA / 100
DRAW_PROBABILITY = 0.5


env = TrueSkill(
    mu=RATING,
    sigma=SIGMA,
    beta=BETA,
    tau=TAU,
    draw_probability=DRAW_PROBABILITY,
    backend=None)


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


class APIError(LadderException):
    def __init__(self, response):
        self.response = response


class ClashRoyaleAPI:
    def __init__(self, token):
        self.token = token


class Player:
    """Player in a game."""

    def __init__(self, discord_id=None, tag=None, rating=RATING, sigma=SIGMA):
        """
        Player.
        :param discord_id: Discord user id.
        :param tag: Clash Royale player tag.
        :param rating: Initial rating.
        """
        if isinstance(rating, Rating):
            self.rating = rating
        elif isinstance(rating, dict):
            self.rating = env.create_rating(mu=rating['mu'], sigma=rating['sigma'])
        else:
            self.rating = env.create_rating()
        self.discord_id = discord_id
        self.tag = normalize_tag(tag)

    @property
    def rating_display(self):
        """Display rating as mu - sigma * 3."""
        return self.rating.mu - self.rating.sigma * 3 + RATING

    def __repr__(self):
        return '<Player: {0}>'.format(str(self.to_dict()))

    def to_dict(self):
        return {
            "rating": {
                "mu": self.rating.mu,
                "sigma": self.rating.sigma,
                "display": self.rating_display
            },
            "discord_id": self.discord_id,
            "tag": self.tag
        }

    @staticmethod
    def from_dict(d):
        if isinstance(d, dict):
            p = Player(**d)
        else:
            p = Player()
        return p


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


class Battle:
    def __init__(self, battle_dict):
        self.data = Box(battle_dict, default_box=True, camel_killer_box=True)

    @property
    def type(self):
        return self.data.get("type")

    def type_is(self, type_name):
        return self.type == type_name

    @property
    def valid_type(self):
        return self.type_is("friendly") or self.type_is("clanMate")

    @property
    def timestamp(self):
        return self.data.get('utcTime')

    @property
    def timestamp_dt(self):
        return dt.datetime.utcfromtimestamp(self.timestamp)

    @property
    def team_deck(self):
        player = self.data.team[0]
        deck = [card.key for card in player.deck]
        return deck

    @property
    def team_decklink(self):
        player = self.data.team[0]
        return player.deckLink

    @property
    def team_tag(self):
        return self.data.team[0].tag

    @property
    def opponent_deck(self):
        player = self.data.opponent[0]
        deck = [card.key for card in player.deck]
        return deck

    @property
    def opponent_decklink(self):
        player = self.data.opponent[0]
        return player.deckLink

    @property
    def opponent_tag(self):
        return self.data.opponent[0].tag

    @property
    def winner(self):
        return self.data.winner

    @property
    def result(self):
        if self.winner == 1:
            return "Win"
        elif self.winner == -1:
            return "Loss"
        else:
            return "Draw"

    @property
    def team_crowns(self):
        return self.data.get("teamCrowns")

    @property
    def opponent_crowns(self):
        return self.data.get("opponentCrowns")


class Match:
    """A match."""

    def __init__(self,
                 player1: Player = None,
                 player2: Player = None,
                 player1_old_rating: Rating = None,
                 player2_old_rating: Rating = None,
                 battle=None):
        self.player1 = player1
        self.player2 = player2
        self.battle = battle
        self.player1_old_rating = player1_old_rating
        self.player2_old_rating = player2_old_rating

    def to_dict(self):
        return {
            "timestamp": self.battle.timestamp,
            "timestamp_iso": self.battle.timestamp_dt.isoformat(),
            "player1": {
                "deck": self.battle.team_deck,
                "decklink": self.battle.team_decklink,
                "crowns": self.battle.team_crowns,
                "tag": self.battle.team_tag,
                "old_rating": {
                    "mu": self.player1_old_rating.mu,
                    "sigma": self.player1_old_rating.sigma,
                },
                "new_rating": {
                    "mu": self.player1.rating.mu,
                    "sigma": self.player1.rating.sigma,
                }

            },
            "player2": {
                "deck": self.battle.opponent_deck,
                "decklink": self.battle.opponent_decklink,
                "crowns": self.battle.opponent_crowns,
                "tag": self.battle.opponent_tag,
                "old_rating": {
                    "mu": self.player2_old_rating.mu,
                    "sigma": self.player2_old_rating.sigma,
                },
                "new_rating": {
                    "mu": self.player2.rating.mu,
                    "sigma": self.player2.rating.sigma,
                }
            }
        }


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
        # preprocess rating if found
        for server_id, server in self.model.servers.items():
            for name, series in server.series.items():
                for player in series.players:
                    if isinstance(player.rating, Rating):
                        player.rating = {
                            "mu": float(player.rating.mu),
                            "sigma": float(player.rating.sigma)
                        }
        dataIO.save_json(JSON, self.model)

    @property
    def auth(self):
        """cr-api.com Authentication token."""
        return self.model.auth

    @auth.setter
    def auth(self, value):
        self.model.auth = value
        self.save()

    def legacy_update(self):
        """Update players from dict to list."""
        for server_k, server in self.model.servers.items():
            for series_name, series in server.series.items():
                player_list = []
                for player_id, player in series.players.items():
                    player_list.append(player.copy())
                series.players = player_list
        self.save()

    def server_model(self, server):
        """Return model by server."""
        self.check_server(server)
        return self.model.servers[server.id]

    def check_server(self, server):
        """Create server settings if required."""
        if server.id not in self.model.servers:
            self.model.servers[server.id] = self.server_default
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

    def get_player(self, server, name, member: discord.Member):
        """Check player settings."""
        self.check_server(server)
        try:
            series = self.get_series(server, name)
            for player in series.players:
                if player.discord_id == member.id:
                    return player
        except NoSuchSeries:
            raise NoSuchSeries
        else:
            return None

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
        series_player = self.get_player(server, name, player)
        if series_player is not None:
            return False
        else:
            series["players"].append(Player(discord_id=player.id, tag=player_tag).to_dict())
            self.save()
            return True

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

    def verify_player(self, series, member: discord.Member):
        """Verify player is in series."""
        for player in series.players:
            if player.discord_id == member.id:
                return True
        return False

    async def find_battles(self, series, member1: discord.Member, member2: discord.Member):
        """Find battle by member1 vs member2."""
        player1, player2 = None, None
        for player in series.players:
            if player.discord_id == member1.id:
                player1 = player
            if player.discord_id == member2.id:
                player2 = player

        url = 'http://api.cr-api.com/player/{}?keys=battles'.format(player1.tag)
        response = {}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'auth': self.auth}) as resp:
                if resp.status != 200:
                    raise APIError(resp)
                else:
                    response = await resp.json()

        all_battles = response.get('battles')
        battles = []
        for battle in all_battles:
            b = Battle(battle)
            add_this = True
            if not b.valid_type:
                add_this = False
            if b.opponent_tag != player2.tag:
                add_this = False
            if add_this:
                battles.append(b)

        return battles

    def is_battle_saved(self, server, name, battle: Battle):
        self.save()
        series = self.get_series(server, name)
        keys = [k for k in series.matches.keys()]
        is_in = str(battle.timestamp) in keys
        return is_in

    def save_battle(self,
                    player1: Player = None,
                    player2: Player = None,
                    player1_old_rating: Rating = None,
                    player2_old_rating: Rating = None,
                    series=None, battle=None):
        match = Match(player1=player1, player2=player2, player1_old_rating=player1_old_rating,
                      player2_old_rating=player2_old_rating, battle=battle)

        series.matches[str(battle.timestamp)] = match.to_dict()
        self.save()

    def update_player_rating(self, server, name, player):
        series = self.get_series(server, name)
        update_player = None
        for p in series.players:
            if p.tag == player.tag:
                update_player = p
        if update_player is None:
            return False
        update_player.rating = {
            "mu": float(player.rating.mu),
            "sigma": float(player.rating.sigma)
        }
        self.save()
        return True


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

    @checks.is_owner()
    @crladderset.command(name="legacyupdate", pass_context=True)
    async def crladderset_legacyupdate(self, ctx):
        """Update legacy database."""
        self.settings.legacy_update()
        await self.bot.say("Updated old DB to new.")

    @checks.mod_or_permissions()
    @crladderset.command(name="create", pass_context=True)
    async def crladderset_create(self, ctx, name):
        """Create a new series.

        Creates a new crladder series and optionally initialize with players.
        """
        server = ctx.message.server
        try:
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
            try:
                player_tag = self.settings.get_player_tag(server, player)
            except CannotFindPlayer:
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
    async def crladder_info(self, ctx, name, *args):
        """Info about a series."""
        server = ctx.message.server
        await self.bot.type()

        if not len(args):
            use = "rating_display"
        else:
            use = args[0].lower()

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
            players = [Player.from_dict(d) for d in series.players]
            players = sorted(players, key=lambda p: p.rating_display, reverse=True)
            for p in players:
                member = server.get_member(p.discord_id)
                if member is not None:
                    if use == 'rating_display':
                        player_list.append("`{:_>4.0f}` \t{}".format(p.rating_display, member))
                    elif use == 'mu':
                        player_list.append("`{:_>4.0f}` \t{}".format(p.rating.mu, member))

            em.add_field(name="Players", value='\n'.join(player_list), inline=False)

            await self.bot.say(embed=em)

    def bot_emoji(self, name):
        """Emoji by name."""
        for emoji in self.bot.get_all_emojis():
            if emoji.name == name:
                return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''

    @crladder.command(name="battle", pass_context=True)
    async def crladder_battle(self, ctx, name, member: discord.Member):
        """Report battle."""
        server = ctx.message.server
        author = ctx.message.author
        await self.bot.type()

        try:
            series = self.settings.get_series(server, name)
        except NoSuchSeries:
            await self.bot.say("Cannot find a series named {}", format(name))
        else:
            if not self.settings.verify_player(series, author):
                await self.bot.say("You are not registered in this series.")
                return
            if not self.settings.verify_player(series, member):
                await self.bot.say("{} is not registered is this series.".format(member))
                return
            try:
                battles = await self.settings.find_battles(series, author, member)
            except APIError as e:
                print(e.response)
                await self.bot.say("Error fetching results from API. Please try again later.")
            else:

                if len(battles) > 1:
                    await self.bot.say("Found multiple battles. Using only last battle.")
                if len(battles) == 0:
                    await self.bot.say("No battle found.")
                    return

                battles = sorted(battles, key=lambda x: int(x.timestamp))
                battle = battles[-1]

                save_battle = True
                if self.settings.is_battle_saved(server, name, battle):
                    save_battle = False

                def match_1vs1(winner: Player, loser: Player, drawn=False):
                    """Match score reporting."""
                    winner.rating, loser.rating = rate_1vs1(winner.rating, loser.rating, drawn=drawn)
                    return winner, loser

                p_author = Player.from_dict(self.settings.get_player(server, name, author).copy())
                p_member = Player.from_dict(self.settings.get_player(server, name, member).copy())
                # print(p_author)

                p_author_rating_old = p_author.rating_display
                p_member_rating_old = p_member.rating_display

                if battle.winner == 1:
                    color = discord.Color.green()
                    p_author, p_member = match_1vs1(p_author, p_member)
                elif battle.winner == 0:
                    color = discord.Color.light_grey()
                    p_author, p_member = match_1vs1(p_author, p_member, drawn=True)
                elif battle.winner == -1:
                    color = discord.Color.red()
                    p_member, p_author = match_1vs1(p_member, p_author)
                else:
                    color = discord.Color.gold()

                em = discord.Embed(
                    title="Battle: {} vs {}".format(author, member),
                    description="Series: {}".format(name),
                    color=color
                )
                em.add_field(
                    name="Result",
                    value=battle.result
                )
                em.add_field(
                    name="Score",
                    value="{} - {}".format(battle.team_crowns, battle.opponent_crowns)
                )
                em.add_field(
                    name="UTC Time",
                    value=battle.timestamp_dt.isoformat()
                )
                em.add_field(
                    name=str(author),
                    value=''.join([self.bot_emoji(key.replace('-', '')) for key in battle.team_deck]),
                    inline=False
                )
                if save_battle:
                    em.add_field(
                        name="Elo",
                        value=inline("{:>10,.1f} -> {:>10,.1f}".format(p_author_rating_old, p_author.rating_display)),
                        inline=False
                    )
                em.add_field(
                    name=str(member),
                    value=''.join([self.bot_emoji(key.replace('-', '')) for key in battle.opponent_deck]),
                    inline=False
                )
                if save_battle:
                    em.add_field(
                        name="Elo",
                        value=inline("{:>10,.1f} -> {:>10,.1f}".format(p_member_rating_old, p_member.rating_display)),
                        inline=False
                    )
                if not save_battle:
                    em.add_field(
                        name=":warning: Warning",
                        value="This battle is not saved because it has already been registered.",
                        inline=False
                    )
                await self.bot.say(embed=em)

                # save battle
                if save_battle:
                    self.settings.save_battle(
                        player1=p_author, player2=p_member, player1_old_rating=p_author_rating_old,
                        player2_old_rating=p_member_rating_old, series=series, battle=battle
                    )
                    updated = self.settings.update_player_rating(server, name, p_author)
                    updated = self.settings.update_player_rating(server, name, p_member)
                    await self.bot.say("Elo updated.")

    @crladder.command(name="quality", aliases=['q'], pass_context=True)
    async def crladder_qualify(self, ctx, name, member1: discord.Member, member2:discord.Member=None):
        """Head to head winning chance."""
        author = ctx.message.author
        server = ctx.message.server
        if member2 is None:
            pm1 = author
            pm2 = member1
        else:
            pm1 = member1
            pm2 = member2
        try:
            p1 = Player.from_dict(self.settings.get_player(server, name, pm1))
            p2 = Player.from_dict(self.settings.get_player(server, name, pm2))
        except NoSuchSeries:
            await self.bot.say("No series with that name on this server.")
        except NoSuchPlayer:
            await self.bot.say("Player not found.")
        else:
            await self.bot.say(
                "If {} plays against {}, "
                "there is a {:.1%} chance to draw.".format(
                    pm1, pm2, quality_1vs1(p1.rating, p2.rating)
                )
            )



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
