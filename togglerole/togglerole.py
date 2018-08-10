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

from collections import defaultdict

import asyncio
import datetime as dt
import discord
import os
from discord.ext import commands

from cogs.utils import checks
from cogs.utils.dataIO import dataIO

DATA_PATH = os.path.join("data", "SML-Cogs", "togglerole")
SETTINGS_JSON = os.path.join(DATA_PATH, "settings.json")

TASK_DELAY = dt.timedelta(minutes=30).total_seconds()

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
            await self.bot.send_cmd_help(ctx)

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
        em = discord.Embed(
            title="Toggleable Roles"
        )
        for actor_role, v in self.settings[server.id].items():
            toggleable_roles = v.keys()
            toggleable_roles = sorted(toggleable_roles, key=lambda x: x.lower())
            if len(toggleable_roles):
                toggleable_roles_str = ', '.join(toggleable_roles)
                em.add_field(name=actor_role, value=toggleable_roles_str)
            else:
                toggleable_roles_str = 'None'

            # out.append('{}: {}'.format(bold(actor_role), toggleable_roles_str))

        await self.bot.say(embed=em)

    def check_server_settings(self, server: discord.Server):
        """Check server setttings"""
        if server.id not in self.settings:
            self.settings[server.id] = dict()
        if "AUTO" not in self.settings[server.id]:
            self.settings[server.id]["AUTO"] = dict()
        dataIO.save_json(SETTINGS_JSON, self.settings)

    def toggleable_roles(self, server, user):
        """Return a list of roles toggleable by user."""
        o = []
        user_role_names = [r.name for r in user.roles]
        for actor_role, toggle_roles in self.settings[server.id].items():
            # ignore special AUTO key
            if actor_role == 'AUTO':
                continue
            if actor_role == '_everyone':
                o.extend(toggle_roles.keys())
            if actor_role in user_role_names:
                o.extend(toggle_roles.keys())
        o = list(set(o))
        o = sorted(o, key=lambda x: x.lower())
        return o

    def toggleable_role_list(self, server, member: discord.Member):
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
        """Toggle a role.
        !togglerole list   - show toggleable roles"""
        author = ctx.message.author
        server = ctx.message.server
        if role is None:
            await self.bot.say(self.toggleable_role_list(server, author))
            return

        # list roles
        if role == 'list':
            await ctx.invoke(self.toggleroleset_list)
            return

        role_obj = None
        toggleable_roles = self.toggleable_roles(server, author)
        if role.lower() not in [r.lower() for r in toggleable_roles]:
            await self.bot.say("{} is not a toggleable role for you.".format(role))
            await self.bot.say(self.toggleable_role_list(server, author))
            return
        for r in server.roles:
            if r.name.lower() == role.lower():
                role_obj = r

        if role_obj is None:
            await self.bot.say("{} not found on this server.".format(role))
            return

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

    @checks.mod_or_permissions(manage_roles=True)
    @commands.command(pass_context=True, no_pm=True, aliases=["trr"])
    async def togglerolereact(self, ctx, on_off=True):
        """Create embeds for user to self-toggle via reactions."""
        server = ctx.message.server
        channel = ctx.message.channel

        self.check_server_settings(server)
        self.settings[server.id]["AUTO"] = dict(
            channel_id=channel.id,
            on_off=on_off
        )
        if on_off:
            await self.post_togglerole_embeds(server, channel)

    def role_embed(self, server, t_role, actor_roles):
        desc = ", ".join(actor_roles)
        if len(desc) == 0:
            return None

        em = discord.Embed(
            title=t_role,
            description=desc
        )

        # list members
        """
        r_role_o = discord.utils.get(server.roles, name=t_role)
        m_with_role = []
        for member in server.members:
            if r_role_o in member.roles:
                m_with_role.append(member)

        name = "Members"
        value = ", ".join([m.name for m in m_with_role])
        if len(value) > 1000:
            value = value[:1000] + "…"
        if len(m_with_role) == 0:
            value = 'None'
        em.add_field(name=name, value=value)
        """
        return em

    async def post_togglerole_embeds(self, server, channel):
        """Post embeds for user to self-toggle via reactions."""
        self.check_server_settings(server)

        # create list of toggleable roles
        toggleables = dict()

        for actor_role, toggle_roles in self.settings[server.id].items():
            # ignore special AUTO key
            if actor_role == 'AUTO':
                continue

            for t_role in toggle_roles:
                if t_role not in toggleables.keys():
                    toggleables[t_role] = []
                toggleables[t_role].append(actor_role)

        # delete channel messages
        if channel is not None:
            await self.bot.purge_from(channel, limit=100)

        message = None
        for t_role, actor_roles in toggleables.items():
            em = self.role_embed(server, t_role, actor_roles)
            if em is None:
                continue

            msg = await self.bot.send_message(channel, embed=em)

            await self.bot.add_reaction(msg, "✅")
            await self.bot.add_reaction(msg, "❌")

            # save first message
            if message is None:
                message = msg



    async def post_togglerole_task(self):
        """Auto post tasks."""
        while self == self.bot.get_cog("ToggleRole"):
            try:
                for server_id, settings in self.settings.items():
                    server = self.bot.get_server(server_id)
                    if server is None:
                        continue
                    self.check_server_settings(server)
                    if self.settings[server.id].get("AUTO", {}).get("on_off", False):
                        channel_id = self.settings.get(server.id, {}).get("AUTO", {}).get("channel_id")
                        if channel_id is None:
                            continue
                        channel = server.get_channel(channel_id)
                        if channel is None:
                            continue
                        await self.post_togglerole_embeds(server, channel)
            except Exception:
                pass
            finally:
                await asyncio.sleep(TASK_DELAY)

    async def on_reaction_add(self, reaction: discord.Reaction, user):
        await self.on_reaction(reaction, user)

    # async def on_reaction_remove(self, reaction: discord.Reaction, user):
    #     await self.on_reaction(reaction, user, remove=True)

    async def on_reaction(self, reaction: discord.Reaction, user):
        message = reaction.message
        channel = message.channel
        server = message.server
        if user == self.bot.user:
            return

        # create list of tasks
        tasks = []

        # tasks after
        update_tasks = []

        for server_id in self.settings.keys():
            auto = self.settings.get(server_id, {}).get("AUTO", {})
            # auto must be on
            if not auto.get('on_off'):
                continue
            # channel id must match
            if auto.get("channel_id") != channel.id:
                continue
                # must not be bot
            if user == self.bot.user:
                continue

            add = False
            remove = False

            if reaction.emoji == '✅':
                add = True
            elif reaction.emoji == '❌':
                remove = True
            else:
                await self.bot.remove_reaction(message, reaction.emoji, user)

            # must be on embed
            if len(message.embeds) == 0:
                continue
            em = message.embeds[0]
            role_name = em.get('title')
            allowed_roles = em.get('description', []).split(", ")

            # must be valid
            if role_name is None:
                continue
            if len(allowed_roles) == 0:
                continue

            # check user has allowed_roles
            valid = False
            for u_role in user.roles:
                if u_role.name in allowed_roles:
                    valid = True
                    break
            if not valid:
                continue

            # check if user has role
            user_has_role = False
            for u_role in user.roles:
                if u_role.name == role_name:
                    user_has_role = True

            update_messages = False

            if add:
                if user_has_role:
                    txt = "User already has the role."
                    tasks.append(self.delay_message(channel, txt))
                else:
                    tasks.append(self.add_role(server, user, role_name, channel=channel))
                    update_messages = True
            elif remove:
                if not user_has_role:
                    txt = "User does not have the role."
                    tasks.append(self.delay_message(channel, txt))
                else:
                    tasks.append(self.remove_role(server, user, role_name, channel=channel))
                    update_messages = True

            # remove reaction
            tasks.append(self.bot.remove_reaction(message, reaction.emoji, user))

            # update messages
            # no need to update messages anymore since members are not displayed
            # if update_messages:
            #     update_tasks.append(self.post_togglerole_embeds(server, channel))

        if len(tasks):
            await asyncio.gather(*tasks)

        if len(update_tasks):
            await asyncio.gather(*update_tasks)

    async def delay_message(self, channel, txt, wait=5):
        msg = await self.bot.send_message(channel, txt)
        await asyncio.sleep(wait)
        await self.bot.delete_message(msg)

    async def add_role(self, server, user, role_name, channel=None):
        role = discord.utils.get(server.roles, name=role_name)
        await self.bot.add_roles(user, role)
        if channel is not None:
            txt = "Added {} to {}".format(role, user)
            await self.delay_message(channel, txt)

    async def remove_role(self, server, user, role_name, channel=None):
        role = discord.utils.get(server.roles, name=role_name)
        await self.bot.remove_roles(user, role)
        if channel is not None:
            txt = "Removed {} from {}".format(role, user)
            await self.delay_message(channel, txt)


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
    bot.loop.create_task(n.post_togglerole_task())
