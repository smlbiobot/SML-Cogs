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

import os
import httplib2
import datetime as dt
import aiohttp

import discord
from discord.ext import commands
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help

from apiclient import discovery
# from oauth2client import client
# from oauth2client import tools
# from oauth2client.file import Storage
from oauth2client.service_account import ServiceAccountCredentials

from apiclient.discovery import build


PATH = os.path.join("data", "calendar")
JSON = os.path.join(PATH, "settings.json")

CREDENTIAL_FILENAME = "calendar-credentials.json"
CREDENTIAL_JSON = os.path.join(PATH, CREDENTIAL_FILENAME)

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
SERVICE_KEY_JSON = os.path.join(PATH, "service_key.json")
APPLICATION_NAME = 'Red Discord Bot Google Calendar API Cog'

RACF_CALENDAR_ID = 'imdea4ui8l6vrpsulmboplsms8@group.calendar.google.com'

class Practice:
    """RACF Practice."""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.serverowner_or_permissions()
    @commands.group(pass_context=True)
    async def setcalendar(self, ctx):
        """Set calendar settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setcalendar.command(name="servicekey", pass_context=True)
    async def setcalendar_gapisecret(self, ctx):
        """Set Google API service account Key.

        This is a json file downloadable from the Google API Console.
        """
        await self.bot.say(
            "Please upload the Google API service account key (json).")
        answer = await self.bot.wait_for_message(
            timeout=30.0,
            author=ctx.message.author)
        if answer is None:
            await self.bot.say("Time out.")
            return
        if not len(answer.attachments):
            await self.bot.say("Cannot find attachments.")
            return
        attach = answer.attachments[0]
        url = attach["url"]

        async with aiohttp.get(url) as cred:
            with open(SERVICE_KEY_JSON, "wb") as f:
                f.write(await cred.read())

        await self.bot.say(
            "Attachment received: {}".format(SERVICE_KEY_JSON))

    @commands.group(pass_context=True)
    async def calendar(self, ctx):
        """Google Calendar."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @calendar.command(name="list", pass_context=True)
    async def calendar_list(self, ctx, max_results=5):
        """List events on a calendar."""
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            SERVICE_KEY_JSON, scopes=SCOPES)
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)

        now = dt.datetime.utcnow().isoformat() + 'Z'

        await self.bot.say(
            "Getting the upcoming {} events:".format(max_results))

        eventsResult = service.events().list(
            calendarId=RACF_CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])
        if not events:
            await self.bot.say("No upcoming events found.")

        out = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            out.append(start)
            out.append(event['summary'])

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
    n = Practice(bot)
    bot.add_cog(n)