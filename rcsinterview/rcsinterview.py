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
import datetime as date
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

PATH = os.path.join("data", "rcsinterview")
JSON = os.path.join(PATH, "settings.json")

CREDENTIALS_FILENAME = "sheets-credentials.json"
CREDENTIALS_JSON = os.path.join(PATH, CREDENTIALS_FILENAME)

SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
SERVICE_KEY_JSON = os.path.join(PATH, "service_key.json")
APPLICATION_NAME = "Red Discord Bot RCS Interview Cog"


class RCSInterview:
    """Reddit Clan System interviews."""

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def setinterview(self, ctx):
        """Set interview settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setinterview.command(name="servicekey", pass_context=True)
    async def setinterview_servicekey(self, ctx):
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

    @setinterview.command(name="sheetid", pass_context=True)
    async def setinterview_sheetid(self, ctx, id):
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

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def interview(self, ctx):
        """Set interview settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @interview.command(name="get", pass_context=True)
    async def interview_get(self, ctx, app_id):
        """Get interview results by application ID.

        Application ID is a field that is tied to an RCS clan application.
        This was given to the interviewee when they apply.
        It is inserted into the sheet as a value in a cell.
        """
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_KEY_JSON, scopes=SCOPES)
        http = credentials.authorize(httplib2.Http())
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=discoveryUrl)

        server = ctx.message.server
        spreadsheetId = self.settings[server.id]["SHEET_ID"]

        # whole sheet
        rangeName = 'FormResponses!A:O'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()
        values = result.get('values', [])

        if not values:
            await self.bot.say('No data found.')
            return

        # output
        out = []

        # questions: first row
        questions = values[0]
        # for question in questions:
        #     out.append('**{}**'.format(question))

        # app id is column C
        answers = None
        forms = values[1:]
        for form in forms:
            if form[2] == app_id:
                answers = form
                break

        # process answers
        if answers is None:
            await self.bot.say("Application ID not found.")
            return

        for id, question in enumerate(questions):
            out.append(
                '`{}. `**{}**'.format(id + 1, question))
            out.append('')
            out.append(answers[id])
            out.append('')

        # output
        for page in pagify('\n'.join(out), shorten_by=24):
            await self.bot.say(page)




        # await self.bot.say('Name, Major:')
        # for row in values:
        #     # Print columns A and E, which correspond to indices 0 and 4.
        #     await self.bot.say('%s, %s' % (row[0], row[4]))


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
    n = RCSInterview(bot)
    bot.add_cog(n)

