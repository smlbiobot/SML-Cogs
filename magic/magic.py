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

import asyncio
import os

import discord
import hsluv
from __main__ import send_cmd_help
from discord.ext import commands
from discord.ext.commands import Context

from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from collections import defaultdict

PATH = os.path.join("data", "magic")
JSON = os.path.join(PATH, "settings.json")

SERVER_DEFAULTS = {
    "role": {
        "id": None,
        "name": "Magic"
    },
    "member_ids": []
}

def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class Magic:
    """Magic username."""

    def __init__(self, bot):
        """Init bot."""
        self.bot = bot
        self.magic_is_running = False
        self.hue = 0
        self.task = None
        self.magic_role = None
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))
        self.interval = 0.5

    def __unload(self):
        """Remove task when unloaded."""
        self.task.cancel()

    async def change_magic_color(self, server):
        """Change magic role color."""
        if not self.magic_is_running:
            return

        server_settings = self.settings[server.id].copy()
        role_name = server_settings["role"]["name"]
        magic_role = discord.utils.get(server.roles, name=role_name)

        self.hue = self.hue + 10
        self.hue = self.hue % 360
        hex_ = hsluv.hsluv_to_hex((self.hue, 100, 60))
        # Remove # sign from hex
        hex_ = hex_[1:]
        new_color = discord.Color(value=int(hex_, 16))

        await self.bot.edit_role(
            server,
            magic_role,
            color=new_color)

        await self.verify_members(server, magic_role)

        await asyncio.sleep(self.interval)
        if self.magic_is_running:
            if self is self.bot.get_cog("Magic"):
                self.task = self.bot.loop.create_task(
                    self.change_magic_color(server))

    @commands.group(pass_context=True)
    @checks.mod_or_permissions()
    async def magic(self, ctx: Context):
        """Magic role with ever changing username color."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @magic.command(name="init", pass_context=True)
    async def magic_init(self, ctx):
        """Init server settings."""
        server = ctx.message.server
        self.settings[server.id] = SERVER_DEFAULTS
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Initialized server with magic settings.")

    @magic.command(name="start", pass_context=True)
    async def magic_start(self, ctx: Context):
        """Start the magic role."""
        self.magic_is_running = True
        await self.bot.say("Magic started.")
        self.task = self.bot.loop.create_task(
            self.change_magic_color(ctx.message.server))

    @magic.command(name="stop", pass_context=True)
    async def magic_stop(self, ctx):
        """Stop magic role color change."""
        self.magic_is_running = False
        await self.bot.say("Magic stopped.")

    @magic.command(name="adduser", pass_context=True)
    async def magic_adduser(self, ctx, member: discord.Member):
        """Permit user to have the magic role."""
        if member is None:
            await send_cmd_help(ctx)
            return
        server = ctx.message.server
        member_ids = self.settings[server.id]["member_ids"]
        if member.id not in member_ids:
            member_ids.append(member.id)
            dataIO.save_json(JSON, self.settings)
        success = await self.edit_user_roles(server, member, add=True)
        if not success:
            await self.bot.say(
                "I don’t have permission to edit that user’s roles.")
        await self.list_magic_users(ctx)

    @magic.command(name="removeuser", pass_context=True)
    async def magic_removeuser(self, ctx, member: discord.Member):
        """Permit user to have the magic role."""
        if member is None:
            await send_cmd_help(ctx)
            return
        server = ctx.message.server
        member_ids = self.settings[server.id]["member_ids"]
        if member.id in member_ids:
            member_ids.remove(member.id)
            dataIO.save_json(JSON, self.settings)
        success = await self.edit_user_roles(server, member, remove=True)
        if not success:
            await self.bot.say(
                "I don’t have permission to edit that user’s roles.")
        await self.list_magic_users(ctx)

    @magic.command(name="userlist", pass_context=True)
    async def magic_userlist(self, ctx):
        """List users permitted to have Magic."""
        await self.list_magic_users(ctx)

    async def edit_user_roles(self, server, member: discord.Member, add=False, remove=False):
        """Add or remove Magic role from user."""
        if "role" not in self.settings[server.id]:
            self.settings[server.id]["role"] = {}
        role_name = self.settings[server.id]["role"]["name"]
        magic_role = discord.utils.get(server.roles, name=role_name)
        try:
            if add:
                await self.bot.add_roles(member, magic_role)
                return True
            if remove:
                await self.bot.remove_roles(member, magic_role)
                return True
        except discord.errors.Forbidden:
            return False

    async def list_magic_users(self, ctx):
        """List users permitted to have Magic."""
        server = ctx.message.server
        member_ids = self.settings[server.id]["member_ids"].copy()
        names = [server.get_member(mid).display_name for mid in member_ids]
        await self.bot.say("List of users permitted for Magic:")
        if len(names):
            await self.bot.say(', '.join(names))
        else:
            await self.bot.say('None')

    async def verify_members(self, server, magic_role):
        """Check members on server with the magic_role are in the permitted list."""
        magic_members = [m for m in server.members if magic_role in m.roles]
        for member in magic_members:
            await self.verify_member_magic(member, magic_role)

    async def verify_member_magic(self, member: discord.Member, magic_role):
        """Check member is in acceptable list."""
        server = member.server
        if server.id not in self.settings:
            return
        if member.id in self.settings[server.id]["member_ids"]:
            return

        if magic_role in member.roles:
            try:
                await self.bot.remove_roles(member, magic_role)
            except discord.errors.Forbidden:
                pass


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
    n = Magic(bot)
    bot.add_cog(n)
