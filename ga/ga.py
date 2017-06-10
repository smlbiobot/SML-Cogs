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
import re
import uuid

from collections import OrderedDict

from discord import Message
from discord import Member
from discord import Server
from discord import Channel
from discord import ChannelType
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context

from cogs.utils import checks

from __main__ import send_cmd_help

import google_measurement_protocol as gmp

from cogs.utils.dataIO import dataIO

PATH = os.path.join('data', 'ga')
JSON = os.path.join(PATH, 'settings.json')

ALPHANUM_PROG = re.compile('\W')


class GA:
    """Send activity of Discord using Google Analytics."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = dataIO.load_json(JSON)

    @checks.serverowner_or_permissions(manage_server=True)
    @commands.group(pass_context=True)
    async def setga(self, ctx):
        """Set Firebase settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @setga.command(name="tid", pass_context=True)
    async def setga_tid(self, ctx, tid):
        """Set Google Analaytics TID."""
        self.settings["TID"] = tid
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Google Analaytics TID saved.")
        await self.bot.delete_message(ctx.message)

    def get_member_uuid(self, member: Member):
        """Get member uuid."""
        client_id = uuid.uuid4()
        if "USERS" not in self.settings:
            self.settings["USERS"] = {}
        if member.id in self.settings["USERS"]:
            client_id = uuid.UUID(self.settings["USERS"][member.id])
        else:
            self.settings["USERS"][member.id] = str(client_id)
        dataIO.save_json(JSON, self.settings)
        return client_id

    async def on_message(self, msg: Message):
        """Track on message."""
        author = msg.author
        server = msg.server
        channel = msg.channel

        if author is None:
            return
        if server is None:
            return
        if not author.id:
            return
        if not server.id:
            return
        if channel is None:
            return
        if channel.is_private:
            return
        if "TID" not in self.settings:
            return

        # client_id = self.get_member_uuid(author)
        # use new uuid for pageviews so they will be logged as counters
        # theory: GA might not add hits if the same uuid is accessing
        # same “page” multiple times within a short time period.
        client_id = uuid.uuid4()

        # message author
        self.log_author(uuid.uuid4(), server, channel, author)
        self.log_message(uuid.uuid4(), server, channel, author)

        # message channel
        self.log_channel(uuid.uuid4(), server, channel, author)

    async def on_command(self, command: Command, ctx: Context):
        """Track command usage."""
        server = ctx.message.server
        author = ctx.message.author
        channel = ctx.message.channel

        if server is None:
            return
        if author is None:
            return
        if "TID" not in self.settings:
            return

        # client_id = self.get_member_uuid(author)
        client_id = uuid.uuid4()
        self.log_command(client_id, server, channel, author, command)

    def gmp_report_pageview(
            self, client_id,
            path=None, title=None):
        """Send GMP Pageview."""
        tid = self.settings["TID"]
        gmp.report(
            tid,
            client_id,
            gmp.PageView(
                path=path,
                title=title))

    def gmp_report_event(
            self, client_id,
            category, action, label=None, value=None):
        """Send GMP event."""
        tid = self.settings["TID"]
        gmp.report(
            tid,
            client_id,
            gmp.Event(
                category,
                action,
                label=label,
                value=value))

    def log_channel(
            self, client_id,
            server: Server, channel: Channel, member: Member):
        """Log channel usage."""
        server_name = self.url_escape(server.name)
        channel_name = self.url_escape(channel.name)
        member_name = self.url_escape(member.display_name)
        self.gmp_report_event(
            client_id,
            '{}: Channels'.format(server_name),
            channel_name,
            label=member_name,
            value=1)

        log_params = OrderedDict([
            ('server', server),
            ('channel', channel)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)
        log_params = OrderedDict([
            ('server', server),
            ('channel', channel),
            ('member', member)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

    def log_author(
            self, client_id,
            server: Server, channel: Channel, member: Member):
        """Log user activity."""
        server_name = self.url_escape(server.name)
        channel_name = self.url_escape(channel.name)
        member_name = self.url_escape(member.display_name)
        self.gmp_report_event(
            client_id,
            '{}: Authors'.format(server_name),
            member_name,
            label=channel_name,
            value=1)
        log_params = OrderedDict([
            ('server', server),
            ('member', member)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

        log_params = OrderedDict([
            ('server', server),
            ('member', member),
            ('channel', channel)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

    def log_message(
            self, client_id,
            server: Server, channel: Channel, member: Member):
        """Log messages."""
        server_name = self.url_escape(server.name)
        self.gmp_report_event(
            client_id,
            '{}: Messages'.format(server_name),
            server_name,
            label=server_name,
            value=1)

        log_params = OrderedDict([
            ('server', server)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

    def log_command(
            self, client_id,
            server: Server, channel: Channel,
            member: Member, command: Command):
        """Log command usage."""
        server_name = self.url_escape(server.name)
        channel_name = self.url_escape(channel.name)
        member_name = self.url_escape(member.display_name)
        self.gmp_report_event(
            client_id,
            '{}: Commands'.format(server_name),
            command.name,
            label='{}: {}: {}'.format(
                server_name,
                channel_name,
                member_name),
            value=1)

        log_params = OrderedDict([
            ('server', server),
            ('command', command)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

        log_params = OrderedDict([
            ('server', server),
            ('command', command),
            ('member', member)
        ])
        self.log_pageview_names(client_id, log_params)
        self.log_pageview_ids(client_id, log_params)

    def log_pageview_ids(self, client_id, params: OrderedDict):
        """Log events as serializable id path."""
        path = '/id'
        title = ''
        for k, v in params.items():
            if k == 'server':
                path += '/server/' + v.id
                title += self.url_escape(v.name) + ': '
            if k == 'channel':
                path += '/channel/' + v.id
                title += self.url_escape(v.name) + ': '
            if k == 'member':
                path += '/member/' + v.id
                title += self.url_escape(v.display_name) + ': '
            if k == 'command':
                path += '/command/' + v.name
                title += self.url_escape(v.name) + ': '
        title = title.rsplit(':', 1)[0]
        self.gmp_report_pageview(client_id, path, title)

    def log_pageview_names(self, client_id, params: OrderedDict):
        """Log events as serializable id path."""
        path = '/name'
        title = ''
        for k, v in params.items():
            if k == 'server':
                path += '/server/' + self.url_escape(v.name)
                title += self.url_escape(v.name) + ': '
            if k == 'channel':
                path += '/channel/' + self.url_escape(v.name)
                title += self.url_escape(v.name) + ': '
            if k == 'member':
                path += '/member/' + self.url_escape(v.display_name)
                title += self.url_escape(v.display_name) + ': '
            if k == 'command':
                path += '/command/' + self.url_escape(v.name)
                title += self.url_escape(v.name) + ': '
        title = title.rsplit(':', 1)[0]
        self.gmp_report_pageview(client_id, path, title)

    def url_escape(self, text):
        """Escaped member name."""
        return re.sub(ALPHANUM_PROG, '', text)


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
    n = GA(bot)
    bot.add_cog(n)

