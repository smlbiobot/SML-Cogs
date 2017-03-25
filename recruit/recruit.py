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
import discord
from discord.ext import commands
from discord.ext.commands import Context
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help

PATH = os.path.join("data", "recruit")
JSON = os.path.join(PATH, "settings.json")

class Recruit:
    """
    Recruitment messages creation for RCS server.
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    def init_server_settings(self, server_id):
        """Init server settings if it does not exist."""
        if server_id not in self.settings:
            self.settings[server_id] = {
                "roles": [],
                "messages": {}
            }
        dataIO.save_json(JSON, self.settings)

    @commands.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def setrecruit(self, ctx: Context):
        """Set roles allowed to change recruit messages."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setrecruit.command(name="addrole", pass_context=True, no_pm=True)
    async def setrecruit_addrole(self, ctx: Context, role: str):
        """Add role(s) that permit editing recruitment messages."""
        server = ctx.message.server
        server_role = discord.utils.get(server.roles, name=role)
        if server_role is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(role))
            return
        await self.settings_addrole(server, role)

    async def settings_addrole(self, server: discord.Server, role: str):
        """Add role to settings."""
        self.init_server_settings(server.id)
        roles_settings = self.settings[server.id]["roles"]
        if role not in roles_settings:
            roles_settings.append(role)
        await self.bot.say(
            "Added {} to list of roles allowed "
            "to set recruitment messages.".format(role))
        dataIO.save_json(JSON, self.settings)

    @setrecruit.command(name="delrole", pass_context=True, no_pm=True)
    async def setrecruit_delrole(self, ctx: Context, role: str):
        """Delete role(s) that permit editing recruitment messages."""
        server = ctx.message.server
        if server.id not in self.settings:
            return
        roles_settings = self.settings[server.id]["roles"]
        server_role = discord.utils.get(server.roles, name=role)
        if server_role is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(role))
            return
        if role not in roles_settings:
            await self.bot.say(
                "{} was never permitted to recruit.".format(role))
            return
        roles_settings.remove(role)
        await self.bot.say(
            "Removed permission for {} to recruit.".format(role))

    @setrecruit.command(name="listrole", pass_context=True, no_pm=True)
    async def setrecruit_listrole(self, ctx: Context):
        """List all role(s) permitted to edit recruitment messages."""
        server = ctx.message.server
        if server.id not in self.settings:
            await self.bot.say("No settings for this server found.")
            return
        roles = self.settings[server.id]["roles"]
        if not len(roles):
            await self.bot.say("You have not added any roles for recruitment.")
            return
        await self.bot.say(
            "List of roles permitted to "
            "edit recruitment messages: {}".format(
                ", ".join(roles)))

    @commands.group(pass_context=True, no_pm=True)
    async def recruit(self, ctx: Context):
        """Recruitment messages management."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @recruit.command(name="set", pass_context=True, no_pm=True)
    async def recruit_set(self, ctx: Context, clan: str, *, msg: str):
        """Set recruiting message."""
        if clan is None:
            await send_cmd_help(ctx)
        if msg is None:
            await send_cmd_help(ctx)
        server = ctx.message.server
        author = ctx.message.author
        author_roles = [r.name for r in author.roles]
        if clan not in author_roles:
            await self.bot.say(
                "{} is not in {}.".format(
                    author.display_name, clan))
            return
        self.init_server_settings(server.id)
        server_permit_roles = self.settings[server.id]["roles"]
        allowed = False
        for r in server_permit_roles:
            if discord.utils.get(author.roles, name=r) is not None:
                allowed = True
        if not allowed:
            await self.bot.say(
                "{} is not permitted to set recruitment messages".format(
                    author.display_name))
            return
        self.settings[server.id]["messages"][clan] = str(msg)
        await self.bot.say(
            "Added recruitment messages for {}".format(clan))
        dataIO.save_json(JSON, self.settings)

    @recruit.command(name="get", pass_context=True, no_pm=True)
    async def recruit_get(self, ctx: Context, clan: str):
        if clan is None:
            await send_cmd_help(ctx)
        server = ctx.message.server
        self.init_server_settings(server.id)
        if clan not in self.settings[server.id]["messages"]:
            await self.bot.say(
                "{} has no recruitment messages set.".format(clan))
            return
        await self.bot.say(self.settings[server.id]["messages"][clan])


def check_folder():
    if not os.path.exists(PATH):
        os.mkdir(PATH)

def check_files():
    if not dataIO.is_valid_json(JSON):
        defaults = {}
        dataIO.save_json(JSON, defaults)

def setup(bot):
    check_folder()
    check_files()
    n = Recruit(bot)
    bot.add_cog(n)