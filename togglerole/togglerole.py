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
from collections import defaultdict

import discord
from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify, bold
from cogs.utils.dataIO import dataIO
from discord.ext import commands

DATA_PATH = os.path.join("data", "SML-Cogs", "togglerole")
SETTINGS_JSON = os.path.join(DATA_PATH, "settings.json")

server_defaults = {
    "_everyone": []
}


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class ToggleRole:
    """Toggle roles by end users.
    
    List of toggleable roles are determined by user’s own roles.
    """

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(SETTINGS_JSON))

    @commands.group(pass_context=True, no_pm=True)
    async def toggleroleset(self, ctx):
        """Settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @toggleroleset.command(name="add", pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def toggleroleset_add(self, ctx, actor_role, toggleable_role):
        """Add a toggleable role.
        
        If you want to wish to allow anyone to toggle that role, use _everyone for actor_role
        
        [p]toggleroleset add Member Coc
        allows users with the Member role to add the CoC toggleable role.
        
        [p]toggleroleset add _everyone Visitor
        allows users with or without roles to self-toggle the Visitor role.
        """
        server = ctx.message.server
        if not self.verify_role(server, actor_role):
            await self.bot.say("{} is not a valid role on this server.".format(actor_role))
            return
        if not self.verify_role(server, toggleable_role):
            await self.bot.say("{} is not a valid role on this server.".format(toggleable_role))
            return
        if actor_role not in self.settings[server.id]:
            self.settings[server.id][actor_role] = {}
        self.settings[server.id][actor_role][toggleable_role] = True
        dataIO.save_json(SETTINGS_JSON, self.settings)
        await ctx.invoke(self.toggleroleset_list)

    @toggleroleset.command(name="remove", aliases=['rm'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def toggleroleset_remove(self, ctx, actor_role, toggleable_role):
        """Remove a toggleable role.
        
        If you want to wish to allow anyone to toggle that role, use _everyone for actor_role 
        """
        server = ctx.message.server
        if not self.verify_role(server, actor_role):
            await self.bot.say("{} is not a valid role on this server.".format(actor_role))
            return
        if not self.verify_role(server, toggleable_role):
            await self.bot.say("{} is not a valid role on this server.".format(toggleable_role))
            return
        self.settings[server.id][actor_role].pop(toggleable_role, None)
        dataIO.save_json(SETTINGS_JSON, self.settings)
        await ctx.invoke(self.toggleroleset_list)

    def verify_role(self, server, role_name):
        """Verify the role exist on the server"""
        if role_name == '_everyone':
            return True
        role = discord.utils.get(server.roles, name=role_name)
        return role is not None

    @toggleroleset.command(name="list", pass_context=True, no_pm=True)
    async def toggleroleset_list(self, ctx):
        """List all toggleable roles."""
        server = ctx.message.server
        out = []
        out.append('Toggleable roles on {}'.format(server.name))
        for actor_role, v in self.settings[server.id].items():
            toggleable_roles = v.keys()
            toggleable_roles = sorted(toggleable_roles, key=lambda x: x.lower())
            if len(toggleable_roles):
                toggleable_roles_str = ', '.join(toggleable_roles)
            else:
                toggleable_roles_str = 'None'
            out.append('{}: {}'.format(bold(actor_role), toggleable_roles_str))

        for page in pagify('\n'.join(out)):
            await self.bot.say(page)

    def toggleable_roles(self, server, user):
        """Return a list of roles toggleable by user."""
        o = []
        user_role_names = [r.name for r in user.roles]
        for actor_role, toggle_roles in self.settings[server.id].items():
            if actor_role == '_everyone':
                o.extend(toggle_roles.keys())
            if actor_role in user_role_names:
                o.extend(toggle_roles.keys())
        o = list(set(o))
        o = sorted(o, key=lambda x: x.lower())
        return o

    def toggleable_role_list(self, server, member:discord.Member):
        """List of toggleable roles for member."""
        toggleable_roles = self.toggleable_roles(server, member)
        if len(toggleable_roles):
            toggleable_roles_str = ', '.join(toggleable_roles)
        else:
            toggleable_roles_str = 'None'
        return (
            "List of roles toggleable for you are: {}".format(
                toggleable_roles_str)
        )

    @commands.command(pass_context=True, no_pm=True)
    async def togglerole(self, ctx, role=None):
        """Toggle a role."""
        author = ctx.message.author
        server = ctx.message.server
        if role is None:
            await self.bot.say(self.toggleable_role_list(server, author))
            return
        toggleable_roles = self.toggleable_roles(server, author)
        if role.lower() not in [r.lower() for r in toggleable_roles]:
            await self.bot.say("{} is not a toggleable role for you.".format(role))
            await self.bot.say(self.toggleable_role_list(server, author))
            return
        for r in server.roles:
            if r.name.lower() == role.lower():
                role_obj = r
        if role_obj in author.roles:
            await self.bot.remove_roles(author, role_obj)
            await self.bot.say(
                "Removed {} role from {}.".format(
                    role_obj.name, author.display_name))
        else:
            await self.bot.add_roles(author, role_obj)
            await self.bot.say(
                "Added {} role for {}.".format(
                    role_obj.name, author.display_name))


def check_folder():
    """Check folder."""
    os.makedirs(DATA_PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(SETTINGS_JSON):
        dataIO.save_json(SETTINGS_JSON, {})


def setup(bot):
    """Setup bot."""
    check_folder()
    check_file()
    n = ToggleRole(bot)
    bot.add_cog(n)
