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

from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

PATH = os.path.join("data", "banned")
JSON = os.path.join(PATH, "settings.json")

CREDENTIALS_FILENAME = "sheets-credentials.json"
CREDENTIALS_JSON = os.path.join(PATH, CREDENTIALS_FILENAME)

SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
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
        if server.id not in self.settings:
            self.settings[server.id] = {}
        self.settings[server.id]["SHEET_ID"] = id
        await self.bot.say("Saved Google Spreadsheet ID.")
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True)
    async def banned(self, ctx):
        """Banned players."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    def get_sheet(self, ctx):
        """Return values from spreadsheet."""
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_KEY_JSON, scopes=SCOPES)
        http = credentials.authorize(httplib2.Http())
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=discoveryUrl)

        server = ctx.message.server
        spreadsheetId = self.settings[server.id]["SHEET_ID"]

        rangeName = 'Sheet1!A:D'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        values = result.get('values', [])

        return values

    def get_players(self, ctx):
        """Return lisst of players as dictionary."""
        sheet = self.get_sheet(ctx)
        rows = sheet[1:]
        players = []
        for row in rows:
            player = {}
            for id, field in enumerate(FIELDS):
                player[field] = row[id] if id < len(row) else None
            players.append(player)
        return players

    @banned.command(name="list", pass_context=True)
    async def banned_list(self, ctx, *, args=None):
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

        # for row in rows:
        #     if len(row) < max_columns:
        #         row.extend([''] * (max_columns - len(row)))
        #     # data = str(row)
        #     data = '+ {} ({})'.format(row[0], row[1])
        #     out.append(data)

        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)

    @banned.command(name="tag", pass_context=True)
    async def banned_tag(self, ctx, tag):
        """Show banned player by player tag."""



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

