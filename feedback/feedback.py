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
from datetime import datetime as dt

import discord
from discord.ext import commands
from discord.ext.commands import Context

from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO

PATH = os.path.join("data", "feedback")
JSON = os.path.join(PATH, "settings.json")


class Feedback:
    """Accept user feedback via DM."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @commands.group(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(manage_server=True)
    async def setfeedback(self, ctx: Context):
        """Set settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    def init_server_settings(self, server):
        """Init server settings."""
        self.settings[server.id] = {
            "channel": "",
            "read_roles": [],
            "send_roles": [],
            "feedbacks": {}
        }
        dataIO.save_json(JSON, self.settings)

    @setfeedback.command(name="channel", pass_context=True, no_pm=True)
    async def setfeedback_channel(
            self, ctx: Context, channel: discord.Channel=None):
        """Set feedback channel."""
        if channel is None:
            channel = ctx.message.channel
        server = ctx.message.server
        if server.id not in self.settings:
            self.init_server_settings(server)
        self.settings[server.id]["channel"] = channel.id
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Feedback channel set to {}".format(channel.name))

    @setfeedback.group(name="addrole", pass_context=True, no_pm=True)
    async def setfeedback_addrole(self, ctx: Context):
        """Set feedback role permissions."""
        if ctx.invoked_subcommand is None or\
                isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @setfeedback_addrole.command(
        name="read", pass_context=True, no_pm=True)
    async def setfeedback_addrole_read(self, ctx: Context, role):
        """Set feedback read role."""
        server = ctx.message.server
        r = discord.utils.get(server.roles, name=role)
        if r is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(
                    role))
            return
        if server.id not in self.settings:
            self.init_server_settings(server)
        if r.id in self.settings[server.id]["read_roles"]:
            return
        self.settings[server.id]["read_roles"].append(r.id)
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Added {} in list of roles allowed to read feedbacks."
            "".format(role))

    @setfeedback_addrole.command(
        name="send", pass_context=True, no_pm=True)
    async def setfeedback_addrole_send(self, ctx: Context, role):
        """Set roles which can accept feedback."""
        server = ctx.message.server
        r = discord.utils.get(server.roles, name=role)
        if r is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(
                    role))
            return
        if server.id not in self.settings:
            self.init_server_settings(server)
        if r.id in self.settings[server.id]["send_roles"]:
            return
        self.settings[server.id]["send_roles"].append(r.id)
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Added {} in list of roles allowed to send feedbacks."
            "".format(role))

    @setfeedback.group(name="removerole", pass_context=True, no_pm=True)
    async def setfeedback_removerole(self, ctx: Context):
        """Add roles."""
        if ctx.invoked_subcommand is None or\
                isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @setfeedback_removerole.command(
        name="read", pass_context=True, no_pm=True)
    async def setfeedback_removerole_read(self, ctx: Context, role):
        """Set feedback read role."""
        server = ctx.message.server
        r = discord.utils.get(server.roles, name=role)
        if r is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(
                    role))
            return
        if server.id not in self.settings:
            return
        self.settings[server.id]["read_roles"].remove(r.id)
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Removed {} in list of roles allowed to read feedbacks."
            "".format(role))

    @setfeedback_removerole.command(
        name="send", pass_context=True, no_pm=True)
    async def setfeedback_removerole_send(self, ctx: Context, role):
        """Remove feedback role."""
        server = ctx.message.server
        r = discord.utils.get(server.roles, name=role)
        if r is None:
            await self.bot.say(
                "{} is not a valid role on this server.".format(
                    role))
            return
        if server.id not in self.settings:
            return
        self.settings[server.id]["send_roles"].remove(r.id)
        dataIO.save_json(JSON, self.settings)
        await self.bot.say(
            "Removed {} in list of roles allowed to send feedbacks."
            "".format(role))

    @setfeedback.command(name="status", pass_context=True, no_pm=True)
    async def setfeedback_status(self, ctx: Context):
        """Display list of roles allowed to use feedback."""
        server = ctx.message.server
        if server.id not in self.settings:
            return
        s = self.settings[server.id]
        if "send_roles" in s:
            roles = [
                discord.utils.get(
                    server.roles, id=id).name for id in s["send_roles"]]
            await self.bot.say(
                "List of roles allowed to send feedback: {}"
                "".format(", ".join(roles)))
        if "read_roles" in s:
            roles = [
                discord.utils.get(
                    server.roles, id=id).name for id in s["read_roles"]]
            await self.bot.say(
                "List of roles allowed to read feedback: {}"
                "".format(", ".join(roles)))
        if "channel" in s:
            channel = discord.utils.get(server.channels, id=s["channel"])
            await self.bot.say("Channel: {}".format(channel))
        if "feedbacks" in s:
            await self.bot.say("Feedbacks: {}".format(len(s["feedbacks"])))

    @commands.command(name="feedback", pass_context=True, no_pm=False)
    async def feedback(self, ctx: Context, *, msg: str):
        """Send feedback as message or DM."""
        author = ctx.message.author
        server = None
        if ctx.message.server is not None:
            server = ctx.message.server
        if server is None:
            servers = []
            for server_id in self.settings:
                server = self.bot.get_server(server_id)
                if author in server.members:
                    servers.append(server)
            if not len(servers):
                await self.bot.say("You are not in the list of servers.")
                return
            if len(servers) > 1:
                out = []
                out.append(
                    "Please choose a server you would like to leave"
                    "feedback for:")
                out.append("\n".join([
                    "{}. {}".format(i, server)
                    for i, server in enumerate(servers)]))
                await self.bot.say("\n".join(out))

                def check(msg):
                    """Validation."""
                    content = msg.content
                    if not content.isdigit():
                        return False
                    content = int(content)
                    if not content < len(servers):
                        return False
                    return True

                answer = await self.bot.wait_for_message(
                    author=author, timeout=60, check=check)
                server = servers[int(answer.content)]
            else:
                server = servers[0]

        settings = self.settings[server.id]

        if "feedbacks" not in settings:
            settings["feedbacks"] = {}
        if author.id not in settings["feedbacks"]:
            settings["feedbacks"][author.id] = []
        settings["feedbacks"][author.id].append(
            self.feedback_data(author, msg))
        dataIO.save_json(JSON, self.settings)

        channel_id = settings["channel"]
        channel = self.bot.get_channel(channel_id)

        feedbackmsg = "**[{}]** {}".format(author, msg)
        await self.bot.send_message(
            channel, feedbackmsg)

        await self.bot.say(
            "Feedback for {} received. "
            "Someone will reply to you shortly.".format(server.name))

    @commands.command(
        name="feedbackreply", aliases="freply",
        pass_context=True, no_pm=True)
    async def feedbackreply(self, ctx, user: discord.Member, *, msg):
        """Reply to user."""
        author = ctx.message.author
        server = ctx.message.server
        if server is None:
            return
        if server.id not in self.settings:
            return
        settings = self.settings[server.id]["feedbacks"]
        if user is None:
            return
        if user.id not in settings:
            await self.bot.say(
                "{} has not left any feedback on this server.".format(
                    user.display_name))
            return
        settings[user.id].append(
            self.feedback_data(author, msg))
        dataIO.save_json(JSON, self.settings)

        replymsg = '**[{}]** {}'.format(author, msg)
        await self.bot.send_message(user, replymsg)
        await self.bot.send_message(
            user, "Use the feedback command again if you wish to reply.")
        await self.bot.say(
            'Reply sent via DM to {}'.format(
                user.display_name))

    def feedback_data(self, user: discord.Member, msg):
        """Return feedback data dictionary."""
        return {
            "author_name": user.display_name,
            "author_id": user.id,
            "time": dt.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            "message": msg
        }



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
    """Setup cog."""
    check_folder()
    check_file()
    bot.add_cog(Feedback(bot))
