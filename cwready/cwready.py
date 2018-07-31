"""
Clan War Readiness
"""

import itertools
from collections import defaultdict

import aiohttp
import asyncio
import discord
import logging
import os
import re
import socket
from discord.ext import commands
from ruamel.yaml import YAML

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

logger = logging.getLogger(__name__)

PATH = os.path.join("data", "cwready")
JSON = os.path.join(PATH, "settings.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")


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
            yaml = YAML()
            with open(CONFIG_YAML) as f:
                self._config = yaml.load(f)
        return self._config

    @commands.command(pass_context=True, no_pm=True, aliases=['cwrt'])
    async def cwreadytag(self, ctx, tag):
        """Return clan war readiness."""
        tag = clean_tag(tag)

        try:
            data = await self.fetch_cwready(tag)
        except Exception as e:
            logger.exception("Unknown exception", e)
            await self.bot.say("Server error: {}".format(e))
        else:
            await self.bot.say(embed=self.cwready_embed(data))
            await self.test_cwr_requirements_results(ctx, data)

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

        try:
            data = await self.fetch_cwready(tag)

        except TagNotFound:
            await self.bot.say("Invalid tag #{}. Please verify that tag is set correctly.".format(tag))
            return
        except UnknownServerError:
            await self.bot.say("Unknown server error from API")
            return
        except Exception as e:
            logger.exception("Unknown exception", e)
            await self.bot.say("Server error: {}".format(e))
        else:
            await self.bot.say(embed=self.cwready_embed(data))
            await self.test_cwr_requirements_results(ctx, data)

    async def test_cwr_requirements_results(self, ctx, data):
        clans = await self.test_cwr_requirements(data)
        if len(clans) == 0:
            await self.bot.say("User does not meet requirements for any of our clans.")
        else:
            await self.bot.say("Qualified clans: {}. {}".format(
                ", ".join([clan.get('name') for clan in clans]),
                self.config.get('addendum', '')
            ))

    async def fetch_cwready(self, tag):
        """Fetch clan war readinesss."""
        url = 'https://royaleapi.com/data/member/war/ready/{}'.format(tag)
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        data = dict()
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                elif resp.status == 404:
                    raise TagNotFound()
                else:
                    raise UnknownServerError()

        return data

    async def fetch_clan(self, tag, session):
        headers = dict(Authorization="Bearer {}".format(self.config.get('auth')))
        url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
        data = dict()
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
            elif resp.status == 404:
                raise TagNotFound()
            else:
                raise UnknownServerError()

        return data

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

        for req in reqs:
            legendary = False
            gold = False
            for league in cwr_data.get('leagues', []):
                if league.get('key') == 'legendary':
                    if league.get('total_percent', 0) * 100 >= req.get('legendary'):
                        legendary = True
                elif league.get('key') == 'gold':
                    if league.get('total_percent', 0) * 100 >= req.get('gold'):
                        gold = True

            if legendary and gold:
                qual.append(req)

        return qual

    def cwready_embed(self, data):

        tag = data.get('tag')
        url = 'https://royaleapi.com/data/member/war/ready/{}'.format(tag)
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

        # leagues
        for league in data.get('leagues'):
            name = league.get('name')
            total = league.get('total', 0)
            percent = league.get('total_percent', 0)
            levels = league.get('levels', 0)
            f_name = "{name} League .. {percent:.0%} .. {levels}".format(
                name=name, total=total, percent=percent, levels=levels
            )
            cards = league.get('cards', [])

            groups = grouper(cards, 20)
            for index, crds in enumerate(groups):
                value = ""
                for card in crds:
                    if card is not None:
                        value += get_emoji(self.bot, card.get('key', None).replace('-', ''))
                        if card.get('overlevel'):
                            value += '+'
                em.add_field(name=f_name if index == 0 else '.', value=value, inline=False)

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
