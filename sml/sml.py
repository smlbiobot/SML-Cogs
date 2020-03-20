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
import io
import json
import os
from collections import defaultdict
from random import sample

import aiohttp
import discord
from cogs.utils import checks
from cogs.utils.dataIO import dataIO
from discord.ext import commands

PATH = os.path.join("data", "sml")
JSON = os.path.join(PATH, "settings.json")

RAFFLE_ANNOUNCE_TEST = """
{role_mention} 

:flag_us::flag_gb: Discord Emote Raffle! React with :pekka: for a chance to win the emote. {winners} winners in {minutes} minutes.
:flag_jp: Discordでのエモート特別抽選！ 下のペッカエモートを押して当選を目指しましょう。時間は{minutes}分以内で{winners}人が当選します！
:flag_cn: Discord的表情抽奖! 加 :pekka: 表情就有机会赢这个表情。{minutes}分钟后会抽{winners}个赢家。
:flag_vn: Xổ số emote trên Discord! Thả biểu cảm :pekka: để có cơ hội dành được emote! Lấy {winners} người thắng cuộc sau {minutes} phút.
:flag_es: Sorteo de emote en discord! Reacciona con :pekka: para tener una oportunidad de ganar el emote! {winners} ganadores en {minutes} minutos
بخت آزمایی ! {winners} برنده در {minutes} دقیقه. با :pekka: واکنش نشان دهید :flag_ir:
"""


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class SML:
    """SML utilities"""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @checks.is_owner()
    @commands.group(pass_context=True)
    async def smlset(self, ctx):
        """SML Settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @smlset.command(name="verified_endpoint", pass_context=True)
    async def smlset_verified_endpoint(self, ctx, url):
        """Set verified endpoint"""
        self.settings["verified_player_endpoint"] = url
        dataIO.save_json(JSON, self.settings)
        await self.bot.say("Endpoint saved")
        await self.bot.delete_message(ctx.message)

    async def discord_id_to_player_tag(self, discord_id):
        url = self.settings.get('verified_player_endpoint')
        url += "&discord_id={}".format(discord_id)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        results = data.get('results', [])
        if results:
            return results[0]
        return None

    @checks.is_owner()
    @commands.group(pass_context=True)
    async def sml(self, ctx):
        """SML"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @sml.command(name="copypin", pass_context=True, no_pm=True)
    async def sml_copypin(self, ctx):
        """Copy pinned messages from this channel."""
        channel = ctx.message.channel
        messages = await self.bot.pins_from(channel)
        message_dicts = []
        for message in messages:
            message_dicts.append({
                "timestamp": message.timestamp.isoformat(),
                "author_id": message.author.id,
                "author_name": message.author.name,
                "content": message.content,
                "emebeds": message.embeds,
                "channel_id": message.channel.id,
                "channel_name": message.channel.name,
                "server_id": message.server.id,
                "server_name": message.server.name,
                "mention_everyone": message.mention_everyone,
                "mentions_id": [m.id for m in message.mentions],
                "mentions_name": [m.name for m in message.mentions]
            })

        filename = "pinned_messages.json"
        with io.StringIO() as f:
            json.dump(message_dicts, f, indent=4)
            f.seek(0)
            await ctx.bot.send_file(
                channel,
                f,
                filename=filename
            )

    @commands.command(pass_context=True)
    async def somecog(self, ctx, *args):
        if not args:
            await self.bot.say(1)
        elif args[0] == 'help':
            if len(args) == 1:
                await self.bot.say(2)
            elif args[1] == 'this':
                await self.bot.say(3)

    @commands.command(pass_context=True)
    async def testinlinelink(self, ctx):
        desc = "[`inline block`](http://google.com)"
        em = discord.Embed(
            title="Test",
            description=desc
        )
        await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def snap(self, ctx, *, msg):
        """Delete message after timeout

        !snap send message here (remove in 60 seconds)
        !snap 15 send message (remove in 15 seconds)
        """
        timeout = 15
        parts = str(msg).split(' ')
        if parts[0].isdigit():
            timeout = int(parts[0])
            msg = " ".join(parts[1:])

        await self.bot.delete_message(ctx.message)
        m = await self.bot.say(
            "{author} said: {message}".format(
                author=ctx.message.author.mention,
                message=msg,
            )
        )
        await asyncio.sleep(timeout)
        try:
            await self.bot.delete_message(m)
        except:
            pass

    @commands.command(pass_context=True, aliases=['lm'])
    async def list_members(self, ctx, *, roles=None):
        """List members.

        list according to time joint
        """

        server = ctx.message.server
        import datetime as dt
        now = dt.datetime.utcnow()

        members = server.members
        if roles:
            roles = roles.split(" ")
            for role in roles:
                r = discord.utils.get(server.roles, name=role)
                if r:
                    members = [m for m in members if r in m.roles]

        if members:
            desc = "All"
            if roles:
                desc = "with Roles: {}".format(", ".join(roles))
            em = discord.Embed(
                title="Server Members",
                description=desc
            )

            def rel_date(time):
                days = (now - time).days
                return days

            out = "\n".join([
                "`{:3d}` **{}** {} days".format(index, m, rel_date(m.joined_at))
                for index, m in
                enumerate(
                    sorted(
                        members,
                        key=lambda x: x.joined_at
                    )[:30],
                    1
                )
            ])

            em.add_field(
                name="Members",
                value=out
            )
            await self.bot.say(embed=em)
        else:
            await self.bot.say("No members found with those roles")

    async def _get_reacted_users(self, reaction):
        reaction_users = []
        after = None
        count = 100
        while True:
            reacted = await self.bot.get_reaction_users(reaction, limit=count, after=after)
            reaction_users.extend(reacted)
            after = reacted[-1]
            if len(reacted) != count:
                break
            import asyncio
            await  asyncio.sleep(0)
        return reaction_users

    async def ensure_role_for_reaction(self, ctx, channel_name=None, message_id=None, role_name=None):
        server = ctx.message.server
        channel = None
        for c in server.channels:
            if c.name == channel_name:
                channel = c

        if channel is None:
            return

        message = await self.bot.get_message(
            channel,
            message_id
        )

        # <:pekka:683662006917922850>
        pekka_reaction = None
        for reaction in message.reactions:
            if reaction.custom_emoji:
                # <:emoji_name:emoji_id>
                emoji = '<:{}:{}>'.format(
                    reaction.emoji.name,
                    reaction.emoji.id)
            else:
                emoji = reaction.emoji

            if emoji != '<:pekka:683662006917922850>':
                continue

            pekka_reaction = reaction

        reaction_users = await self._get_reacted_users(pekka_reaction)

        giveaway_role = discord.utils.get(server.roles, name=role_name)

        valid_users = []
        for u in reaction_users:
            if u == self.bot.user:
                continue
            valid_users.append(u)

        user_ids = [u.id for u in valid_users]
        members = []
        for uid in user_ids:
            member = server.get_member(uid)
            if member and giveaway_role not in member.roles and not member.bot:
                members.append(member)

        await self.bot.say("Total reacted members: {}".format(len(user_ids)))
        await self.bot.say("Total members without role: {}".format(len(members)))

        for member in members:
            await self.bot.add_roles(member, giveaway_role)
            await self.bot.say("Add Giveaway role to {}".format(member.mention))

        remove_members = []
        for member in server.members:
            if giveaway_role in member.roles:
                if member.id not in user_ids:
                    if not member.bot:
                        remove_members.append(member)

        await self.bot.say("People who should be removed count: {}".format(len(remove_members)))

        for member in remove_members:
            await self.bot.remove_roles(member, giveaway_role)
            await self.bot.say("Remove Giveaway role from {}".format(member.mention))

        await self.bot.say("task completed")

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, aliases=['gtr'])
    async def giveaway_tourney_roles(self, ctx):
        """
        Check reactions added to specific message
        add role to people who reacted
        :return:
        """
        await self.bot.send_typing(ctx.message.channel)
        await self.ensure_role_for_reaction(
            ctx,
            channel_name='self-roles',
            message_id=683662858306715675,
            role_name='Emote.Giveaway'
        )
        await self.ensure_role_for_reaction(
            ctx,
            channel_name='self-roles-2',
            message_id=686171857350688831,
            role_name='Emote.Giveaway.2'
        )

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, aliases=['gvr', 'raffles', 'raf'])
    async def giveaway_raffles(self, ctx, channel: discord.Channel, message_id, count=1, verified=0):
        """
        Run a giveaway raffle against a message ID in channel.
        :param ctx:
        :param message_id:
        :param pick:
        :return:
        """
        await self.bot.send_typing(ctx.message.channel)
        message = await self.bot.get_message(channel, message_id)
        server = ctx.message.server

        pekka_reaction = None
        for reaction in message.reactions:
            if reaction.custom_emoji:
                # <:emoji_name:emoji_id>
                emoji = '<:{}:{}>'.format(
                    reaction.emoji.name,
                    reaction.emoji.id)
            else:
                emoji = reaction.emoji

            if emoji != '<:pekka:683662006917922850>':
                continue

            pekka_reaction = reaction

        reaction_users = await self._get_reacted_users(pekka_reaction)
        await self.bot.say("Reacted users: {}".format(len(reaction_users)))

        # draw from verified users only
        users = []
        if verified == 1:
            url = self.settings.get("verified_player_endpoint")
            if not url:
                await self.bot.say("You must set the verified player endpoint to get player tags from verified players")
                return

            verified_role = discord.utils.get(server.roles, name='Verified')
            users = [server.get_member(user.id) for user in reaction_users]
            users = [user for user in users if verified_role in user.roles]
            users = [user for user in users if user]

            await self.bot.say("Reacted users with verified role: {}".format(len(users)))
            if len(users) < count:
                await self.bot.say("Not enough users left")
                return

        else:
            users = reaction_users

        picks = sample(users, count)

        support_channel = discord.utils.get(server.channels, name='support')

        if verified == 1:
            tasks = [
                self.discord_id_to_player_tag(m.id) for m in picks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            mentions = []
            for result, user in zip(results, picks):
                mentions.append(
                    "{} `#{} {}`".format(user.mention, result.get('player_tag'), user)
                )

            o = [
                "Congratulations to \n",
                "\n".join(mentions),
                " \n({} / {})".format(count, len(reaction_users)),
                "! You have won the giveaway raffle! ",
                "If you want to gift the emote to someone else, please mention in {}. ".format(support_channel.mention),
                "Emotes will be delivered to your game account within 72 hours by Supercell. ",
            ]
        else:

            o = [
                "Congratulations to ",
                " ".join([m.mention for m in picks]),
                " ({} / {})".format(count, len(reaction_users)),
                "! You have won the giveaway raffle! ",
                "Please provide your `player name` and `player tag` in {}. ".format(support_channel.mention),
                "You must claim your prizes within 1 hour or we will pick other winners. "
                "Emotes will be delivered to your game account within 72 hours by Supercell. ",
            ]

        await self.bot.say("".join(o))

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, aliases=['araffles'])
    async def announce_raffles(self, ctx, minutes=15, count=1):
        """Announce raffles to channel"""
        channel = ctx.message.channel
        role = discord.utils.get(ctx.message.server.roles, name='Emote.Giveaway')
        role2 = discord.utils.get(ctx.message.server.roles, name='Emote.Giveaway.2')
        txt = RAFFLE_ANNOUNCE_TEST.format(
            role_mention=f"{role.mention} {role2.mention}",
            minutes=minutes,
            winners=count,
        )
        await self.bot.send_message(channel, txt)


def check_folder():
    """Check folder."""
    os.makedirs(PATH, exist_ok=True)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = SML(bot)
    bot.add_cog(n)
