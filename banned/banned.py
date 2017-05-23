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
import datetime as dt
import httplib2
import aiohttp

import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help

# from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

import gspread
from fuzzywuzzy import fuzz

PATH = os.path.join("data", "banned")
JSON = os.path.join(PATH, "settings.json")

CREDENTIALS_FILENAME = "sheets-credentials.json"
CREDENTIALS_JSON = os.path.join(PATH, CREDENTIALS_FILENAME)

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
SERVICE_KEY_JSON = os.path.join(PATH, "service_key.json")
APPLICATION_NAME = "Red Discord Bot Banned Cog"

FIELDS = [
    'IGN',
    'PlayerTag',
    'Reason',
    'ImageLink',
    'Date'
]


class Player:
    """Player. A row in Sheet."""

    def __init__(
            self, ign=None, tag=None,
            reason=None, link=None, banned_date=None):
        """Constructor."""
        self.ign = ign
        self.tag = tag
        self.reason = reason
        self.link = link
        self.banned_date = banned_date


class Banned:
    """Manage people who are banned from the RACF.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def check_server_settings(self, server):
        """check server settings. Init if necessary."""
        if server.id not in self.settings:
            self.settings[server.id] = {}
        if "SHEET_ID" not in self.settings[server.id]:
            self.settings[server.id]["SHEET_ID"] = ""
        if "ROLES" not in self.settings[server.id]:
            self.settings[server.id]["ROLES"] = []
        dataIO.save_json(JSON, self.settings)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def setbanned(self, ctx):
        """Set banned settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setbanned.command(name="servicekey", pass_context=True)
    async def setbanned_servicekey(self, ctx):
        """Set Google API service account key.

        This is a json file downloaable from the Google API Console.
        """
        TIMEOUT = 30.0
        await self.bot.say(
            "Please upload the Google API service account key (json). "
            "[Timeout: {} seconds]".format(TIMEOUT))
        attach = await self.bot.wait_for_message(
            timeout=TIMEOUT,
            author=ctx.message.author)
        if attach is None:
            await self.bot.say("Operation time out.")
            return
        if not len(attach.attachments):
            await self.bot.say("Cannot find attachments.")
            return
        attach = attach.attachments[0]
        url = attach["url"]

        async with aiohttp.get(url) as cred:
            with open(SERVICE_KEY_JSON, "wb") as f:
                f.write(await cred.read())

        await self.bot.say(
            "Attachment received and saved as {}".format(SERVICE_KEY_JSON))

    @setbanned.command(name="sheetid", pass_context=True)
    async def setbanned_sheetid(self, ctx, id):
        """Set Google Spreadsheet ID.

        Example:
        https://docs.google.com/spreadsheets/d/1A2B3C/edit

        If Google Spreadsheet’s URL is above, then its ID is 1A2B3C
        """
        server = ctx.message.server
        self.check_server_settings(server)
        self.settings[server.id]["SHEET_ID"] = id
        await self.bot.say("Saved Google Spreadsheet ID.")
        dataIO.save_json(JSON, self.settings)

    @setbanned.command(name="info", pass_context=True)
    async def setbanned_info(self, ctx):
        """Display settings."""
        server = ctx.message.server
        self.check_server_settings(server)
        em = discord.Embed(title="Banned: Settings")
        em.add_field(
            name="Spreadsheet ID",
            value=self.settings[server.id]["SHEET_ID"])
        em.add_field(
            name="Service Key Uploaded",
            value=os.path.exists(SERVICE_KEY_JSON))
        role_ids = self.settings[server.id]["ROLES"]
        roles = [discord.utils.get(server.roles, id=id) for id in role_ids]
        role_names = [r.name for r in roles]
        if len(role_names):
            em.add_field(
                name="Roles with edit permission",
                value=', '.join(role_names))
        else:
            em.add_field(
                name="Roles with edit permission",
                value="None")
        await self.bot.say(embed=em)

    @setbanned.command(name="addrole", pass_context=True)
    async def setbanned_addrole(self, ctx, *, role):
        """Add roles allowed to edit bans."""
        server = ctx.message.server
        self.check_server_settings(server)
        server_role = discord.utils.get(server.roles, name=role)
        if server_role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(role))
            return
        self.check_server_settings(server)
        if server_role.id in self.settings[server.id]["ROLES"]:
            await self.bot.say(
                '{} is already in the list.'.format(role))
            return
        self.settings[server.id]["ROLES"].append(server_role.id)
        role_ids = self.settings[server.id]["ROLES"]
        roles = [discord.utils.get(server.roles, id=id) for id in role_ids]
        role_names = [r.name for r in roles]
        await self.bot.say(
            'List of roles updated: {}.'.format(
                ', '.join(role_names)))
        dataIO.save_json(JSON, self.settings)

    @setbanned.command(name="removerole", pass_context=True)
    async def setbanned_removerole(self, ctx, *, role):
        """Remove roles allowed to edit bans."""
        server = ctx.message.server
        self.check_server_settings(server)
        server_role = discord.utils.get(server.roles, name=role)
        if server_role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(role))
            return
        self.check_server_settings(server)
        if server_role.id not in self.settings[server.id]["ROLES"]:
            await self.bot.say(
                '{} is not on in the list.'.format(role))
            return
        self.settings[server.id]["ROLES"].remove(server_role.id)
        await self.bot.say(
            'Removed {} from list of roles.'.format(role))
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    async def banned(self, ctx):
        """Banned players."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    def get_sheet(self, ctx) -> gspread.Worksheet:
        """Return values from spreadsheet."""
        server = ctx.message.server

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_KEY_JSON, scopes=SCOPES)
        spreadsheetId = self.settings[server.id]["SHEET_ID"]
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(spreadsheetId)
        worksheet = sh.get_worksheet(0)

        return worksheet

    def get_players(self, ctx):
        """Return lisst of players as dictionary."""
        sheet = self.get_sheet(ctx)
        records = sheet.get_all_records(default_blank="-")
        return records

    @banned.command(name="list", pass_context=True)
    async def banned_list(self, ctx):
        """List banned players.

        By default, list only player names and tags,
        sorted alphabetically by name,

        Optional arguments.
        """
        players = self.get_players(ctx)
        players = sorted(players, key=lambda x: x['IGN'])

        out = [
            '+ {} ({})'.format(player['IGN'], player['PlayerTag'])
            for player in players]

        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)

    def player_embed(self, ctx, player):
        """Return Discord embed of player info."""
        server = ctx.message.server
        title = 'Banned Player'
        em = discord.Embed(title=title)
        fields = ['IGN', 'PlayerTag', 'Reason', 'Date']
        for field in fields:
            if player[field] is not None:
                em.add_field(name=field, value=player[field])
        if player['ImageLink'] is not None:
            em.set_image(url=player['ImageLink'])
        em.set_footer(text=server.name, icon_url=server.icon_url)
        return em

    @banned.command(name="tag", pass_context=True)
    async def banned_tag(self, ctx, tag):
        """Show banned player by player tag."""
        if not tag.startswith('#'):
            tag = '#{}'.format(tag)
        players = self.get_players(ctx)
        player = None
        for p in players:
            if p['PlayerTag'] == tag:
                player = p
                break
        if player is None:
            await self.bot.say('Cannot find player with that tag.')
            return

        await self.bot.say(embed=self.player_embed(ctx, player))

    @banned.command(name="ign", pass_context=True, aliases=['name'])
    async def banned_ign(self, ctx, *, ign):
        """Find player by IGN."""
        players = self.get_players(ctx)
        player = None

        # find exact match
        for p in players:
            if p['IGN'] == ign:
                player = p
                break

        if player is not None:
            await self.bot.say(embed=self.player_embed(ctx, player))
            return

        # find fuzzy match
        fuzz_ratio = []
        for id, p in enumerate(players):
            ratio = fuzz.ratio(ign, p['IGN'])
            fuzz_ratio.append({
                "id": id,
                "ratio": ratio,
                "player": p
            })
        fuzz_ratio = sorted(fuzz_ratio, key=lambda x: x["ratio"], reverse=True)

        await self.bot.say('Exact IGN not found. Showing closest match:')
        await self.bot.say(
            embed=self.player_embed(
                ctx, fuzz_ratio[0]["player"]))

        out = []
        list_max = 5
        out.append('Here are other top matches:'.format(list_max))

        for r in fuzz_ratio[1:list_max + 1]:
            player = r["player"]
            out.append('+ {} ({})'.format(player['IGN'], player['PlayerTag']))

        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)


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
    n = Banned(bot)
    bot.add_cog(n)

