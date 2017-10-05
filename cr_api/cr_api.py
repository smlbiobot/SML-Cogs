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

import asyncio
import datetime as dt
import os
from collections import defaultdict

import aiohttp
import async_timeout
from __main__ import send_cmd_help
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "cr_api")
JSON = os.path.join(PATH, "settings.json")

CHESTS = dataIO.load_json(os.path.join(PATH, 'chests.json'))


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class SCTag:
    """SuperCell tags."""

    TAG_CHARACTERS = list("0289PYLQGRJCUV")

    def __init__(self, tag: str):
        """Init.

        Remove # if found.
        Convert to uppercase.
        Convert Os to 0s if found.
        """
        if tag.startswith('#'):
            tag = tag[1:]
        tag = tag.replace('O', '0')
        tag = tag.upper()
        self._tag = tag

    @property
    def tag(self):
        """Return tag as str."""
        return self._tag

    @property
    def valid(self):
        """Return true if tag is valid."""
        for c in self.tag:
            if c not in self.TAG_CHARACTERS:
                return False
        return True

    @property
    def invalid_chars(self):
        """Return list of invalid characters."""
        invalids = []
        for c in self.tag:
            if c not in self.TAG_CHARACTERS:
                invalids.append(c)
        return invalids

    @property
    def invalid_error_msg(self):
        """Error message to show if invalid."""
        return (
            'The tag you have entered is not valid. \n'
            'List of invalid characters in your tag: {}\n'
            'List of valid characters for tags: {}'.format(
                ', '.join(self.invalid_chars),
                ', '.join(self.TAG_CHARACTERS)
            ))


class CRPlayerModel:
    """Clash Royale player model."""

    def __init__(self, is_cache=False, data=None):
        """Init."""
        self.data = data
        self.is_cache = is_cache
        self.CHESTS = CHESTS

    @property
    def tag(self):
        """Player tag"""
        return self.data.get("tag", None)

    @property
    def name(self):
        """IGN."""
        return self.data.get("name", None)

    @property
    def trophies(self):
        """Trophies."""
        return self.data.get("trophies", None)

    @property
    def experience(self):
        """Experience."""
        return self.data.get("experience", None)

    @property
    def level(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("level", None)
        return None

    @property
    def xp(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("xp", 0)
        return 0

    @property
    def xp_total(self):
        """XP Level."""
        if self.experience is not None:
            return self.experience.get("xpRequiredForLevelUp", None)
        return None

    @property
    def xp_str(self):
        """Experience in current / total format."""
        current = 'MAX'
        total = 'MAX'
        if isinstance(self.xp_total, int):
            current = '{:,}'.format(self.xp)
            total = '{:,}'.format(self.xp_total)
        return '{} / {}'.format(current, total)

    @property
    def clan(self):
        """Clan."""
        return self.data.get("clan", None)

    @property
    def not_in_clan(self):
        """Not in clan flag."""
        return self.clan is None

    @property
    def clan_name(self):
        """Clan name."""
        if self.not_in_clan:
            return "No Clan"
        if self.clan is not None:
            return self.clan.get("name", None)
        return None

    @property
    def clan_tag(self):
        """Clan tag."""
        if self.clan is not None:
            return self.clan.get("tag", None)
        return None

    @property
    def clan_role(self):
        """Clan role."""
        if self.not_in_clan:
            return "N/A"
        if self.clan is not None:
            return self.clan.get("role", None)
        return None

    @property
    def clan_name_tag(self):
        """Clan name and tag."""
        return '{} #{}'.format(self.clan_name, self.clan_tag)

    @property
    def clan_badge_url(self):
        """Clan badge url."""
        if self.not_in_clan:
            return "http://smlbiobot.github.io/img/emblems/NoClan.png"
        try:
            url = self.clan['badge']['url']
            return 'http://api.cr-api.com' + url
        except KeyError:
            pass
        return ''

    @property
    def stats(self):
        """Stats."""
        return self.data.get("stats", None)

    @property
    def challenge_cards_won(self):
        """Challenge cards won."""
        if self.stats is not None:
            return self.stats.get("challengeCardsWon", 0)
        return 0

    @property
    def tourney_cards_won(self):
        """Challenge cards won."""
        if self.stats is not None:
            return self.stats.get("tournamentCardsWon", 0)
        return 0

    @property
    def tourney_cards_per_game(self):
        """Number of tournament cards won per game played."""
        if self.tourney_games:
            return self.tourney_cards_won / self.tourney_games
        return None

    @property
    def challenge_max_wins(self):
        """Max challenge wins."""
        if self.stats is not None:
            return self.stats.get("challengeMaxWins", 0)
        return 0

    @property
    def total_donations(self):
        """Total donations."""
        if self.stats is not None:
            return self.stats.get("totalDonations", 0)
        return 0

    @property
    def cards_found(self):
        """Cards found."""
        if self.stats is not None:
            return self.stats.get("cardsFound", 0)
        return 0

    @property
    def favorite_card(self):
        """Favorite card"""
        """Cards found."""
        if self.stats is not None:
            return self.stats.get("favoriteCard", "soon")
        return "soon"

    @property
    def trophy_current(self):
        """Current trophies."""
        return self.data.get("trophies", None)

    @property
    def trophy_highest(self):
        """Personal best."""
        if self.stats is not None:
            return self.stats.get("maxTrophies", None)
        return None

    @property
    def trophy_legendary(self):
        """Legendary trophies."""
        if self.stats is not None:
            return self.stats.get("legendaryTrophies", None)
        return None

    def trophy_value(self, emoji):
        """Trophy values.

        Current / Highest (PB)
        """
        return '{} / {} PB {}'.format(
            '{:,}'.format(self.trophy_current),
            '{:,}'.format(self.trophy_highest),
            emoji)

    @property
    def games(self):
        """Game stats."""
        return self.data.get("games", None)

    @property
    def tourney_games(self):
        """Number of tournament games."""
        if self.games is not None:
            return self.games.get("tournamentGames", 0)
        return 0

    @property
    def wins(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("wins", 0)
        return 0

    @property
    def losses(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("losses", 0)
        return 0

    @property
    def draws(self):
        """Games won."""
        if self.games is not None:
            return self.games.get("draws", 0)
        return 0

    def win_draw_losses(self, emoji):
        """Win / draw / losses."""
        return '{} / {} / {} {}'.format(
            '{:,}'.format(self.wins),
            '{:,}'.format(self.draws),
            '{:,}'.format(self.losses),
            emoji
        )

    @property
    def total_games(self):
        """Total games played."""
        if self.games is not None:
            return self.games.get("total", 0)
        return 0

    @property
    def win_streak(self):
        """Win streak."""
        streak = 0
        if self.games is not None:
            streak = self.games.get("currentWinStreak", 0)
        return max(streak, 0)

    @property
    def three_crown_wins(self):
        """Three crown wins."""
        if self.games is not None:
            return self.stats.get("threeCrownWins", 0)
        return 0

    @property
    def rank(self):
        """Global rank"""
        return self.data.get("globalRank", None)

    """
    Chests.
    """

    @property
    def chest_cycle(self):
        """Chest cycle."""
        return self.data.get("chestCycle", None)

    @property
    def chest_cycle_position(self):
        """Chest cycle position."""
        if self.chest_cycle is not None:
            return self.chest_cycle.get("position", None)
        return None

    def chest_by_position(self, pos):
        """Return chest type based on position."""
        if pos == self.chest_cycle.get("superMagicalPos"):
            return "SuperMagical"
        elif pos == self.chest_cycle.get("legendaryPos"):
            return "Legendary"
        elif pos == self.chest_cycle.get("epicPos"):
            return "Epic"
        return self.CHESTS[pos % len(self.CHESTS)]

    def chests(self, count):
        """Next n chests."""
        if self.chest_cycle_position is not None:
            return [self.chest_by_position(self.chest_cycle_position + i) for i in range(count)]
        return []

    def chest_index(self, key):
        """Chest incdex by chest key."""
        if self.chest_cycle is None:
            return None
        if self.chest_cycle_position is None:
            return None
        chest_pos = self.chest_cycle.get(key, None)
        if chest_pos is None:
            return None
        return chest_pos - self.chest_cycle_position

    @property
    def chest_super_magical_index(self):
        """Super magical index."""
        return self.chest_index("superMagicalPos")

    @property
    def chest_legendary_index(self):
        """Super magical index."""
        return self.chest_index("legendaryPos")

    @property
    def chest_epic_index(self):
        """Super magical index."""
        return self.chest_index("epicPos")

    def chest_first_index(self, key):
        """First index of chest by key."""
        if self.CHESTS is not None:
            pos = self.chest_cycle_position
            if pos is not None:
                start_pos = pos % len(self.CHESTS)
                chests = self.CHESTS[start_pos:]
                chests.extend(self.CHESTS)
                return chests.index(key)
        return None

    @property
    def chest_magical_index(self):
        """First index of magical chest"""
        return self.chest_first_index('Magic')

    @property
    def chest_giant_index(self):
        """First index of giant chest"""
        return self.chest_first_index('Giant')

    @property
    def chests_opened(self):
        """Number of chests opened."""
        return self.chest_cycle_position

    def shop_offers(self, name):
        """Shop offers by name.

        Valid names are: legendary, epic, arena.
        """
        offers = self.data.get("shopOffers")
        return offers.get(name)

    @property
    def shop_offers_arena(self):
        """Get epic shop offer."""
        return self.shop_offers("arena")

    @property
    def shop_offers_epic(self):
        """Get epic shop offer."""
        return self.shop_offers("epic")

    @property
    def shop_offers_legendary(self):
        """Get epic shop offer."""
        return self.shop_offers("legendary")

    @property
    def win_ratio(self):
        """Win ratio."""
        return (self.wins + self.draws * 0.5) / (self.wins + self.draws + self.losses)

    @property
    def arena(self):
        """League. Can be either Arena or league."""
        try:
            return self.data["arena"]["arena"]
        except KeyError:
            return None

    @property
    def arena_text(self):
        """Arena text."""
        try:
            return self.data["arena"]["name"]
        except KeyError:
            return None

    @property
    def arena_subtitle(self):
        """Arena subtitle"""
        try:
            return self.data["arena"]["arena"]
        except KeyError:
            return None

    @property
    def arena_id(self):
        """Arena ID."""
        try:
            return self.data["arena"]["arenaID"]
        except KeyError:
            return None

    @property
    def league(self):
        """League (int)."""
        league = max(self.arena_id - 11, 0)
        return league

    @property
    def arena_url(self):
        """Arena Icon URL."""
        if self.league > 0:
            url = 'http://smlbiobot.github.io/img/leagues/league{}.png'.format(self.league)
        else:
            url = 'http://smlbiobot.github.io/img/arenas/arena-{}.png'.format(self.arena.Arena)
        return url

    @property
    def seasons(self):
        """Season finishes."""
        s_list = []
        for s in self.data.get("previousSeasons"):
            s_list.append({
                "number": s.get("seasonNumber", None),
                "highest": s.get("seasonHighest", None),
                "ending": s.get("seasonEnding", None),
                "rank": s.get("seasonEndGlobalRank", None)
            })
        s_list = sorted(s_list, key=lambda s: s["number"])
        return s_list


class CRClanMemberModel:
    """Clash Royale clan member model."""

    def __init__(self, data):
        """Init.
        """
        self.data = data
        self._discord_member = None

    @property
    def name(self):
        """Name aka IGN."""
        return self.data.get('name', None)

    @property
    def tag(self):
        """Player tag."""
        return self.data.get('tag', None)

    @property
    def score(self):
        """Player trophies."""
        return self.data.get('score', None)

    @property
    def donations(self):
        """Donations."""
        return self.data.get('donations', None)

    @property
    def clan_chest_crowns(self):
        """Clan chest crowns"""
        return self.data.get('clanChestCrowns', None)

    @property
    def arena(self):
        """Arena object."""
        return self.data.get('arena', None)

    @property
    def arena_str(self):
        """Arena. eg: Arena 10: Hog Mountain"""
        arena = self.data.get('arena', None)
        if arena is not None:
            return '{}: {}'.format(
                arena.get('arena', ''),
                arena.get('name', '')
            )
        return ''

    @property
    def role(self):
        """Role ID"""
        return self.data.get('role', None)

    @property
    def exp_level(self):
        """Experience level."""
        return self.data.get('expLevel', None)

    @property
    def discord_member_id(self):
        """Discord user id."""
        return self._discord_member

    @discord_member_id.setter
    def discord_member_id(self, value):
        """Discord user id."""
        self._discord_member = value

    @property
    def mention(self):
        """Discord mention."""
        # return self.discord_member.mention
        return ""

    @property
    def role_name(self):
        """Properly formatted role name."""
        return self.data.get('roleName', None)

    @property
    def previousRank(self):
        """Previous rank."""
        return self.data.get('previousRank', 0)

    @property
    def currentRank(self):
        """API has typo."""
        return self.data.get('currentRank', 0)

    @property
    def rank(self):
        """Rank in clan with trend.

        Rank diffis in reverse because lower is better.
        Previous rank is 0 when user is new to the clan.

        \u00A0 is a non-breaking space.

        """
        rank_str = '--'
        if self.previousRank != 0:
            rank_diff = self.currentRank - self.previousRank
            if rank_diff > 0:
                rank_str = "↓ {}".format(rank_diff)
            elif rank_diff < 0:
                rank_str = "↑ {}".format(-rank_diff)
        return "`{0:\u00A0>8} {1:\u00A0<16}`".format(self.currentRank, rank_str)

    @property
    def rankdelta(self):
        """Difference in rank.

        Return None if previous rank is 0
        """
        if self.previousRank == 0:
            return None
        else:
            return self.currentRank - self.previousRank

    @property
    def league(self):
        """League ID from Arena ID."""
        arenaID = self.arena["arenaID"]
        leagueID = arenaID - 11
        if leagueID > 0:
            return leagueID
        return 0

    @property
    def league_icon_url(self):
        """League Icon URL."""
        return (
            'http://smlbiobot.github.io/img/leagues/'
            'league{}.png'
        ).format(self.league)

    def league_emoji(self, bot):
        """League emoji.

        Goes through all servers the bot is on to find the emoji.
        """
        name = 'league{}'.format(self.league)
        for server in bot.servers:
            for emoji in server.emojis:
                if emoji.name == name:
                    return '<:{}:{}>'.format(emoji.name, emoji.id)
        return ''


class CRClanModel:
    """Clash Royale Clan data."""

    def __init__(self, data=None, is_cache=False, timestamp=None, loaded=True):
        """Init.
        """
        # self.__dict__.update(kwargs)
        self.data = data
        self.is_cache = is_cache
        self.timestamp = timestamp
        self.loaded = loaded
        self._members = []
        self._discord_role = None

    @property
    def badge(self):
        """Badge."""
        return self.data.get('badge', None)

    @property
    def badge_url(self):
        """Badge URL."""
        try:
            return self.data['badge']['url']
        except KeyError:
            return ''

    @property
    def current_rank(self):
        """Current rank."""
        return self.data.get('currentRank', None)

    @property
    def description(self):
        """Description."""
        return self.data.get('description', None)

    @property
    def donations(self):
        """Donations."""
        return self.data.get('donations', None)

    @property
    def members(self):
        """Members."""
        if len(self._members) == 0:
            members = self.data.get('members', None)
            for m in members:
                self._members.append(CRClanMemberModel(data=m))
        return self._members

    @property
    def member_tags(self):
        """List of member tags."""
        return [m.tag for m in self.members]

    @property
    def name(self):
        """Name."""
        return self.data.get('name', None)

    @property
    def member_count(self):
        """Member count."""
        return self.data.get('memberCount', None)

    @property
    def region_name(self):
        """Region."""
        region = self.data.get('region', None)
        if region is not None:
            return region.get('name', None)
        return None

    @property
    def required_score(self):
        """Trophy requirement."""
        return self.data.get('requiredScore', None)

    @property
    def score(self):
        """Trophies."""
        return self.data.get('score', None)

    @property
    def member_count_str(self):
        """Member count in #/50 format."""
        return '{}/50'.format(self.member_count)

    @property
    def tag(self):
        """Tag."""
        return self.data.get('tag', None)

    @property
    def type(self):
        """Type."""
        return self.data.get('type', None)

    @property
    def type_name(self):
        """"Type name."""
        return self.data.get('typeName', None)

    @property
    def valid(self):
        """Return True if it has expected properties."""
        return hasattr(self, 'name')

    @property
    def cache_message(self):
        """Cache message."""
        passed = dt.datetime.utcnow() - self.timestamp

        days = passed.days
        hours, remainder = divmod(passed.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        days_str = '{} days '.format(days) if days > 0 else ''
        passed_str = '{} {} hours {} minutes {} seconds ago'.format(days_str, hours, minutes, seconds)
        return (
            "Warning: Unable to access API. Returning cached data. "
            "Real-time data in CR may be different. \n"
            "Displaying data from {}.".format(passed_str)
        )

    """
    Cog helper properties
    """
    @property
    def discord_role(self):
        """Discord role object."""
        return self._discord_role

    @discord_role.setter
    def discord_role(self, value):
        """Discord role object."""
        self._discord_role = value


class Settings:
    """CR API Settings."""
    timeout = 30


class ClashRoyaleAPI:
    """Clash Royale API.
    
    This is a utility cog that other cogs call to fetch data from http://cr-api.com
    
    Examples
    
    class MyCog:
    
        def __init__(self, bot):
            self.bot = bot
            
        def foo(self):
            api = self.bot.get_cog('ClashRoyaleAPI')
            profile = api.profile_model('C0G20PR2')
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(name="crapi", pass_context=True)
    async def crapi(self, ctx):
        """Clash Royale API wrapper for cr-api.com"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @crapi.command(name="status", pass_context=True)
    async def crapi_status(self, ctx):
        """Cog status."""
        await self.bot.say("Cog loaded.")

    async def fetch(self, session, url):
        """Fetch URL.
        
        :param session: aiohttp.ClientSession
        :param url: URL
        :return: Response in JSON
        """
        print(url)
        try:
            with async_timeout.timeout(Settings.timeout):
                async with session.get(url) as response:
                    return await response.json()
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientResponseError:
            return None

    async def profile_json(self, tag):
        """Get player profile as JSON.
        
        http://api.cr-api.com/profile/C0G20PR2
        """
        url = 'http://api.cr-api.com/profile/{}'.format(SCTag(tag).tag)
        async with aiohttp.ClientSession() as session:
            data = await self.fetch(session, url)
        return data

    async def profile_model(self, tag):
        """Get player profile as CRPlayerModel."""
        data = await self.profile_json(tag)
        return CRPlayerModel(data=data)

    async def clan_json(self, tag):
        """Clan as JSON.
        
        http://api.cr-api.com/clan/2CCCP 
        """
        url = 'http://api.cr-api.com/clan/{}'.format(SCTag(tag).tag)
        async with aiohttp.ClientSession() as session:
            data = await self.fetch(session, url)
        return data

    async def clan_model(self, tag):
        """Clan as CRClanModel."""
        data = await self.clan_json(tag)
        return CRClanModel(data=data)

    async def clans_json(self, tags):
        """Clans as JSON."""
        sctags = [SCTag(t).tag for t in tags]
        url = 'http://api.cr-api.com/clan/{}'.format(','.join(sctags))
        async with aiohttp.ClientSession() as session:
            data = await self.fetch(session, url)
        return data

    async def clans_model(self, tags):
        """Clans as a list of CRClanModel.
        
        TOOD: Legacy remove.
        """
        data = await self.clans_json(tags)
        return [CRClanModel(c) for c in data]

    async def clan_models(self, tags):
        """Clans as a list of CRClanModel."""
        data = await self.clans_json(tags)
        return [CRClanModel(c) for c in data]

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
    n = ClashRoyaleAPI(bot)
    bot.add_cog(n)
