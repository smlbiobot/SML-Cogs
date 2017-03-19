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
import asyncio
from datetime import datetime as dt
from datetime import timedelta
from discord.ext import commands
from discord.ext.commands import Context
from discord import Member
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from __main__ import send_cmd_help

PATH_LIST = ['data', 'clanbattle']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
CB_ROLES = ["clanbattle"]
ROLE_PREFIX = "cb_"
VC_PREFIX = "CB: "
DT_FORMAT = "%Y-%m-%d %H:%M:%S"
INTERVAL = 5

class ClanBattle:
    """Clan battle modules for Clash Royale 2v2 mode."""

    def __init__(self, bot):
        """Clan battle module for Clash Royale 2v2 mode."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.task = self.bot.loop.create_task(self.loop_task())

    async def loop_task(self):
        """Check for empty VCs. and remove"""
        await self.bot.wait_until_ready()
        await self.remove_empty_vc()
        await asyncio.sleep(INTERVAL)
        if self is self.bot.get_cog("ClanBattle"):
            self.task = self.bot.loop.create_task(self.loop_task())

    async def remove_empty_vc(self):
        """Remove all empty voice channels created by members."""
        print("remove_empty_vc")
        for server_id in self.settings:
            for member_id in self.settings[server_id]:
                m_settings = self.settings[server_id][member_id]
                vc_id = m_settings["channel_id"]
                vc = self.bot.get_channel(vc_id)
                vc_members = vc.voice_members
                print("vc_members: {}".format(str(vc_members)))
                if not len(vc_members):
                    # print("VC is empty")
                    time = dt.strptime(m_settings["time"], DT_FORMAT)
                    now = dt.utcnow()
                    td = timedelta(seconds=15)
                    print("-" * 30)
                    print("time: {}".format(str(time)))
                    print("now: {}".format(str(now)))
                    print("now - time: {}".format(str(now-time)))
                    if now - time > td:
                        print("over 1 minute")
                        server = self.bot.get_server(server_id)
                        member = self.bot.get_member(member_id)
                        await self.bot.clanbattle_end_member(member, server)

    async def on_voice_state_update(self, before: Member, after: Member):
        """Update CB VC last accesss time"""
        for server_id in self.settings:
            if before.id in self.settings[server_id]:
                m_settings = self.settings[server_id][before.id]
                if before.voice.voice_channel != after.voice.voice_channel:
                    m_settings["time"] = dt.utcnow().strftime(DT_FORMAT)
                    dataIO.save_json(JSON, self.settings)

    @commands.group(aliases=['cb'], pass_context=True, no_pm=True)
    @commands.has_any_role(*CB_ROLES)
    async def clanbattle(self, ctx: Context):
        """Clan Battles."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @clanbattle.command(name="create", pass_context=True, no_pm=True)
    async def clanbattle_create(self, ctx: Context, member: Member=None):
        """Create clan battle voice channels.

        Example:
        !clanbattle
        !clanbattle create SML
        !clanbattle create @SML @vin
        """
        server = ctx.message.server
        author = ctx.message.author
        if member is None:
            member = author

        if server.id not in self.settings:
            self.settings[server.id] = {}
        if member.id in self.settings[server.id]:
            await self.bot.say("You already have an active clan battle VC.")
            return

        vc_name = "{}{}".format(VC_PREFIX, member.display_name)

        cannot_connect = discord.PermissionOverwrite(connect=False)
        can_connect = discord.PermissionOverwrite(connect=True)

        cb_role = await self.bot.create_role(
            server,
            name="{}{}".format(ROLE_PREFIX, member.display_name))

        await self.bot.add_roles(member, cb_role)

        channel = await self.bot.create_channel(
            server,
            vc_name,
            (server.default_role, cannot_connect),
            (server.me, can_connect),
            (cb_role, can_connect),
            type=discord.ChannelType.voice)

        self.settings[server.id][member.id] = {
            "channel_id": channel.id,
            "members": [member.id],
            "role_id": cb_role.id,
            "time": dt.utcnow().strftime(DT_FORMAT)
        }
        dataIO.save_json(JSON, self.settings)

        await self.bot.say("Clan Battle VC for {} created.".format(author.display_name))

    @clanbattle.command(name="add", pass_context=True, no_pm=True)
    async def clanbattle_add(self, ctx: Context, *members: Member):
        """Add member(s) to the clan battle VC."""
        if not len(members):
            await send_cmd_help(ctx)
            return
        server = ctx.message.server
        author = ctx.message.author

        if server.id not in self.settings:
            await self.bot.say("You do not have an active clan battle VC.")
            return
        if author.id not in self.settings[server.id]:
            await self.bot.say("You do not have an active clan battle VC.")
            return
        author_settings = self.settings[server.id][author.id]
        role_id = author_settings["role_id"]
        roles = [r for r in server.roles if r.id == role_id]
        for member in members:
            await self.bot.add_roles(member, *roles)
            if member.id not in author_settings["members"]:
                author_settings["members"].append(member.id)

        dataIO.save_json(JSON, self.settings)

        await self.bot.say(
            "{} can now join clan battle VC for {}".format(
                ', '.join([m.display_name for m in members]),
                author.display_name))

    @clanbattle.command(name="remove", pass_context=True, no_pm=True)
    async def clanbattle_remove(self, ctx: Context, *members: Member):
        """Remove member(s) to the clan battle VC."""
        if not len(members):
            await send_cmd_help(ctx)
            return
        server = ctx.message.server
        author = ctx.message.author
        if server.id not in self.settings:
            await self.bot.say("You do not have an active clan battle VC.")
            return
        if author.id not in self.settings[server.id]:
            await self.bot.say("You do not have an active clan battle VC.")
            return
        author_settings = self.settings[server.id][author.id]
        role_id = author_settings["role_id"]
        roles = [r for r in server.roles if r.id == role_id]
        for member in members:
            await self.bot.remove_roles(member, *roles)
            author_settings["members"].remove(member.id)

        dataIO.save_json(JSON, self.settings)

        await self.bot.say(
            "{} can no longer join the clan battle VC for {}".format(
                ', '.join([m.display_name for m in members]),
                author.display_name))




    @clanbattle.command(name="end", pass_context=True, no_pm=True)
    async def clanbattle_end(self, ctx: Context):
        """Remove clan battle voice channels."""
        server = ctx.message.server
        author = ctx.message.author
        await self.clanbattle_end_member(author, server)

        # if server.id not in self.settings:
        #     return
        # if author.id not in self.settings[server.id]:
        #     return

    async def clanbattle_end_member(self, member: Member=None, server=None):
        """Remove clan battle voice channels and roles for specific member."""
        print("clanbattle_end_member")
        if server is None:
            return
        if member is None:
            return
        if server.id not in self.settings:
            return
        if member.id not in self.settings[server.id]:
            return
        print("clanbattle_end_member proceed")

        m_settings = self.settings[server.id][member.id]
        channel_id = m_settings["channel_id"]
        channel = self.bot.get_channel(channel_id)
        if channel:
            await self.bot.delete_channel(channel)
        if "role_id" in m_settings:
            role_id = m_settings["role_id"]
            roles = [r for r in server.roles if r.id == role_id]
            if len(roles):
                for r in roles:
                    await self.bot.delete_role(server, r)
        del self.settings[server.id][member.id]
        dataIO.save_json(JSON, self.settings)

        await self.bot.say("Clan Battle VC for {} removed.".format(member.display_name))



    @clanbattle.command(name="init", pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    async def clanbattle_init(self, ctx: Context):
        """Initialize clan battle roles and voice channels.

        Remove VCs starting with CB: prefix.
        Remove roles starting with cb_ prefix.
        """
        server = ctx.message.server
        roles = [r for r in server.roles if r.name.startswith(ROLE_PREFIX)]
        if len(roles):
            for r in roles:
                await self.bot.delete_role(server, r)
            await self.bot.say("Removed all clan battle related roles.")
        channels = [c for c in server.channels if c.name.startswith(VC_PREFIX)]
        if len(channels):
            for c in channels:
                await self.bot.delete_channel(c)
            await self.bot.say("Removed all clan battle related channels.")

        del self.settings[server.id]
        dataIO.save_json(JSON, self.settings)




def check_folder():
    """check data folder exists and create if needed."""
    if not os.path.exists(PATH):
        print("Creating {} folder".format(PATH))
        os.makedirs(PATH)


def check_file():
    """Check data folder exists and create if needed."""
    defaults = {}
    if not dataIO.is_valid_json(JSON):
        print("Creating default clanbattle settings.json")
        dataIO.save_json(JSON, defaults)


def setup(bot):
    """Add cog to bot."""
    check_folder()
    check_file()
    n = ClanBattle(bot)
    bot.add_cog(n)