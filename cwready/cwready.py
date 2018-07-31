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
import aiohttp
import logging
import socket

logger = logging.getLogger(__name__)

PATH = os.path.join("data", "cwready")
JSON = os.path.join(PATH, "settings.json")

class TagNotFound(Exception):
    pass


class UnknownServerError(Exception):
    pass

def grouper(n, iterable, fillvalue=None):
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

    # @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=['cwrt'])
    async def cwreadytag(self, ctx, tag):
        """Return clan war readiness."""
        tag = clean_tag(tag)

        try:
            em = await self.cwready_embed(tag)
            # em, txt = await self.cwready_embed2(tag)
        except Exception as e:
            logger.exception("Unknown exception", e)
            await self.bot.say("Server error: {}".format(e))
        else:
            await self.bot.say(embed=em)
            # await self.bot.say(embed=em)
            # for page in pagify("\n".join(txt)):
            #     if len(page):
            #         await self.bot.say(page)



    # @checks.mod_or_permissions(manage_roles=True)
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
            # em, txt = await self.cwready_embed2(tag)
            em = await self.cwready_embed(tag)
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
            await self.bot.say(embed=em)
            # for page in pagify("\n".join(txt)):
            #     await self.bot.say(page)

    async def cwready_text(self, tag):
        url = 'https://royaleapi.com/data/member/war/ready/{}'.format(tag)
        player_url = "https://royaleapi.com/player/{}".format(tag)
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                elif resp.status == 404:
                    raise TagNotFound()
                else:
                    raise UnknownServerError()

        out = [
            "{name} #{tag}".format(name=data.get('name'), tag=data.get('tag')),
            "Clan War Readiness",
            player_url
        ]


        clan_name = data.get('clan', {}).get('name', '')
        clan_tag = data.get('clan', {}).get('tag', '')
        out += [
            "{} #{}".format(clan_name, clan_tag),
            "{trophies} / {pb} PB :trophy:".format(
                trophies=data.get('trophies', 0),
                pb=data.get('trophies_best', 0)
            )
        ]
        out += [
            "War Wins: {}".format(data.get('war_day_wins', 0)),
            "War Cards: {}".format(data.get('clan_cards_collected', 0)),
            "Challenge Max Wins: {}".format(data.get('challenge_max_wins', 0)),
            "Challenge Cards Won: {}".format(data.get('challenge_cards_won', 0))
        ]

        # leagues
        for league in data.get('leagues'):
            name = league.get('name')
            total = league.get('total', 0)
            percent = league.get('total_percent', 0)
            levels = league.get('levels', 0)
            f_name = "{name} League .. {percent:.0%} .. {levels}".format(
                name=name, total=total, percent=percent, levels=levels
            )

            out += [f_name]

            cards = league.get('cards', [])


            value = ""
            for card in cards:
                if card is not None:
                    value += get_emoji(self.bot, card.get('key', None).replace('-', ''))
                    if card.get('overlevel'):
                        value += '+'
            out += [value]

        return out


    async def cwready_embed(self, tag):
        url = 'https://royaleapi.com/data/member/war/ready/{}'.format(tag)
        player_url = "https://royaleapi.com/player/{}".format(tag)
        conn = aiohttp.TCPConnector(
            family=socket.AF_INET,
            verify_ssl=False,
        )
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                elif resp.status == 404:
                    raise TagNotFound()
                else:
                    raise UnknownServerError()

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
