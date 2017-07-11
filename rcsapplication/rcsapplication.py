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
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help

from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

PATH = os.path.join("data", "rcsapp")
JSON = os.path.join(PATH, "settings.json")

CREDENTIALS_FILENAME = "sheets-credentials.json"
CREDENTIALS_JSON = os.path.join(PATH, CREDENTIALS_FILENAME)

SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
SERVICE_KEY_JSON = os.path.join(PATH, "service_key.json")
APPLICATION_NAME = "Red Discord Bot RCS Interview Cog"


class NoDataFound(Exception):
    pass

class ApplicationIdNotFound(Exception):
    pass


class RCSApplication:
    """Reddit Clan System apps."""

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.mod_or_permissions()
    @commands.group(pass_context=True)
    async def setrcsapplication(self, ctx):
        """Set app settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setrcsapplication.command(name="servicekey", pass_context=True)
    async def setrcsapplication_servicekey(self, ctx):
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

    @setrcsapplication.command(name="req", pass_context=True)
    async def setrcsapplication_req(self, ctx, *, requirements):
        """Set RCS Requirements.

        This is an open text field. It can be set to anything,
        and will be displayed to interested parties requesting that info.
        """
        pass

    @setrcsapplication.command(name="sheetid", pass_context=True)
    async def setrcsapplication_sheetid(self, ctx, id):
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
    async def rcsapplication(self, ctx):
        """Set app settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @rcsapplication.command(name="new", pass_context=True)
    async def rcsapplication_new(self, ctx, user: discord.Member):
        """Create a new application ID.

        This will additionally create a link to the Google Form and
        give instruction to the user re: what to do.
        """
        pass

    @rcsapplication.command(name="get", pass_context=True)
    async def rcsapplication_get(self, ctx, app_id):
        """Get app results by application ID.

        Application ID is a field that is tied to an RCS clan application.
        This was given to the interviewee when they app.
        It is inserted into the sheet as a value in a cell.
        """
        await self.bot.send_typing(ctx.message.channel)
        try:
            # out = self.get_application_response(ctx, app_id)
            em = self.get_application_response_embed(ctx, app_id)
        except NoDataFound:
            await self.bot.say('No data found.')
            return
        except ApplicationIdNotFound:
            await self.bot.say("Application ID not found.")
            return

        await self.bot.say(embed=em)

    @rcsapplication.command(name="getmd", pass_context=True)
    async def rcsapplication_getmd(self, ctx, app_id):
        """Return appliation info as markdown."""
        await self.bot.send_typing(ctx.message.channel)
        try:
            out = self.get_application_response(ctx, app_id)
        except NoDataFound:
            await self.bot.say('No data found.')
            return
        except ApplicationIdNotFound:
            await self.bot.say("Application ID not found.")
            return

        for page in pagify(out, shorten_by=80):
            await self.bot.say(box(page, lang="markdown"))

    def get_application_response(self, ctx, app_id):
        """Return application info as text."""
        result = self.get_gspread_result(ctx.message.server)
        values = result.get('values', [])

        if not values:
            # await self.bot.say('No data found.')
            raise NoDataFound()
            return

        # output
        out = []

        # questions: first row
        questions = values[0]
        # questions contain legacy field at end
        questions = questions[:-1]

        # for question in questions:
        #     out.append('**{}**'.format(question))

        # app id is column C
        answers = None
        forms = values[1:]
        for form in forms:
            if form[1] == app_id:
                answers = form
                break

        # process answers
        if answers is None:
            # await self.bot.say("Application ID not found.")
            raise ApplicationIdNotFound()
            return

        for id, question in enumerate(questions):
            out.append(
                '`{}. `**{}**'.format(id + 1, question))
            out.append('')
            if id < len(answers):
                out.append(answers[id])
                out.append('')

        return '\n'.join(out)

    def get_application_response_embed(self, ctx, app_id):
        """Return application info as text."""
        server = ctx.message.server
        result = self.get_gspread_result(server)
        values = result.get('values', [])

        if not values:
            raise NoDataFound()
            return

        # questions: first row
        questions = values[0]
        # questions contain legacy field at end
        questions = questions[:-1]

        # app id is column C
        answers = None
        forms = values[1:]
        for form in forms:
            if form[1] == app_id:
                answers = form
                break

        # process answers
        if answers is None:
            # await self.bot.say("Application ID not found.")
            raise ApplicationIdNotFound()
            return

        em = discord.Embed(
            title="RCS Application Response",
            description=answers[0])

        for id, question in enumerate(questions):
            if id > 0:
                name = '{}. {}'.format(id, question)
                value = answers[id]
                em.add_field(name=name, value=value, inline=False)

        em.set_footer(text=server.name, icon_url=server.icon_url)

        return em

    def get_gspread_result(self, server):
        """Return Google Spreadsheet reuslt."""
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_KEY_JSON, scopes=SCOPES)
        http = credentials.authorize(httplib2.Http())
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=discoveryUrl)
        spreadsheetId = self.settings[server.id]["SHEET_ID"]

        # whole sheet
        rangeName = 'FormResponses!A:O'
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheetId, range=rangeName).execute()

        return result

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
    n = RCSApplication(bot)
    bot.add_cog(n)

