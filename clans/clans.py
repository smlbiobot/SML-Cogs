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

import argparse
import asyncio
import datetime as dt
import json
import os
import re
from collections import defaultdict

import aiohttp
import arrow
import discord
import humanfriendly
import unidecode
import yaml
from box import Box
from cogs.utils import checks
from cogs.utils.chat_formatting import bold
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord import DiscordException
from discord.ext import commands

PATH = os.path.join("data", "clans")
JSON = os.path.join(PATH, "settings.json")
CACHE = os.path.join(PATH, "cache.json")
SAVE_CACHE = os.path.join(PATH, "save_cache.json")
CONFIG_YAML = os.path.join(PATH, "config.yml")
AUTH_YAML = os.path.join(PATH, "auth.yml")
BADGES = os.path.join(PATH, "alliance_badges.json")
CLAN_WARS_INTERVAL = dt.timedelta(minutes=5)
CLAN_WARS_SLEEP = 10
CLAN_WARS_CACHE = os.path.join(PATH, "clan_wars_cache.json")

EMOJI_CW_TROPHY = '<:cwtrophy:450878327880941589>'

TASK_INTERVAL = 57


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


def clean_tag(tag):
    """clean up tag."""
    if tag is None:
        return None
    t = tag
    if t.startswith('#'):
        t = t[1:]
    t = t.strip()
    t = t.upper()
    return t


def format_timespan(seconds, short=False, pad=False):
    """Wrapper for human friendly, shorten words."""
    h = humanfriendly.format_timespan(int(seconds))
    if short:
        h = h.replace(' weeks', 'w')
        h = h.replace(' week', 'w')
        h = h.replace(' days', 'd')
        h = h.replace(' day', 'd')
        h = h.replace(' hours', 'h')
        h = h.replace(' hour', 'h')
        h = h.replace(' minutes', 'm')
        h = h.replace(' minute', 'm')
        h = h.replace(' seconds', 's')
        h = h.replace(' second', 's')
        h = h.replace(',', '')
        h = h.replace(' and', '')
        h = h.replace('  ', ' ')
    else:
        h = h.replace('week', 'wk')
        h = h.replace('hour', 'hr')
        h = h.replace('minute', 'min')
        h = h.replace('second', 'sec')
    if pad:
        h = ' ' + h
        h = re.sub('(\D)(\d)(\D)', r'\g<1>0\2\3', h)
        h = h.strip()
    return h


def smart_truncate(content, length=100, suffix='...'):
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length + 1].split(' ')[0:-1]) + suffix


def emoji_value(emoji, value, pad=5, inline=True, truncate=True):
    emojis = {
        'win': '<:cwwarwin:450890799312404483>',
        'crown': '<:crownblue:337975460405444608>',
        'battle': '<:cwbattle:450889588215513089>',
        'trophy': ':trophy:',
        'laddertrophy': '<:laddertrophy:337975460451319819>',
        'cwtrophy': '<:cwtrophy:450878327880941589>',
    }
    value = str(value)

    if truncate:
        value = value[:pad]

    s_value = '{: >{width}}'.format(value, width=pad)

    if inline:
        s_value = wrap_inline(s_value)

    if emoji in emojis.keys():
        s = "{} {}".format(s_value, emojis[emoji])
    else:
        s = s_value
    return s


def wrap_inline(str):
    return '`\u2800{}\u2800`'.format(str)


class APIError(Exception):
    def __init__(self, message):
        self.message = message


class Clans:
    """Auto parse clan info and display requirements"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.badges = dataIO.load_json(BADGES)
        self._auth = None
        self.task = None

        provider = self.settings.get('provider')
        if provider is None:
            provider = 'cr-api'

        # add auto tasks
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self.auto_tasks())

    def __unload(self):
        """Remove task when unloaded."""
        try:
            self.task.cancel()
        except Exception:
            pass

    async def auto_tasks(self):
        try:
            while True:
                if self == self.bot.get_cog("Clans"):
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        self.post_auto_clans()
                    )
                    loop.create_task(
                        self.post_clanwars()
                    )

                    await asyncio.sleep(TASK_INTERVAL)
        except asyncio.CancelledError:
            pass

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def clansset(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @checks.mod_or_permissions()
    @clansset.command(name="api", pass_context=True, no_pm=True)
    async def clansset_api(self, ctx, provider):
        """Set API provider.

        Possible values: cr-api, official
        """
        if provider == 'cr-api':
            self.settings['provider'] = 'cr-api'
        elif provider == 'official':
            self.settings['provider'] = 'official'

        dataIO.save_json(JSON, self.settings)
        await self.bot.say("API Provider updated.")

    @checks.mod_or_permissions()
    @clansset.command(name="config", pass_context=True, no_pm=True)
    async def clansset_config(self, ctx):
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

        await self.bot.delete_message(ctx.message)

    @checks.mod_or_permissions()
    @clansset.command(name="auth", pass_context=True, no_pm=True)
    async def clansset_auth(self, ctx):
        """Upload auth yaml file. See auth.example.yml for how to format it."""
        attach = ctx.message.attachments[0]
        url = attach["url"]

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(AUTH_YAML, "wb") as f:
                    f.write(await resp.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(AUTH_YAML))

        await self.bot.delete_message(ctx.message)

    @property
    def clans_config(self):
        if os.path.exists(CONFIG_YAML):
            with open(CONFIG_YAML) as f:
                config = Box(yaml.safe_load(f), default_box=True)
            return config
        return None

    @property
    def auth(self):
        if self._auth is None:
            if os.path.exists(AUTH_YAML):
                with open(AUTH_YAML) as f:
                    config = yaml.safe_load(f)
                    if self.api_provider == 'cr-api':
                        self._auth = config.get('token')
                    else:
                        self._auth = config.get('token')
        return self._auth

    @property
    def api_provider(self):
        if self.settings.get('provider') == 'official':
            return 'official'
        return 'cr-api'

    async def get_clan(self, tag):
        """Return dict of clan"""
        try:
            if self.api_provider == 'official':
                url = 'https://api.clashroyale.com/v1/clans/%23{}'.format(tag)
                headers = {'Authorization': 'Bearer {}'.format(self.auth)}
            else:
                url = 'http://api.royaleapi.com/clan/{}'.format(tag)
                headers = {'auth': self.auth}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as resp:
                    data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise APIError('json.decoder.JSONDecodeError')
        except asyncio.TimeoutError:
            raise APIError('asyncio.TimeoutError')
        except Exception as e:
            raise APIError('Unknown errors')
        else:
            return data

    async def get_clans(self, tags):
        """Return list of clans"""
        try:
            if self.api_provider == 'official':
                urls = ['https://api.clashroyale.com/v1/clans/%23{}'.format(tag) for tag in tags]
                headers = {'Authorization': 'Bearer {}'.format(self.auth)}
                data = []
                async with aiohttp.ClientSession() as session:
                    for url in urls:
                        async with session.get(url, headers=headers, timeout=30) as resp:
                            data.append(await resp.json())
            else:
                url = 'http://api.royaleapi.com/clan/{}'.format(",".join(tags))
                headers = {'auth': self.auth}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=30) as resp:
                        data = await resp.json()
        except json.decoder.JSONDecodeError:
            raise APIError('json.decoder.JSONDecodeError')
        except asyncio.TimeoutError:
            raise APIError('asyncio.TimeoutError')
        except:
            raise APIError('Unknown error')
        else:
            return data

    @commands.command(pass_context=True, no_pm=True)
    async def clans(self, ctx, *args):
        """Display clan info.

        [p]clans -m   Disable member count
        [p]clans -t   Disable clan tag
        """
        await self.bot.type()
        channel = ctx.message.channel
        await self.post_clans(channel, *args)

    def enable_auto_clan(self, server, channel):
        self.check_settings(server)
        self.settings["auto_clan"]["servers"][server.id].update(dict(
            channel_id=channel.id,
            auto=True
        ))
        self.save_settings()

    def disable_auto_clan(self, server, channel):
        self.check_settings(server)
        self.settings["auto_clan"]["servers"][server.id].update(dict(
            channel_id=None,
            auto=False
        ))
        self.save_settings()

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True, aliases=['auto_clans', 'autoclans'])
    async def auto_clan(self, ctx):
        """Auto display clan info."""
        await self.bot.type()

        server = ctx.message.server
        channel = ctx.message.channel
        self.enable_auto_clan(server, channel)
        message = await self.post_clans(channel)
        await self.bot.purge_from(channel, limit=5, before=message)

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def auto_clan_stop(self, ctx):
        """Stop auto display"""
        server = ctx.message.server
        channel = ctx.message.channel
        self.disable_clanwars(server, channel)

        await self.bot.say("Auto clan update stopped.")

    async def post_auto_clans(self, message=None):
        self.check_settings()
        for server_id, v in self.settings['auto_clan']['servers'].items():
            if v.get('auto'):
                channel_id = v.get('channel_id')
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    message_id = v.get('message_id')
                    msg = None
                    if message_id is not None:
                        try:
                            msg = await self.bot.get_message(channel, message_id)
                        except DiscordException:
                            pass
                    try:
                        message = await self.post_clans(channel, msg=msg)
                    except DiscordException:
                        pass
                    else:
                        v['message_id'] = message.id

        dataIO.save_json(JSON, self.settings)

    async def post_clans(self, channel, *args, msg=None):
        """Post clans to channel."""
        config = self.clans_config
        clan_tags = [clan.tag for clan in config.clans if not clan.hide]

        use_cache = False
        clans = []
        try:
            clans = await self.get_clans(clan_tags)
            dataIO.save_json(CACHE, clans)
        except json.decoder.JSONDecodeError:
            use_cache = True
        except asyncio.TimeoutError:
            use_cache = True

        if use_cache:
            data = dataIO.load_json(CACHE)
            clans = data
            await self.bot.say("Cannot load from API. Loading info from cache.")

        em = discord.Embed(
            title=config.name,
            description=config.description,
            color=discord.Color(int(config.color, 16)),
            timestamp=dt.datetime.utcnow()
        )
        badge_url = None
        show_member_count = "-m" not in args
        show_clan_tag = "-t" not in args

        for clan in clans:
            desc = clan.get('description', '')

            # trophies, pb, psf
            match = re.search('[\d,O]{4,}', desc)
            pb_match = re.search('PB', desc)
            psf_match = re.search('PSF', desc)
            name = clan.get('name')
            if match is not None:
                trophies = match.group(0)
                trophies = trophies.replace(',', '')
                trophies = trophies.replace('O', '0')
            else:
                trophies = clan.get('requiredTrophies')
            pb = ''
            if pb_match is not None:
                pb = ' PB'
            psf = ''
            if psf_match is not None:
                psf = ' PSF'

            # member count
            member_count = ''
            if show_member_count:
                if self.api_provider == 'official':
                    member_count = clan.get('members')
                else:
                    member_count = len(clan.get('members'))

                member_count = ', {} / 50'.format(member_count)

            # clan tag
            clan_tag = ''
            if show_clan_tag:
                clan_tag = ', {}'.format(clan.get('tag'))

            # cw coverage
            cw = ""
            match = re.search('(\d+)L(\d+)G', desc)
            if match is not None:
                legendary = match.group(1)
                gold = match.group(2)
                if len(gold) == 1:
                    gold = "{}0".format(gold)
                if len(legendary) == 1:
                    legendary = "{}0".format(legendary)
                gold = int(gold)
                legendary = int(legendary)
                cw = "\nCWR: {}% Legendary, {}% Gold".format(
                    legendary,
                    gold
                )

            # clan scores + cw trophies
            clan_score_cw_trophies = "{trophy}{cw_trophy}".format(
                trophy=emoji_value('laddertrophy', clan.get('clanScore', 0), 5),
                cw_trophy=emoji_value('cwtrophy', clan.get('clanWarTrophies', 0), 5),
            )

            # aux requirements
            aux = ""
            for c in config.clans:
                if c.tag in clan.get('tag'):
                    if c.get('aux'):
                        aux = '\n{}'.format(c.get('aux'))

            # embed value
            value = '`{trophies}{pb}{psf}{member_count}{clan_tag}`{cw}{aux}\n{clan_score_cw_trophies}'.format(
                clan_tag=clan_tag,
                member_count=member_count,
                trophies=trophies,
                pb=pb,
                psf=psf,
                cw=cw,
                aux=aux,
                clan_score_cw_trophies=clan_score_cw_trophies)
            em.add_field(name=name, value=value, inline=False)

            if badge_url is None:
                if self.api_provider == 'official':
                    for badge in self.badges:
                        if badge.get('id') == clan.get('badgeId'):
                            badge_url = 'https://royaleapi.github.io/cr-api-assets/badges/{}.png'.format(
                                badge.get('name'))
                else:
                    badge_url = clan['badge']['image']

        if badge_url is not None:
            em.set_thumbnail(url=badge_url)

        if config.get('url'):
            em.url = config.get('url')

        for inf in config.info:
            em.add_field(
                name=inf.name,
                value=inf.value
            )

        if msg is None:
            # delete channel messages
            await self.bot.purge_from(channel, limit=5, before=msg)
            msg = await self.bot.send_message(channel, embed=em)
        else:
            await self.bot.edit_message(msg, embed=em)

        return msg

    def search_args_parser(self):
        """Search arguments parser."""
        parser = argparse.ArgumentParser(prog='[p]racfaudit search')

        parser.add_argument(
            'name',
            nargs='?',
            default='_',
            help='IGN')
        parser.add_argument(
            '-c', '--clan',
            nargs='?',
            help='Clan')
        parser.add_argument(
            '-n', '--min',
            nargs='?',
            type=int,
            default=0,
            help='Min Trophies')
        parser.add_argument(
            '-m', '--max',
            nargs='?',
            type=int,
            default=10000,
            help='Max Trophies')
        parser.add_argument(
            '-l', '--link',
            action='store_true',
            default=False
        )

        return parser

    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True)
    async def clanmembersearch(self, ctx, *args):
        """Search for member.

        usage: [p]crmembersearch [-h] [-t TAG] name

        positional arguments:
          name                  IGN

        optional arguments:
          -h, --help            show this help message and exit
          -c CLAN, --clan CLAN  Clan name
          -n MIN --min MIN      Min Trophies
          -m MAX --max MAX      Max Trophies
          -l --link             Display link to royaleapi.com
        """
        parser = self.search_args_parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await self.bot.send_cmd_help(ctx)
            return

        await self.bot.type()
        config = self.clans_config
        clan_tags = [clan.tag for clan in config.clans]

        api_error = False
        clans = []
        try:
            clans = await self.get_clans(clan_tags)
            dataIO.save_json(CACHE, clans)
        except APIError:
            api_error = True

        if api_error:
            await self.bot.say("Cannot load clans from API.")
            return

        members = []
        for clan in clans:
            if self.api_provider == 'official':
                member_list = clan.get('memberList')
            else:
                member_list = clan.get('members')

            for member in member_list:
                member = Box(member)
                member.clan = clan
                member.tag = clean_tag(member.tag)
                members.append(member)

        results = []

        if pargs.name != '_':
            for member in members:
                # simple search
                if pargs.name.lower() in member['name'].lower():
                    results.append(member)
                else:
                    # unidecode search
                    s = unidecode.unidecode(member['name'])
                    s = ''.join(re.findall(r'\w', s))
                    if pargs.name.lower() in s.lower():
                        results.append(member)
        else:
            results = members

        # filter by clan name
        if pargs.clan:
            results = [m for m in results if pargs.clan.lower() in m.clan.name.lower()]

        # filter by trophies
        results = [m for m in results if pargs.min <= m['trophies'] <= pargs.max]

        limit = 10
        if len(results) > limit:
            await self.bot.say(
                "Found more than {0} results. Returning top {0} only.".format(limit)
            )
            results = results[:limit]

        roles = {
            'leader': 'Leader',
            'coleader': 'Co-Leader',
            'elder': 'Elder',
            'member': 'Member'
        }

        if len(results):
            out = []
            for member_model in results:
                member_model['role_name'] = roles[member_model['role'].lower()]
                out.append("**{0.name}** #{0.tag}, {0.clan.name}, {0.role_name}, {0.trophies}".format(member_model))
                if pargs.link:
                    out.append('http://royaleapi.com/player/{}'.format(member_model.tag))
            for page in pagify('\n'.join(out)):
                await self.bot.say(page)
        else:
            await self.bot.say("No results found.")

    def clanwars_str(self, clans):
        """
        Clan Wars info as a str output (save space)
        :param clans: list of clans
        :return: str
        """
        import datetime as dt  # somehow dt not registered from global import

        o = []

        config = self.clans_config
        legend = ("\n{wins} "
                  "{crowns} "
                  "{battles_played}"
                  "{trophies}").format(

            wins=emoji_value('win', 'Wins', inline=False, truncate=False),
            crowns=emoji_value('crown', 'Crowns', inline=False, truncate=False),
            battles_played=emoji_value('battle', 'Battles Played', inline=False, truncate=False),
            trophies=emoji_value('cwtrophy', 'CW Trophies', inline=False, truncate=False)
        )

        o += [
            bold(config.name),
            "Last updated: {}".format(dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')),
            legend
        ]

        # Badge
        badge_url = config.badge_url

        # clan list
        STATES = {
            'collectionDay': 'Coll',
            'warDay': 'War',
            'notInWar': 'N/A',
            'matchMaking': 'MM',
        }

        for c in clans:
            clan = Box(c, default_box=True)
            state = clan.state
            timespan = None
            wins = clan.clan.wins
            crowns = clan.clan.crowns
            battles_played = clan.clan.battlesPlayed

            if state == 'collectionDay':
                end_time = clan.get('collectionEndTime')
            elif state == 'warDay':
                end_time = clan.get('warEndTime')
            else:
                end_time = None

            if end_time is not None:
                dt = arrow.get(end_time, 'YYYYMMDDTHHmmss.SSS').datetime
                now = arrow.utcnow().datetime
                span = dt - now
                hours, remainder = divmod(span.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                timespan = '{: 2}h{: 2}m{: 2}s'.format(int(hours), int(minutes), int(seconds))

            clan_name = clan.clan.name
            clan_score = clan.clan.clanScore
            state = clan.get('state', 'ERR')

            if state in ['collectionDay', 'warDay']:
                o += [
                    "\u2800",
                    (
                            wrap_inline("{clan_name:<15.15} {state: <4} {timespan: >11.11}") +
                            "\n{wins} "
                            "{crowns} "
                            "{battles_played}"
                            "{trophies}"
                    ).format(
                        clan_name=clan_name,
                        state=STATES.get(state, 'ERR'),
                        timespan=timespan or '',
                        wins=emoji_value('win', wins, 2),
                        crowns=emoji_value('crown', crowns, 2),
                        battles_played=emoji_value('battle', battles_played, 3),
                        trophies=emoji_value('cwtrophy', clan_score, 5)
                    )
                ]
            else:
                o += [
                    wrap_inline(
                        "---\nNot in war"
                    )
                ]

        return '\n'.join(o)

    def clanwars_embed(self, clans):
        """Clan wars info embed.

        This allows us to update status easily by supplying new data.
        """
        import datetime as dt  # somehow dt not registered from global import

        config = self.clans_config
        legend = ("\n{wins} "
                  "{crowns} "
                  "{battles_played}"
                  "{trophies}").format(

            wins=emoji_value('win', 'Wins', inline=False, truncate=False),
            crowns=emoji_value('crown', 'Crowns', inline=False, truncate=False),
            battles_played=emoji_value('battle', 'Battles Played', inline=False, truncate=False),
            trophies=emoji_value('cwtrophy', 'CW Trophies', inline=False, truncate=False)
        )
        em = discord.Embed(
            title=config.name,
            color=discord.Color.red(),
            description=(
                    "\nLast updated: {}".format(dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))
                    + legend
            ),
            timestamp=dt.datetime.utcnow()
        )

        # clan list
        STATES = {
            'collectionDay': 'Coll',
            'warDay': 'War',
            'notInWar': 'Not in War',
            'matchMaking': 'Matchmaking',
        }

        for c, cf in zip(clans, config.clans):
            clan = Box(c, default_box=True)
            state = clan.state
            timespan = None
            wins = clan.clan.wins
            crowns = clan.clan.crowns
            battles_played = clan.clan.battlesPlayed

            if state == 'collectionDay':
                end_time = clan.get('collectionEndTime')
            elif state == 'warDay':
                end_time = clan.get('warEndTime')
            else:
                end_time = None

            if end_time is not None:
                dt = arrow.get(end_time, 'YYYYMMDDTHHmmss.SSS').datetime
                now = arrow.utcnow().datetime
                span = dt - now
                hours, remainder = divmod(span.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                timespan = '{: 2}h{: 2}m{: 2}s'.format(int(hours), int(minutes), int(seconds))

            # clan_name = clan.clan.name
            clan_name = cf.name
            clan_score = clan.clan.clanScore
            state = clan.get('state', 'ERR')

            if state in ['collectionDay', 'warDay']:
                value = (
                        wrap_inline("{state: <4} {timespan: >11.11}") +
                        "\n{wins} "
                        "{crowns} "
                        "{battles_played}"
                        "{trophies}"
                ).format(
                    state=STATES.get(state, 'ERR'),
                    timespan=timespan or '',
                    wins=emoji_value('win', wins, 2),
                    crowns=emoji_value('crown', crowns, 2),
                    battles_played=emoji_value('battle', battles_played, 3),
                    trophies=emoji_value('cwtrophy', clan_score, 5)
                )

            else:
                value = wrap_inline(STATES.get(state, 'ERR'))

            em.add_field(name=clan_name, value=value, inline=False)

        # Badge
        badge_url = config.badge_url

        if badge_url is not None:
            em.set_footer(icon_url=badge_url, text=config.name)

        return em

    @property
    def clanwars_settings(self):
        return self.settings.get('clan_wars')

    @clanwars_settings.setter
    def clanwars_settings(self, value):
        self.settings['clan_wars'] = value
        self.save_settings()

    async def set_clanwars_message_id(self, message):
        server = message.server
        s = nested_dict()
        s['clan_wars'][server.id]['message_id'] = message.id
        self.settings.update(s)
        self.save_settings()

    async def update_clanwars(self, message):
        await self.set_clanwars_message_id(message)

    def save_settings(self):
        dataIO.save_json(JSON, self.settings)

    async def update_cw_message(self, message, count_down=None):
        # Only update if in settings
        try:
            server = message.server
            message_id = self.settings['clan_wars'][server.id]["message_id"]
        except KeyError:
            return
        else:
            if message_id != message.id:
                return

        new_message = False

        if count_down is None or dt.datetime.utcnow() > count_down:
            count_down = dt.datetime.utcnow() + CLAN_WARS_INTERVAL
            clans = await self.get_clanwars()
            new_message = True
        elif os.path.exists(CLAN_WARS_CACHE):
            clans = dataIO.load_json(CLAN_WARS_CACHE)
        else:
            clans = await self.get_clanwars()

        s = self.clanwars_str(clans)

        if new_message:
            channel = message.channel
            await self.bot.delete_message(message)
            message = await self.bot.send_message(channel, s)
            await self.set_clanwars_message_id(message)
        else:
            await self.bot.edit_message(message, s)

        self.task = self.bot.loop.create_task(self.update_cw_message(message, count_down=count_down))

    async def fetch(self, session, url):
        async with session.get(url) as response:
            if response.status != 200:
                response.raise_for_status()
            return await response.json()

    async def get_clanwars(self):
        # official
        config = self.clans_config
        clan_tags = [c.tag for c in config.clans if not c.hide]
        war_url_fmt = 'https://api.clashroyale.com/v1/clans/%23{tag}/currentwar'
        info_url_fmt = 'https://api.clashroyale.com/v1/clans/%23{tag}'

        clans = []
        headers = {'Authorization': 'Bearer {}'.format(self.auth)}

        urls = []
        for tag in clan_tags:
            url = war_url_fmt.format(tag=tag)
            urls.append(url)

        async with aiohttp.ClientSession(loop=self.bot.loop, headers=headers) as session:
            clans = await asyncio.gather(
                *[self.bot.loop.create_task(
                    self.fetch(session, url)
                ) for url in urls])

        if clans:
            dataIO.save_json(CLAN_WARS_CACHE, clans)
        return clans

    @commands.group(pass_context=True, aliases=['cw'])
    async def clanwars(self, ctx):
        """Settings"""
        if ctx.invoked_subcommand is None:
            # await self.bot.send_cmd_help(ctx)
            await ctx.invoke(self.clanwars_default)

    @clanwars.command(name='default', pass_context=True, no_pm=True)
    async def clanwars_default(self, ctx):
        """Display clan war info.

        MOD arguments:
        auto: auto-update message with latest data.
        """
        if self.api_provider != 'official':
            await self.bot.say("This command is not supported  for the API provider you have selected.")
            return

        await self.bot.type()

        clans = await self.get_clanwars()
        em = self.clanwars_embed(clans)
        message = await self.bot.say(embed=em)

        # s = self.clanwars_str(clans)
        # for page in pagify(s):
        #     await self.bot.say(page)
        # message = await self.bot.say(s)

    def check_settings(self, server=None):
        """Init server with defaults"""
        # auto clan
        if "auto_clan" not in self.settings:
            self.settings["auto_clan"] = {}
        if "servers" not in self.settings["auto_clan"]:
            self.settings["auto_clan"]["servers"] = {}

        if server is not None:
            if server.id not in self.settings["auto_clan"]['servers']:
                self.settings["auto_clan"]['servers'][server.id] = dict(
                    channel_id=None,
                    auto=False
                )

        # auto clan wars
        if "clan_wars" not in self.settings:
            self.settings['clan_wars'] = {}
        if "servers" not in self.settings["clan_wars"]:
            self.settings['clan_wars']['servers'] = {}

        if server is not None:
            if server.id not in self.settings["clan_wars"]['servers']:
                self.settings["clan_wars"]['servers'][server.id] = dict(
                    channel_id=None,
                    auto=False
                )
        dataIO.save_json(JSON, self.settings)

    def enable_clanwars(self, server, channel):
        self.check_settings(server)
        self.settings["clan_wars"]["servers"][server.id].update(dict(
            channel_id=channel.id,
            auto=True
        ))
        self.save_settings()

    def disable_clanwars(self, server, channel):
        self.check_settings(server)
        self.settings["clan_wars"]["servers"][server.id].update(dict(
            channel_id=None,
            auto=False
        ))
        self.save_settings()

    @checks.mod_or_permissions()
    @clanwars.command(name='auto', pass_context=True, no_pm=True)
    async def clanwars_auto(self, ctx):
        """Auto display clan war info."""
        if self.api_provider != 'official':
            await self.bot.say("This command is not supported  for the API provider you have selected.")
            return

        await self.bot.type()

        server = ctx.message.server
        channel = ctx.message.channel
        self.enable_clanwars(server, channel)
        await self.post_clanwars()

    @checks.mod_or_permissions()
    @clanwars.command(name='stop', pass_context=True, no_pm=True)
    async def clanwars_stop(self, ctx):
        """Stop auto display"""
        server = ctx.message.server
        channel = ctx.message.channel
        self.disable_clanwars(server, channel)

        await self.bot.say("Auto clan wars update stopped.")

    # async def post_clanwars_task(self):
    #     """Task: post embed to channel."""
    #     try:
    #         while True:
    #             if self == self.bot.get_cog("Clans"):
    #                 try:
    #                     await self.post_clanwars()
    #                 except DiscordException as e:
    #                     pass
    #                 await asyncio.sleep(TASK_INTERVAL)
    #     except asyncio.CancelledError:
    #         pass

    async def post_clanwars(self):
        """Post embbed to channel."""
        self.check_settings()
        for server_id, v in self.settings['clan_wars']['servers'].items():
            if v.get('auto'):
                channel_id = v.get('channel_id')
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    # post clan wars status
                    try:
                        clans = await self.get_clanwars()
                    except:
                        pass
                    else:
                        em = self.clanwars_embed(clans)
                        message_id = v.get('message_id')
                        message = None
                        if message_id is not None:
                            try:
                                message = await self.bot.get_message(channel, message_id)
                            except DiscordException:
                                pass

                        if message is None:
                            await self.bot.purge_from(channel, limit=10)
                            message = await self.bot.send_message(channel, embed=em)
                            v["message_id"] = message.id
                            dataIO.save_json(JSON, self.settings)
                        else:
                            await self.bot.edit_message(message, embed=em)

    async def on_message(self, msg):
        """Auto expand clan invite.


        """
        s = msg.content
        m = re.search(
            'https://link.clashroyale.com/invite/clan/..\?tag=(.+)&token=.+&platform=(iOS|android)',
            s
        )
        if not m:
            return

        url = m.group(0)
        tag = m.group(1)

        clan = await self.get_clan(tag)
        clan = Box(clan)

        info_link = "https://royaleapi.com/clan/{tag}".format(tag=tag)
        war_link = "https://royaleapi.com/clan/{tag}/war".format(tag=tag)
        analytics_link = "https://royaleapi.com/clan/{tag}/war/analytics".format(tag=tag)

        title = "Clan Invitation - Clash Royale"
        description = "\n".join([
            "**{name}** #{tag}".format(name=clan.name, tag=tag),
            "{trophies}".format(
                trophies=emoji_value("laddertrophy", clan.clanScore)
            ),
            "{cwtrophies}".format(
                cwtrophies=emoji_value("cwtrophy", clan.clanWarTrophies)
            ),
            "{}".format(clan.description),
            " • ".join([
                "[Info]({info_link})".format(info_link=info_link),
                "[War]({war_link})".format(war_link=war_link),
                "[Analytics]({analytics_link})".format(analytics_link=analytics_link),
            ]),
        ])

        em = discord.Embed(
            title=title,
            description=description,
            url=url,
        )
        em.set_footer(text=info_link)

        await self.bot.delete_message(msg)
        await self.bot.send_message(msg.channel, embed=em)


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
    n = Clans(bot)
    bot.add_cog(n)
