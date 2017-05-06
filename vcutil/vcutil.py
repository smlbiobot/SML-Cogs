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
import asyncio
import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
from __main__ import send_cmd_help

PATH = os.path.join('data', 'vcutil')
JSON = os.path.join('data', 'vcutil', 'settings.json')

LOOP_INTERVAL = 5
VC_TIMEOUT = 60

class VCUtil:
    """Voice channel utilities."""

    def __init__(self, bot):
        """Voice channel utilities."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        # self.task = self.bot.loop.create_task(self.loop_task())

    # async def loop_task(self):
    #     """Check for empty VCs and remove text chat."""
    #     await self.bot.wait_until_ready()
    #     await asyncio.sleep(LOOP_INTERVAL)

    #     if self is self.bot.get_cog("VCUtil"):
    #         self.task = self.loop.create_task(self.bot.loop_task())
    #         await self.monitor_vc_chat()

    # async def monitor_vc_chat(self):
    #     """Remove self-generated text chat if VC is empty."""
    #     for server_id in self.settings:
    #         pass

    @commands.group(pass_context=True, no_pm=True)
    async def vcutil(self, ctx):
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @vcutil.command(name="addvc", pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    async def vcutil_addvc(self, ctx, vc: discord.Channel):
        """Add a Voice Channel to monitor."""
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = {}
        if vc is None:
            await self.bot.say("{} is not a valid channel.".format(vc))
            return
        if vc.type != discord.ChannelType.voice:
            await self.bot.say("{} is not a voice channel".format(vc))
            return
        if "vc" not in self.settings[server.id]:
            self.settings[server.id]["vc"] = []
        vclist = self.settings[server.id]["vc"]
        if vc.id not in vclist:
            vclist.append(vc.id)
        await self.bot.say(
            "Added {} to list of channels to monitor.".format(vc))
        dataIO.save_json(JSON, self.settings)

    @vcutil.command(name="removevc", pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    async def vcutil_removevc(self, ctx, vc: discord.Channel):
        """Remove a Voice Channel to monitor."""
        server = ctx.message.server
        msg = "{} removed from list.".format(vc)
        if server.id in self.settings:
            if "vc" in self.settings[server.id]:
                if vc.id in self.settings[server.id]["vc"]:
                    self.settings[server.id]["vc"].remove(vc.id)
        await self.bot.say(msg)
        dataIO.save_json(JSON, self.settings)

    @vcutil.command(name="addrole", pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    async def vcutil_addrole(self, ctx, role):
        """Add a role to see VC Chat."""
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = {}
        if "roles" not in self.settings[server.id]:
            self.settings[server.id]["roles"] = []
        role = discord.utils.get(server.roles, name=role)
        if role is None:
            await self.bot.say(
                "{} is not a role on this server.".format(
                    role))
            return
        if role.id not in self.settings[server.id]["roles"]:
            self.settings[server.id]["roles"].append(role.id)
        await self.bot.say(
            "Added {} to list of roles to see VC chat.".format(
                role.name))
        dataIO.save_json(JSON, self.settings)

    @vcutil.command(name="removerole", pass_context=True, no_pm=True)
    @checks.admin_or_permissions()
    async def vcutil_removerole(self, ctx, role):
        """Remove a role from seeing VC chat."""
        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = {}
        if "roles" not in self.settings[server.id]:
            self.settings[server.id]["roles"] = []
        role = discord.utils.get(server.roles, name=role)
        if role is None:
            await self.bot.say(
                "{} is not a role on this server.".format(
                    role))
            return
        if role.id in self.settings[server.id]["roles"]:
            self.settings[server.id]["roles"].remove(role.id)
        await self.bot.say(
            "Remove {} from list of roles to see VC chat.".format(
                role.name))
        dataIO.save_json(JSON, self.settings)

    @vcutil.command(name="list", pass_context=True, no_pm=True)
    async def vcutil_listvc(self, ctx):
        """List voice channels being monitored."""
        server = ctx.message.server
        vcs = []
        roles = []
        if server.id in self.settings:
            if "vc" in self.settings[server.id]:
                for id in self.settings[server.id]["vc"]:
                    c = self.bot.get_channel(id)
                    vcs.append(c.name)
            if "roles" in self.settings[server.id]:
                for id in self.settings[server.id]["roles"]:
                    r = discord.utils.get(server.roles, id=id)
                    roles.append(r.name)
        await self.bot.say(
            "List of VC channels monitored: {}\n"
            "List of roles to add/remove: {}\n".format(
                ", ".join(vcs), ", ".join(roles)))

    async def on_voice_state_update(self, before, after):
        """Update member roles when they enter monitored VCs."""
        server = before.server
        if server.id not in self.settings:
            return
        if "vc" not in self.settings[server.id]:
            return
        if "roles" not in self.settings[server.id]:
            return
        if not len(self.settings[server.id]["roles"]):
            return
        if not len(self.settings[server.id]["vc"]):
            return
        if before.voice.voice_channel is not None:
            if before.voice.voice_channel.id in self.settings[server.id]["vc"]:
                for role_id in self.settings[server.id]["roles"]:
                    role = discord.utils.get(server.roles, id=role_id)
                    await self.bot.remove_roles(before, role)
                    # print("Removed role {} for {}".format(role.name, before.display_name))
        if after.voice.voice_channel is not None:
            if after.voice.voice_channel.id in self.settings[server.id]["vc"]:
                for role_id in self.settings[server.id]["roles"]:
                    role = discord.utils.get(server.roles, id=role_id)
                    await self.bot.add_roles(before, role)
                    # print("Added role {} for {}".format(role.name, after.display_name))


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
    n = VCUtil(bot)
    bot.add_cog(n)