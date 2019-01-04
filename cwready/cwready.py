"""
Clan War Readiness
"""

import asyncio
import itertools
from collections import defaultdict

import aiohttp
import discord
import logging
import os
import re
import socket
import yaml
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

logger = logging.getLogger(__name__)

PATH = os.path.join("data", "cwready")
JSON = os.path.join(PATH, "settings.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")
CARDS_JSON_URL = 'https://royaleapi.github.io/cr-api-data/json/cards.json'
CARDS = None


class TagNotFound(Exception):
    pass


class UnknownServerError(Exception):
    pass


def grouper(iterable, n, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if isinstance(t, list):
        t = t[0]
    if isinstance(t, tuple):
        t = t[0]
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    t = t.replace('O', '0')
    t = t.replace('B', '8')
    return t


def get_emoji(bot, name):
    for emoji in bot.get_all_emojis():
        if emoji.name == name:
            return '<:{}:{}>'.format(emoji.name, emoji.id)
    return name


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


async def get_card_constants():
    global CARDS
    if CARDS is None:
        async with aiohttp.ClientSession() as session:
            async with session.get(CARDS_JSON_URL) as resp:
                CARDS = await resp.json()
    return CARDS


class CWReady:
    """Clan War Readinesx"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self._config = None

    @property
    def config(self):
        if self._config is None:
            if not os.path.exists(CONFIG_YAML):
                return {}
            with open(CONFIG_YAML) as f:
                self._config = yaml.load(f)
        return self._config

    @property
    def bot_auth(self):
        return self.settings.get('bot_auth', '')

    @checks.admin()
    @commands.command(pass_context=True)
    async def cwrauth(self, ctx, auth):
        """Set CWR Bot authentication token."""
        self.settings['bot_auth'] = auth
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Bot Authentication saved.")
        await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True, aliases=['cwrt'])
    async def cwreadytag(self, ctx, tag):
        """Return clan war readiness."""
        tag = clean_tag(tag)

        tasks = [
            self.fetch_cwready(tag),
            self.fetch_cw_history(tag)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, TagNotFound):
                await self.bot.say("Invalid tag #{}. Please verify that tag is set correctly.".format(tag))
                return
            if isinstance(r, UnknownServerError):
                await self.bot.say("Unknown server error from API")
                return
            if isinstance(r, Exception):
                logger.exception("Unknown exception", r)
                await self.bot.say("Server error: {}".format(r))

        data, hist = results
        await self.bot.say(embed=await self.cwready_embed(data, hist))
        await self.send_cwr_req_results(ctx, data)

        # import json
        # print(json.dumps(hist))

    @commands.command(pass_context=True, no_pm=True, aliases=['cwr'])
    async def cwready(self, ctx, member: discord.Member = None):
        """Return clan war readiness."""
        if member is None:
            member = ctx.message.author

        tag = None

        # if tag is none, attempt to load from racf_audit
        db = os.path.join("data", "racf_audit", "player_db.json")
        players = dataIO.load_json(db)
        for k, v in players.items():
            if v.get('user_id') == member.id:
                tag = v.get('tag')

        if tag is None:
            await self.bot.say(
                "Cannot find associated tag in DB. Please use `cwreadytag` or `cwrt` to fetch by tag")
            await self.bot.send_cmd_help(ctx)
            return

        tag = clean_tag(tag)

        await ctx.invoke(self.cwreadytag, tag)

    async def send_cwr_req_results(self, ctx, data):
        # don’t send results for now
        pass
        # await self.send_cwr_req_results_channel(ctx.message.channel, data)

    async def send_cwr_req_results_channel(self, channel, data):
        clans = await self.test_cwr_requirements(data)
        if len(clans) == 0:
            await self.bot.send_message(
                channel,
                "User does not meet requirements for any of our clans."
            )
        else:
            await self.bot.send_message(
                channel,
                "Qualified clans: {}. {}".format(
                    ", ".join([clan.get('name') for clan in clans]),
                    self.config.get('addendum', '')
                ))

    async def fetch_json(self, url, headers=None, error_dict=None):
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        data = dict()
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                elif error_dict and resp.status in error_dict.keys():
                    for k, v in error_dict.items():
                        if resp.status == k:
                            raise v()
                else:
                    raise UnknownServerError()

        return data

    async def fetch_cwready(self, tag):
        """Fetch clan war readinesss."""
        url = 'https://royaleapi.com/bot/cwr/{}'.format(tag)
        headers = dict(auth=self.bot_auth)
        error_dict = {
            404: TagNotFound
        }
        return await self.fetch_json(url, headers=headers, error_dict=error_dict)

    async def fetch_clan(self, tag, session):
        headers = dict(Authorization="Bearer {}".format(self.config.get('auth')))
        url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
        error_dict = {
            404: TagNotFound
        }
        return await self.fetch_json(url, headers=headers, error_dict=error_dict)

    async def fetch_clans(self, tags):
        """Fetch clan info by tags."""
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )

        async with aiohttp.ClientSession(connector=conn) as session:
            data_list = await asyncio.gather(*[self.fetch_clan(tag, session) for tag in tags])

        return data_list

    async def fetch_cwr_requirements(self, tags):
        """Fetch CWR requirements by clan."""
        data_list = await self.fetch_clans(tags)
        req = []

        for data in data_list:
            tag = clean_tag(data.get('tag', ''))
            name = data.get('name', '')
            desc = data.get('description', '')
            # cw coverage
            legendary = 0
            gold = 0
            match = re.search('(\d+)L(\d+)G', desc)
            if match is not None:
                legendary = match.group(1)
                gold = match.group(2)
                if len(gold) == 1:
                    gold = "{}0".format(gold)
                if len(legendary) == 1:
                    legendary = "{}0".format(legendary)

            req.append(dict(
                tag=tag,
                name=name,
                legendary=int(legendary),
                gold=int(gold)
            ))

        return req

    async def test_cwr_requirements(self, cwr_data):
        """Find which clan candidate meets requirements for."""
        qual = []

        # test minimum challenge wins
        if cwr_data.get('challenge_max_wins', 0) < self.config.get('min_challenge_wins', 0):
            return qual

        tags = [clan.get('tag') for clan in self.config.get('clans', [])]
        reqs = await self.fetch_cwr_requirements(tags)

        cwr_legendary = 0
        cwr_gold = 0
        for league in cwr_data.get('leagues', []):
            if league.get('key') == 'legendary':
                cwr_legendary = round(league.get('total_percent', 0) * 100)
            if league.get('key') == 'gold':
                cwr_gold = round(league.get('total_percent', 0) * 100)

        for req in reqs:
            if cwr_legendary >= req.get('legendary') and cwr_gold >= req.get('gold'):
                qual.append(req)

        return qual

    async def fetch_cw_history(self, tag):
        url = (
            "https://royaleapi.com"
            "/bot/player/cw_history?player_tag={tag}"
            "&auth={auth}".format(
                tag=tag,
                auth=self.bot_auth
            )
        )
        data = await self.fetch_json(url, error_dict={404: TagNotFound})
        return data

    async def cwready_embed(self, data, hist):
        """CWR embed"""

        tag = data.get('tag')
        player_url = "https://royaleapi.com/player/{}".format(tag)

        em = discord.Embed(
            title="{name} #{tag}".format(name=data.get('name'), tag=data.get('tag')),
            description="Clan War Readiness",
            url=player_url
        )
        # em.url = player_url
        # stats
        clan_name = data.get('clan', {}).get('name', '')
        clan_tag = data.get('clan', {}).get('tag', '')
        em.add_field(name='Clan', value="{} #{}".format(clan_name, clan_tag))
        em.add_field(
            name='Trophies',
            value="{trophies} / {pb} PB :trophy:".format(
                trophies=data.get('trophies', 0),
                pb=data.get('trophies_best', 0)
            ))
        em.add_field(name='War Wins', value=data.get('war_day_wins', 0))
        em.add_field(name='War Cards', value=data.get('clan_cards_collected', 0))
        em.add_field(name='Challenge Max Wins', value=data.get('challenge_max_wins', 0))
        em.add_field(name='Challenge Cards Won', value=data.get('challenge_cards_won', 0))

        # Add maxed
        maxed = dict(
            key='maxed',
            name='Maxed',
            levels='Lvl 13',
            total=0,
            total_percent=0,
            cards=[]
        )
        for league in data.get('leagues', []):
            if league.get('key') == 'legendary':
                cards = []
                for card in league.get('cards', []):
                    if card.get('overlevel'):
                        maxed['cards'].append(dict(
                            key=card.get('key'),
                            overlevel=False
                        ))
                    else:
                        cards.append(dict(
                            key=card.get('key'),
                            overlevel=False
                        ))
                league.update(dict(cards=cards))

        total_card_count = len(await get_card_constants())
        maxed.update(dict(
            total=len(maxed['cards']),
            total_percent=len(maxed['cards']) / total_card_count
        ))
        data['total_maxed'] = len(maxed['cards'])

        data['leagues'].insert(0, maxed)

        # leagues
        for league in data.get('leagues', []):
            name = league.get('name')
            total = league.get('total', 0)
            percent = league.get('total_percent', 0)
            levels = league.get('levels', 0)
            f_name = "{name} .. {percent:.0%} .. {levels}".format(
                name=name, total=total, percent=percent, levels=levels
            )
            cards = league.get('cards', [])

            groups = grouper(cards, 20)
            for index, crds in enumerate(groups):
                value = ""
                for card in crds:
                    if card is not None:
                        value += get_emoji(self.bot, card.get('key', None).replace('-', ''))
                em.add_field(name=f_name if index == 0 else '\u2800', value=value, inline=False)

        # CW History: Detail
        if isinstance(hist, dict):
            if hist.get('win_rate'):
                em.add_field(
                    name='Win %',
                    value='Last 10: {last_10:.0%}, Last 20: {last_20:.0%}, Lifetime: {lifetime:.0%}'.format(
                        **hist.get('win_rate'))
                )


            battles = hist.get('battles')
            if battles:
                battle_list = []
                mia_last20 = 0
                mia_last20_percent = 0

                for b in battles[:20]:
                    league = b.get('league')
                    if league is not None:
                        league_name = 'cwl{}'.format(league).replace('-', '')
                        b['league_emoji'] = get_emoji(self.bot, league_name)
                    else:
                        b['league_emoji'] = get_emoji(self.bot, 'clanwar')
                    battle_list.append('{league_emoji}{wins}/{battles_played}'.format(**b))

                    if b.get('battles_played', 1) == 0:
                        mia_last20 += 1

                if len(battles):
                    mia_last20_percent = mia_last20 / len(battles)

                mia_str = 'No MIA'
                if mia_last20 != 0:
                    mia_str = 'MIA: {mia_last20} / {count}: {mia_last20_percent:.0%}'.format(
                        mia_last20=mia_last20,
                        count=len(battles),
                        mia_last20_percent=mia_last20_percent
                    )

                em.add_field(
                    name='Last 20 Battles : {mia_str}'.format(mia_str=mia_str),
                    value=' '.join(battle_list)
                )
        else:
            em.add_field(
                name='No Clan War History',
                value=(
                    'RoyaleAPI does not have this player’s history in database. '
                    'This simply means that his/her clans have not accessed their CW analytics before.'
                )
            )

        em.set_footer(text=player_url, icon_url='https://smlbiobot.github.io/img/cr-api/cr-api-logo.png')

        return em

    @checks.mod_or_permissions()
    @commands.command(name="cwrconfig", pass_context=True, no_pm=True)
    async def cwr_config(self, ctx):
        """Upload config yaml file. See config.example.yml for how to format it."""
        if len(ctx.message.attachments) == 0:
            await self.bot.say(
                "Please attach config yaml with this command. "
                "See config.example.yml for how to format it."
            )
            return

        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(CONFIG_YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(CONFIG_YAML))

        self.settings['config'] = CONFIG_YAML
        dataIO.save_json(JSON, self.settings)

        # reset config so it will reload
        self._config = None

        await self.bot.delete_message(ctx.message)


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
    n = CWReady(bot)
    bot.add_cog(n)
