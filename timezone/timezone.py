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
import re

import discord
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "timezone")
JSON = os.path.join(PATH, "settings.json")

GMAPS_FIELDS = {
    "timeZoneName": "Time Zone Name",
    "timeZoneId": "Time Zone ID"
}

TZ_ABBREV = {
    "ACDT": "Australia",
    "ACST": "Australia",
    "BST": "London",
    "CET": "France",
    "CT": "Beijing",
    "EDT": "New York",
    "EEST": "Finland",
    "EET": "Findland",
    "EST": "New York",
    "ET": "New York",
    "GMT": "London",
    "HKT": "Hong Kong",
    "JST": "Japan",
    "KST": "Korea",
    "MDT": "Idaho",
    "MYT": "Malaysia",
    "PDT": "Los Angeles",
    "PST": "Los Angeles",
    "SST": "Singapore",
    "WEST": "Spain",
    "WET": "London"
}

try:
    import pytz
    pytz_available = True
except ImportError:
    pytz_available = False

try:
    import delorean
    delorean_available = True
except ImportError:
    delorean_available = False

try:
    import googlemaps
    googlemaps_available = True
except ImportError:
    googlemaps_available = False

class TimeZone:
    """Timezone conversion and more."""

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def gmclient(self):
        """Return Google Maps client."""
        if "GOOGLE_API_KEY" in self.settings:
            key = self.settings["GOOGLE_API_KEY"]
            return googlemaps.Client(key=key)
        return None

    @commands.group(aliases=['stz'], pass_context=True)
    @checks.serverowner_or_permissions()
    async def settimezone(self, ctx):
        """Set Timezone settings."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @settimezone.command(name="googleapikey", pass_context=True)
    async def settimezone_googleapikey(self, ctx, apikey):
        """Set Google API Key."""
        self.settings["GOOGLE_API_KEY"] = apikey
        await self.bot.say("Google API Key set.")
        dataIO.save_json(JSON, self.settings)

    @commands.group(aliases=['tz'], pass_context=True)
    async def timezone(self, ctx):
        """Timezone."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @timezone.command(name="list", pass_context=True)
    async def timezone_list(self, ctx):
        """List all timezones via DM."""
        author = ctx.message.author
        out = []
        for tz in pytz.all_timezones:
            out.append('+ {}'.format(tz))
        for page in pagify('\n'.join(out)):
            await self.bot.send_message(author, content=page)
        await self.bot.say(
            "{0.mention} List of timezones sent via DM.".format(
                author))

    @timezone.command(name="country", pass_context=True)
    async def timezone_country(self, ctx, country):
        """Commonly used timezones with ISO 3166 country codes.

        Example:
        [p]timezone country nz
        """
        timezones = pytz.country_timezones(country)
        if not len(timezones):
            await self.bot.say(
                "{} does not appear to be a "
                "valid ISO 3166 country code.".format(country))
            return
        name = pytz.country_names[country]
        await self.bot.say(
            "Commonly used timezones in {}: {}.".format(
                name, ", ".join(timezones)))

    @timezone.command(name="parse", pass_context=True)
    async def timezone_parse(self, ctx, *, datetime_str):
        """Parse ambiguous time information."""
        await self.bot.say(
            delorean.parse(datetime_str))

    @timezone.command(name="location", aliases=['loc'], pass_context=True)
    async def timezone_location(self, ctx, *, address):
        """Find timezone by location."""
        gc = self.gmclient().geocode(address)
        loc = gc[0]['geometry']['location']
        result = self.gmclient().timezone(location=loc)
        if result['status'] == 'OK':
            em = discord.Embed()
            for k, v in result.items():
                if k in ['timeZoneName', 'timeZoneId']:
                    em.add_field(name=GMAPS_FIELDS[k], value=v)
            await self.bot.say(embed=em)
        else:
            await self.bot.say(result['status'])

    @timezone.command(name="time", pass_context=True)
    async def timezone_time(self, ctx, *, address):
        """Find the time by location."""
        gc = self.gmclient().geocode(address)
        loc = gc[0]['geometry']['location']
        timestamp = dt.datetime.utcnow()
        result = self.gmclient().timezone(location=loc)
        if result['status'] == 'OK':
            result_time = (
                timestamp +
                dt.timedelta(seconds=result['dstOffset']) +
                dt.timedelta(seconds=result['rawOffset'])
            )
            await self.bot.say(result_time)

        else:
            await self.bot.say(result['status'])

    @timezone.command(name="convert", pass_context=True)
    async def timezone_convert(self, ctx, time, from_loc, to_loc):
        """Convert time from location to location.

        !tz convert "2017-05-14 9:00" EST Sydney
        !tz convert "2017-05-14 9:00" "Hong Kong" London
        """
        if from_loc.upper() in TZ_ABBREV:
            from_loc = TZ_ABBREV[from_loc.upper()]
        if to_loc.upper() in TZ_ABBREV:
            to_loc = TZ_ABBREV[to_loc.upper()]

        from_tz = self.get_timezone(from_loc)
        to_tz = self.get_timezone(to_loc)

        from_time = delorean.parse(time)
        orig_time = delorean.Delorean(
            datetime=from_time.naive,
            timezone=from_tz["timeZoneId"]
        )

        converted_time = delorean.Delorean(
            datetime=from_time.naive,
            timezone=from_tz["timeZoneId"]
        )
        converted_time.shift(to_tz["timeZoneId"])

        dt_fmt = "%A, %B %d, %Y at %H:%M:%S"

        msg = (
            "{} \n"
            "for {} \n"
            "is \n"
            "{} \n"
            "for {}.").format(
                orig_time.datetime.strftime(dt_fmt),
                "{} ({})".format(from_tz["timeZoneId"], from_tz["timeZoneName"]),
                converted_time.datetime.strftime(dt_fmt),
                "{} ({})".format(to_tz["timeZoneId"], to_tz["timeZoneName"])
            )
        await self.bot.say(msg)


    @commands.group(aliases=['gm'], pass_context=True)
    async def gmaps(self, ctx):
        """Timezone."""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @gmaps.command(name="geocode", pass_context=True)
    async def gmaps_geocode(self, ctx, *, address):
        """Geocode an address."""
        results = self.gmclient().geocode(address)
        for result in results:
            em = discord.Embed()
            for k, v in result['geometry'].items():
                em.add_field(name=k, value=v)
            await self.bot.say(embed=em)

    @gmaps.command(name="timezone", pass_context=True)
    async def gmaps_timezone(self, ctx, *, address):
        """Find the timezone by address."""
        result = self.get_timezone(address)
        await self.bot.say(result)

    def get_timezone(self, address):
        """Return timezone info by location.

        Result format:
        {
            'dstOffset': 3600,
            'rawOffset': -18000,
            'status': 'OK',
            'timeZoneId': 'America/New_York',
            'timeZoneName': 'Eastern Daylight Time'
        }

        """
        gc = self.gmclient().geocode(address)
        loc = gc[0]['geometry']['location']
        result = self.gmclient().timezone(location=loc)
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
    """Add cog to bog."""
    check_folder()
    check_file()
    if not pytz_available:
        raise RuntimeError("You need to run `pip3 install pytz`")
    elif not delorean_available:
        raise RuntimeError("You need to run `pip3 install delorean`")
    elif not googlemaps_available:
        raise RuntimeError("You need to run `pip3 install googlemaps`")
    else:
        n = TimeZone(bot)
        bot.add_cog(n)

