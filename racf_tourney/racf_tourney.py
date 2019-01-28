"""
The MIT License (MIT)

Copyright (c) 2019 SML

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

from collections import defaultdict

import discord
import os
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "settings.json")
JSON = os.path.join(PATH, "settings.json")

ROYALEAPI_A = 'PV98LY0P'
ROYALEAPI_B = 'PQGU8RQ0'
ROYALEAPI_C = 'P0VGU80L'
ROYALEAPI_D = 'P8VLQPVL'
ROYALEAPI_E = 'P2QYLV0V'
ROYALEAPI_F = 'PQUGVQU8'
ROYALEAPI_G = 'Y2LGRU0Q'
ROYALEAPI_Z = 'P0VPRCRC'
ROYALEAPI_M = '9R8G9290'

TOURNEY_NAMES = {
    'nnmod': {
        'clan_tags': [
            ROYALEAPI_A,
            ROYALEAPI_B,
            ROYALEAPI_C,
            ROYALEAPI_D,
            ROYALEAPI_E,
            ROYALEAPI_Z
        ]
    }
}


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


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


class RACFTourney:
    """Family Tournament signups"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    def _check_settings(self, server, name=None):
        """Check and verify settings. Init if necessary"""
        if server.id not in self.settings:
            self.settings[server.id] = {}

        if name is not None:
            if name not in self.settings[server.id]:
                self.settings[server.id][name] = dict(
                    players={}
                )

        self._save_settings()

    def _save_settings(self):
        dataIO.save_json(JSON, self.settings)

    def _get_player(self, discord_id=None):
        """Get player tag by discord ID"""
        if discord_id is not None:
            cog = self.bot.get_cog("RACFAudit")
            for tag, p in cog.players.items():
                if p.get('user_id') == discord_id:
                    return p

        return None

    @commands.group(aliases=["rtourney"], pass_context=True, no_pm=True)
    async def racf_tourney(self, ctx):
        """RACF Tournaments."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @racf_tourney.command(name="remove", pass_context=True)
    @checks.mod_or_permissions()
    async def _remove_player(self, ctx, name=None, player: discord.Member = None):
        """Remove player from tourney using discord user id"""
        if name is None:
            await self.bot.say("Please specify the name of the tourney")
            return

        if player is None:
            await self.bot.say("Please specific the player to remove")
            return

        server = ctx.message.server
        players = self.settings.get(server.id, {}).get(name, {}).get('players', {})

        if player.id not in players:
            await self.bot.say("Cannot find player in that tourney")
            return

        self.settings[server.id][name]['players'].pop(player.id)
        self._save_settings()
        await self.bot.say("Player removed from tourney.")

    @racf_tourney.command(name="list", pass_context=True)
    async def _list_players(self, ctx, name=None):
        """List players"""
        # validate tourneys
        if name not in TOURNEY_NAMES:
            await self.bot.say(
                "You must enter a valid tourney name. \n{}".format(
                    "\n".join(["- {}".format(n) for n in TOURNEY_NAMES])
                )
            )
            await self.bot.say("Aborting")
            return

        o = [
            'Players participating in **{}**:'.format(name)
        ]

        server = ctx.message.server
        for author_id, player in self.settings.get(server.id, {}).get(name, {}).get('players', {}).items():
            o.append("- {player_name} #{player_tag}, {clan_name}".format(**player))

        for page in pagify('\n'.join(o)):
            await self.bot.say(page)

    @racf_tourney.command(name="signup", pass_context=True)
    async def _signup(self, ctx, name=None):
        """Signup."""
        # validate tourneys
        if name not in TOURNEY_NAMES:
            await self.bot.say(
                "You must enter a valid tourney name. \n{}".format(
                    "\n".join(["- {}".format(n) for n in TOURNEY_NAMES])
                )
            )
            await self.bot.say("Aborting")
            return

        author = ctx.message.author
        server = ctx.message.server

        # abort if exist
        self._check_settings(server, name=name)
        if self.settings.get(server.id, {}).get(name, {}).get('players', {}).get(author.id):
            await self.bot.say("You are already registered to this tourney. Aborting…")
            return

        # must be member
        member_role = discord.utils.get(server.roles, name="Member")
        if member_role not in author.roles:
            await self.bot.say("You must be a member to signup for our tournaments")
            return

        player = self._get_player(discord_id=author.id)

        # load data from api
        cog = self.bot.get_cog("RACFAudit")
        if not cog:
            await self.bot.say("RACFAudit is not loaded. Aborting…")
            return

        api = cog.api
        url = 'https://api.clashroyale.com/v1/players/%23{}'.format(player.get('tag'))
        p_model = {}
        try:
            p_model = await api.fetch(url)
        except Exception as e:
            await self.bot.say("API Error. Aborting…")

        player_tag = clean_tag(player.get('tag', ''))
        player_name = p_model.get('name', '')
        clan_tag = clean_tag(p_model.get('clan', {}).get('tag', ''))
        clan_name = p_model.get('clan', {}).get('name', '')

        # validate clan tags
        if clan_tag not in TOURNEY_NAMES.get(name, {}).get('clan_tags', []):
            await self.bot.say("Sorry, but your current clan does not qualify for this tournament. Aborting…")
            return

        # register

        self.settings[server.id][name]['players'][author.id] = {
            'user_id': author.id,
            'player_name': player_name,
            'player_tag': player_tag,
            'clan_tag': clan_tag,
            'clan_name': clan_name
        }
        self._save_settings()
        await self.bot.say(
            "You have successfully registered to **{tourney}** as {name} #{tag}, {clan_name} #{clan_tag}".format(
                tourney=name,
                name=player_name,
                tag=player_tag,
                clan_name=clan_name,
                clan_tag=clan_tag
            )
        )


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
    n = RACFTourney(bot)
    bot.add_cog(n)
