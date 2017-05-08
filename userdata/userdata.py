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
import string
import asyncio
from random import choice

import discord
from discord import Message
from discord import Server
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "userdata")
JSON = os.path.join(PATH, "settings.json")

class UserDataError(Exception):
    pass

class InvalidServerField(UserDataError):
    pass

class InvalidUserField(UserDataError):
    pass

class UserData:
    """User self-store data."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def init_server(self, ctx):
        """Init server settings."""
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = {}
        if "fields" not in self.settings[server.id]:
            self.settings[server.id]["fields"] = []
        dataIO.save_json(JSON, self.settings)

    def init_user(self, ctx):
        """Init server users settings."""
        server = ctx.message.server
        author = ctx.message.author
        if "users" not in self.settings[server.id]:
            self.settings[server.id]["users"] = {}
        if author.id not in self.settings[server.id]["users"]:
            self.settings[server.id]["users"][author.id] = {}
        dataIO.save_json(JSON, self.settings)

    @checks.mod_or_permissions()
    @commands.group(aliases=["sud"], pass_context=True, no_pm=True)
    async def setuserdata(self, ctx):
        """Set user data settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setuserdata.command(name="addfield", pass_context=True, no_pm=True)
    async def setuserdata_addfield(self, ctx, field):
        """Add a data field."""
        self.init_server(ctx)
        server = ctx.message.server
        if field not in self.settings[server.id]["fields"]:
            self.settings[server.id]["fields"].append(field)
        await self.bot.say(
            "List of fields udpated: {}".format(
                ", ".join(self.settings[server.id]["fields"])))
        dataIO.save_json(JSON, self.settings)

    @setuserdata.command(name="removefield", pass_context=True, no_pm=True)
    async def setuserdata_removefield(self, ctx, field):
        """Remove a data field."""
        self.init_server(ctx)
        server = ctx.message.server
        if field in self.settings[server.id]["fields"]:
            self.settings[server.id]["fields"].remove(field)
        await self.bot.say(
            "List of fields udpated: {}".format(
                ", ".join(self.settings[server.id]["fields"])))
        dataIO.save_json(JSON, self.settings)

    @setuserdata.command(name="sortfields", pass_context=True, no_pm=True)
    async def setuserdata_sortfields(self, ctx):
        """Sort the list of fields alphabetically."""
        self.init_server(ctx)
        server = ctx.message.server
        self.settings[server.id]["fields"] = sorted(
            self.settings[server.id]["fields"])
        await self.bot.say(
            "List of fields udpated: {}".format(
                ", ".join(self.settings[server.id]["fields"])))
        dataIO.save_json(JSON, self.settings)

    @commands.group(aliases=["ud"], pass_context=True, no_pm=True)
    async def userdata(self, ctx):
        """User Data."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @userdata.command(name="fields", pass_context=True, no_pm=True)
    async def userdata_fields(self, ctx):
        """List available fields."""
        self.init_server(ctx)
        server = ctx.message.server
        await self.bot.say(
            "List of user fields: {}".format(
                ", ".join(self.settings[server.id]["fields"])))

    @userdata.command(name="add", pass_context=True, no_pm=True)
    async def userdata_add(self, ctx, field, value):
        """Add data.

        !userdata add Facebook http://profileurl
        """
        self.init_server(ctx)
        self.init_user(ctx)
        server = ctx.message.server
        author = ctx.message.author
        try:
            field = self.get_field(ctx, field)
        except InvalidServerField:
            await self.bot.say(
                "{} is not a valid field.\n"
                "List of available fields: {}".format(
                    field, ", ".join(self.settings[server.id]["fields"])))
            return
        self.settings[server.id]["users"][author.id][field] = value
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "{}: {}: {}".format(
                author.display_name, field, value))

    @userdata.command(name="edit", pass_context=True, no_pm=True)
    async def userdata_edit(self, ctx, field, value):
        """Edit data."""
        await ctx.invoke(self.userdata_add, field, value)

    @userdata.command(name="remove", pass_context=True, no_pm=True)
    async def userdata_remove(self, ctx, field):
        """Remove data from specific field.

        !userdata remove Facebook
        """
        self.init_server(ctx)
        self.init_user(ctx)
        server = ctx.message.server
        author = ctx.message.author
        try:
            field = self.get_field(ctx, field)
        except InvalidServerField:
            await self.bot.say(
                "{} is not a valid field.\n"
                "List of available fields: {}".format(
                    field, ", ".join(self.settings[server.id]["fields"])))
            return
        try:
            user_field = self.get_user_field(server, author, field)
        except InvalidUserField:
            await self.bot.say(
                "{} does not have {} set.".format(
                    author.display_name, field))
            return
        del self.settings[server.id]["users"][author.id][field]
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Removed {} from {}".format(
                field, author.display_name))

    @userdata.command(name="info", pass_context=True, no_pm=True)
    async def userdata_info(self, ctx, member: discord.Member=None):
        """Display user data."""
        self.init_server(ctx)
        self.init_user(ctx)
        server = ctx.message.server
        if member is None:
            member = ctx.message.author
        if member.id not in self.settings[server.id]["users"]:
            await self.bot.say("User does not have any user data set.")
            return
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        em = discord.Embed(
            color=discord.Color(value=color))
        em.set_author(name=member.display_name)
        for k, v in self.settings[server.id]["users"][member.id].items():
            em.add_field(name=k, value=v)
        await self.bot.say(embed=em)

    def get_field(self, ctx, field):
        """Return field regardless of casing."""
        self.init_server(ctx)
        server = ctx.message.server
        fields = [f.lower() for f in self.settings[server.id]["fields"]]
        if field.lower() not in fields:
            raise InvalidServerField()
        field = [
            f for f in self.settings[server.id]["fields"]
            if field.lower() == f.lower()][0]
        return field

    def get_user_field(self, server, user, field):
        """Return field data of a user."""
        if field not in self.settings[server.id]["users"][user.id]:
            raise InvalidUserField()
        return self.settings[server.id]["users"][user.id][field]


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check settings."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Add cog."""
    check_folder()
    check_file()
    bot.add_cog(UserData(bot))