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

import datetime
import re
import os
import io
import aiohttp

from collections import OrderedDict

import matplotlib
matplotlib.use('Agg')

import discord
from discord.ext import commands
from discord.ext.commands import Command
from discord.ext.commands import Context
from cogs.utils.chat_formatting import pagify

from __main__ import send_cmd_help
from .utils.dataIO import dataIO
from .utils import checks

from matplotlib import pyplot as plt

try:
    import psutil
except:
    psutil = False


try:
    import datadog
    from datadog import statsd
except ImportError:
    raise ImportError('Please install the datadog package from pip') from None


PATH_LIST = ['data', 'activity']
PATH = os.path.join(*PATH_LIST)
JSON = os.path.join(*PATH_LIST, "settings.json")
HOST = '127.0.0.1'
INTERVAL = 5

class Activity:
    """Activity Logger.

    Logs activity of a Discord server.
    Displays:
    - Most active user by message sent
    - Richest user via bank economy module
    - Server Stats

    Settings
    - server_id
      - year, week number
        - messages
        - commands
        - mentions
        - message_time
      - on_off
      - server_id
      - server_name
    """

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json(JSON)
        self.handles = {}
        self.lock = False
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.rank_max = 5
        self.task = bot.loop.create_task(self.loop_task())
        datadog.initialize(statsd_host=HOST)

    def __unload(self):
        self.lock = True
        self.session.close()
        for h in self.handles.values():
            h.close()

    @commands.group(pass_context=True)
    @checks.is_owner()
    async def activityset(self, ctx: Context):
        """Change activity logging settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @activityset.command(name="server", pass_context=True, no_pm=True)
    async def activityset_server(self, ctx: Context, on_off: bool):
        """Set loggig on or off for server events."""
        server = ctx.message.server

        self.check_server_settings(server)

        self.settings[server.id]['on_off'] = on_off

        if on_off:
            await self.bot.say(f"Logging enabled for {server}")
        else:
            await self.bot.say(f"Logging disabled for {server}")
        self.save_json()

    @commands.command(pass_context=True, no_pm=True)
    async def rank(self, ctx: Context, member: discord.Member = None):
        """Return the activity level of the caller or member.

        Example usage
        !rank
        !rank SML
        !rank @SML
        """
        server = ctx.message.server
        author = ctx.message.author

        if server is None:
            return
        if server.id not in self.settings:
            return
        if member is None:
            member = author

        self.check_server_settings(server)
        time_id = self.get_time_id()

        out = []
        out.append("**{}** (this week)".format(server.name))
        out.append("User: {}".format(member.display_name))

        server_settings = self.settings[server.id][time_id]

        msg = server_settings["messages"]
        msg_rank = 0
        msg_count = 0
        if member.id in server_settings["messages"]:
            msg = OrderedDict(
                sorted(msg.items(), key=lambda x: -x[1]["messages"]))
            for i, (k, v) in enumerate(msg.items()):
                if member.id == k:
                    msg_rank = i + 1
                    msg_count = v["messages"]
                    break

        if msg_rank:
            out.append("Message rank: #{} ({} messages sent)".format(
                msg_rank, msg_count))
        else:
            out.append("0 messages sent.")

        mentions = server_settings["mentions"]
        mention_rank = 0
        mention_count = 0
        if member.id in server_settings["mentions"]:
            mentions = OrderedDict(
                sorted(mentions.items(), key=lambda x: -x[1]["mentions"]))
            for i, (k, v) in enumerate(mentions.items()):
                if member.id == k:
                    mention_rank = i + 1
                    mention_count = v["mentions"]
                    break
        if mention_rank:
            out.append("Mentions rank: #{} (Mentioned {} times)".format(
                mention_rank, mention_count))
        else:
            out.append("Not mentioned by anyone.")


        for page in pagify("\n".join(out)):
            await self.bot.say(page)

    @commands.command(pass_context=True)
    async def ranks(self, ctx: Context, top_max: int=None):
        """Show the activity for this server."""
        server = ctx.message.server
        self.check_server_settings(server)
        time_id = self.get_time_id()

        out = []

        if top_max is None:
            top_max = self.rank_max
        else:
            top_max = int(top_max)

        out.append("**{}** (this week)".format(server.name))

        out.extend(self.get_message_ranks(server, time_id, top_max))
        out.extend(self.get_economy_ranks(server, time_id, top_max))
        out.extend(self.get_command_ranks(server, time_id, top_max))
        out.extend(self.get_mention_ranks(server, time_id, top_max))
        out.extend(self.get_channel_ranks(server, time_id, top_max))
        out.extend(self.get_emoji_ranks(server, time_id, top_max))

        # date on start of week
        dt = datetime.datetime.utcnow()
        start = dt - datetime.timedelta(days=dt.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        out.append("Data since: {} UTC".format(start.isoformat()))
        out.append("Stats data on {} UTC".format(dt.isoformat()))

        # pagify output
        pagified = list(pagify("\n".join(out), shorten_by=12))
        for page in pagified:
            await self.bot.say(page)
            if not page == pagified[-1]:
                def pagination_check(m):
                    return m.content.lower() == 'y'
                await self.bot.say(
                    "Would you like to see more results? (y/n)")
                answer = await self.bot.wait_for_message(
                    timeout=10.0,
                    author=ctx.message.author,
                    check=pagination_check)
                if answer is None:
                    await self.bot.say("Results aborted.")
                    return

    @commands.command(pass_context=True)
    async def plotactivity(self, ctx: Context):
        """Plot the activity for the week."""
        # # Three subplots sharing both x/y axes
        # f, (ax1, ax2, ax3) = plt.subplots(3, sharex=True, sharey=True)
        # ax1.plot(x, y)
        # ax1.set_title('Sharing both axes')
        # ax2.scatter(x, y)
        # ax3.scatter(x, 2 * y ** 2 - 1, color='r')
        # # Fine-tune figure; make subplots close to each other and hide x ticks for
        # # all but bottom plot.
        # f.subplots_adjust(hspace=0)
        # plt.setp([a.get_xticklabels() for a in f.axes[:-1]], visible=False)

        server = ctx.message.server
        self.check_server_settings(server)
        self.check_message_time_settings(server)

        time_id = self.get_time_id()
        settings = None
        if server.id in self.settings:
            settings = self.settings[server.id][time_id]['message_time']

        if settings is None:
            return

        facecolor = '#32363b'
        edgecolor = '#eeeeee'
        spinecolor = '#999999'
        footercolor = '#999999'
        labelcolor = '#cccccc'
        tickcolor = '#999999'
        titlecolor = '#ffffff'

        # settings[day][hour]
        fig, axes = plt.subplots(7, sharex=True, sharey=True)

        plt.xticks(range(0, 24, 4))

        days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        days_gen = (d for d in days)

        for ax in axes:
            ax.ylabel = next(days_gen)
            # await self.bot.say(day)
            for spine in ax.spines.values():
                spine.set_edgecolor(spinecolor)

        for i, (k, v) in enumerate(settings.items()):
            # fix legacy data  issues where v is not a dict
            if isinstance(v, dict):
                x = [str(k) for k in v.keys()]
                y = [int(k) for k in v.values()]
                axes[i].plot(x, y, 'o-')
                axes[i].tick_params(axis='x', colors=tickcolor)
                axes[i].tick_params(axis='y', colors=tickcolor)

        fig.subplots_adjust(hspace=0)
        plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible=False)

        plot_filename = 'plot.png'
        plot_name = ""

        with io.BytesIO() as f:
            plt.savefig(
                f, format="png", facecolor=facecolor,
                edgecolor=edgecolor, transparent=True)
            f.seek(0)
            await ctx.bot.send_file(
                ctx.message.channel,
                f,
                filename=plot_filename,
                content=plot_name)

        fig.clf()
        plt.clf()
        plt.cla()




    def get_message_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return message ranks by time id as a list."""
        out = []
        msg = self.settings[server.id][time_id]["messages"]
        msg = dict(sorted(msg.items(), key=lambda x: -x[1]["messages"]))
        out.append("__Most active members__")
        for i, (k, v) in enumerate(msg.items()):
            if i < top_max:
                out.append("`{:4d}.` {} ({} messages)".format(
                    i + 1,
                    v["name"],
                    str(v["messages"])))
        return out

    def get_economy_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return economy ranks by time id as a list."""
        out = []
        out.append("__Richest members__")
        economy = self.bot.get_cog("Economy")
        if economy is not None:
            bank = economy.bank
            if bank is not None:
                if server.id in bank.accounts:
                    accounts = bank.accounts[server.id]
                    accounts = dict(sorted(accounts.items(),
                                           key=lambda x: -x[1]["balance"]))
                    for i, (k, v) in enumerate(accounts.items()):
                        if i < top_max:
                            member = server.get_member(k)
                            if member:
                                out.append("`{:>2}.` {} ({} credits)".format(
                                    str(i + 1),
                                    member.display_name,
                                    str(v["balance"])))
        return out

    def get_command_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return command ranks by time id as a list."""
        out = []
        cmd = self.settings[server.id][time_id]["commands"]
        cmd = dict(sorted(cmd.items(), key=lambda x: -x[1]["count"]))
        out.append("__Most used commands__")
        for i, (k, v) in enumerate(cmd.items()):
            if i < top_max:
                out.append("`{:>2}.` {} ({} times)".format(
                    str(i + 1),
                    v["name"],
                    str(v["count"])))
        return out

    def get_mention_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return mentions ranks by time id as a list."""
        out = []
        mentions = self.settings[server.id][time_id]["mentions"]
        mentions = dict(sorted(mentions.items(),
                               key=lambda x: -x[1]["mentions"]))
        out.append("__Most mentioned members__")
        for i, (k, v) in enumerate(mentions.items()):
            if i < top_max:
                out.append("`{:>2}.` {} ({} times)".format(
                    str(i + 1),
                    v["name"],
                    str(v["mentions"])))
        return out

    def get_channel_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return channels ranks by time id as a list."""
        out = []
        channels = self.settings[server.id][time_id]["channels"]
        channels = dict(sorted(channels.items(),
                               key=lambda x: -x[1]["messages"]))
        out.append("__Most active channels__")
        for i, (k, v) in enumerate(channels.items()):
            if i < top_max:
                out.append("`{}.` {} ({} messages)".format(
                    str(i + 1),
                    v["name"],
                    str(v["messages"])))
        return out

    def get_emoji_ranks(
            self, server: discord.Server, time_id: str, top_max=5):
        """Return emoji ranks by time as a list."""
        out = []
        emojis = self.settings[server.id][time_id]["emojis"]
        emojis = dict(sorted(emojis.items(), key=lambda x: -x[1]["count"]))
        out.append("__Most used emojis__")
        for i, (k, v) in enumerate(emojis.items()):
            if i < top_max:
                out.append("`{}.` {} ({} times)".format(
                    str(i + 1),
                    "{}".format(v["name"]),
                    str(v["count"])))
        return out

    async def on_message(self, message: discord.Message):
        """Log number of messages."""

        author = message.author
        server = message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        # Don’t log bot messages
        if author is server.me:
            return

        # datadog log

        # datadog - mentions

        for member in message.mentions:
            statsd.increment(
                'bot.mentions',
                tags=[
                    'member:' + str(member.display_name),
                    'member_id:' + str(member.id),
                    'member_name:' + str(member.display_name)])

        # datadog - messages (msg)

        channel = message.channel
        channel_name = ''
        channel_id = ''
        if channel is not None:
            if not channel.is_private:
                channel_name = channel.name
                channel_id = channel.id
        server_id = server.id

        statsd.increment(
            'bot.msg',
            tags=[
                'author:' + str(message.author.display_name),
                'author_id:' + str(message.author.id),
                'author_name:' + str(message.author.name),
                'channel:' + str(channel_name),
                'server_id:' + str(server_id),
                'channel_name:' + str(channel_name),
                'channel_id:' + str(channel_id)])

        # datadog - send stats
        # self.send_server_roles(server)

        # json log
        time_id = self.get_time_id()

        if server.id in self.settings:
            server_settings = self.settings[server.id][time_id]

            # log message author
            if author.id not in server_settings['messages']:
                server_settings['messages'][author.id] = {
                    'name': author.display_name,
                    'id': author.id,
                    'messages': 0
                }
            author_settings = server_settings['messages'][author.id]
            author_settings['messages'] += 1

            # log message mentions
            for member in message.mentions:
                if member.id not in server_settings['mentions']:
                    server_settings['mentions'][member.id] = {
                        'name': member.display_name,
                        'id': member.id,
                        'mentions': 0
                    }
                server_settings['mentions'][member.id]['mentions'] += 1

            # log channel usage
            channel = message.channel
            if channel is not None:
                if not channel.is_private:
                    if channel.id not in server_settings['channels']:
                        server_settings['channels'][channel.id] = {
                            'name': channel.name,
                            'id': channel.id,
                            'messages': 0
                        }
                    server_settings['channels'][channel.id]['messages'] += 1

            # log emojis usage
            # Discord emojis: <:joyless:230104023305420801>
            emoji_p = re.compile('\<\:.+?\:\d+\>')
            emojis = emoji_p.findall(message.content)
            if len(emojis):
                for emoji in emojis:
                    if emoji not in server_settings['emojis']:
                        server_settings['emojis'][emoji] = {
                            'name': emoji,
                            'count': 0
                        }
                    server_settings['emojis'][emoji]['count'] += 1
            uemoji_p = re.compile(u'['
                                  u'\U0001F300-\U0001F64F'
                                  u'\U0001F680-\U0001F6FF'
                                  u'\uD83C-\uDBFF\uDC00-\uDFFF'
                                  u'\u2600-\u26FF\u2700-\u27BF]{1,2}',
                                  re.UNICODE)
            emojis = uemoji_p.findall(message.content)
            if len(emojis):
                for emoji in emojis:
                    if emoji not in server_settings['emojis']:
                        server_settings['emojis'][emoji] = {
                            'name': emoji,
                            'count': 0
                        }
                    server_settings['emojis'][emoji]['count'] += 1

            # log message time
            date = datetime.datetime.utcnow()
            hour = date.strftime("%H")
            day = date.strftime("%w")
            server_settings['message_time'][day][hour] += 1

        self.save_json()



    async def on_command(self, command: Command, ctx: Context):
        """Log command used."""
        server = ctx.message.server

        if server is None:
            return

        self.check_server_settings(server)

        if not self.settings[server.id]['on_off']:
            return

        # json log

        time_id = self.get_time_id()

        server_commands = self.settings[server.id][time_id]['commands']

        if command.name not in server_commands:
            server_commands[command.name] = {
                'name': command.name,
                'cog_name': command.cog_name,
                'count': 0
            }
        server_commands[command.name]['count'] += 1

        self.save_json()

        # datadog log
        channel = ctx.message.channel
        channel_name = ''
        channel_id = ''
        if channel is not None:
            if not channel.is_private:
                channel_name = channel.name
                channel_id = channel.id
        server_id = server.id
        server_name = server.name
        statsd.increment(
            'bot.cmd',
            tags=[
                'server_id:' + str(server_id),
                'server_name:' + str(server_name),
                'channel_name:' + str(channel_name),
                'channel_id:' + str(channel_id),
                'command_name:' + str(command),
                'cog_name:' + type(ctx.cog).__name__])


    def check_server_settings(self, server: discord.Server):
        """Verify server settings are available."""
        if server.id not in self.settings:
            self.settings[server.id] = {}

        server_settings = self.settings[server.id]

        if 'server_id' not in server_settings:
            server_settings['server_id'] = server.id
        if 'server_name' not in server_settings:
            server_settings['server_name'] = server.name
        if 'on_off' not in server_settings:
            server_settings['on_off'] = False

        time_id = self.get_time_id()

        if time_id not in server_settings:
            server_settings[time_id] = {}

        if 'messages' not in server_settings[time_id]:
            server_settings[time_id]['messages'] = {}
        if 'commands' not in server_settings[time_id]:
            server_settings[time_id]['commands'] = {}
        if 'mentions' not in server_settings[time_id]:
            server_settings[time_id]['mentions'] = {}
        if 'channels' not in server_settings[time_id]:
            server_settings[time_id]['channels'] = {}
        if 'emojis' not in server_settings[time_id]:
            server_settings[time_id]['emojis'] = {}
        if 'message_time' not in server_settings[time_id]:
            server_settings[time_id]['message_time'] = {}

        self.check_message_time_settings(server)

        self.save_json()

    def check_message_time_settings(self, server: discord.Server):
        """Create message time fields if not already set."""
        time_id = self.get_time_id()
        settings = self.settings[server.id][time_id]["message_time"]
        for day in range(0, 7):
            if str(day) not in settings:
                settings[str(day)] = {
                    '{:02d}'.format(h): 0 for h in range(0, 24)}

        # legacy get rids of hourly data
        new_settings = settings.copy()
        for k, v in settings.items():
            if len(k) > 1:
                del new_settings[k]
        settings = new_settings
        self.save_json()

    def get_time_id(self, date: datetime.date=None):
        """Return current year, week as a tuple."""
        if date is None:
            date = datetime.datetime.utcnow()
        (now_year, now_week, now_day) = date.isocalendar()
        return "{}, {}".format(now_year, now_week)

    def get_server_messages_settings(self, server: discord.Server,
                                     time_id: datetime.date=None):
        """Return the messages dict from settings."""
        if time_id is None:
            time_id = self.get_time_id()
        return self.settings[server.id][time_id]["messages"]

    def get_server_commands_settings(self, server: discord.Server,
                                     time_id: datetime.date=None):
        """Return the messages dict from settings."""
        if time_id is None:
            time_id = self.get_time_id()
        return self.settings[server.id][time_id]["commands"]

    def save_json(self):
        """Save settings."""
        dataIO.save_json(JSON, self.settings)

    def send_all(self):
        """Send all data to DataDog."""
        self.send_roles()

    def send_roles(self):
        """Send roles from all servers."""
        for server in self.bot.servers:
            self.send_server_roles(server)

    def send_server_roles(self, server: discord.Server):
        """Log server roles on datadog."""
        roles = {}
        for role in server.roles:
            roles[role.id] = {'role': role, 'count': 0}
        for member in server.members:
            for role in member.roles:
                roles[role.id]['count'] += 1

        for role in server.roles:
            role_count = roles[role.id]['count']
            statsd.gauge(
                'bot.roles.{}'.format(server.id),
                role_count,
                tags=[
                    'role_name:' + role.name,
                    'role_id:' + role.id,
                    'server_id:' + server.id,
                    'server_name:' + server.name])


    async def loop_task(self):
        await self.bot.wait_until_ready()
        self.tags = ['application:red',
                     'bot_id:' + self.bot.user.id,
                     'bot_name:' + self.bot.user.name]
        self.send_all()
        await asyncio.sleep(INTERVAL)
        if self is self.bot.get_cog('Activity'):
            self.task = self.bot.loop.create_task(self.loop_task())

def check_folders():
    if not os.path.exists(PATH):
        os.mkdir(PATH)

def check_files():
    if not dataIO.is_valid_json(JSON):
        defaults = {}
        dataIO.save_json(JSON, defaults)

def setup(bot):
    check_folders()
    check_files()
    n = Activity(bot)
    bot.add_cog(n)
