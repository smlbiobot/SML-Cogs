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

import discord
from discord.ext import commands
from discord.ext.commands import Context
from cogs.utils.chat_formatting import pagify
from .utils import checks
from random import choice
import math
from __main__ import send_cmd_help
from cogs.economy import SetParser

RULES_URL = "https://www.reddit.com/r/CRRedditAlpha/comments/584ba2/reddit_alpha_clan_family_rules/"
ROLES_URL = "https://www.reddit.com/r/CRRedditAlpha/wiki/roles"
DISCORD_URL = "http://tiny.cc/alphachat"

welcome_msg = "Hi {}! Are you in the Reddit Alpha Clan Family (RACF) / " \
              "interested in joining our clans / just visiting?"

CHANGECLAN_ROLES = ["Leader", "Co-Leader", "Elder", "High Elder", "Member"]
DISALLOWED_ROLES = ["SUPERMOD", "MOD", "Bot Commander",
                    "Higher Power", "AlphaBot"]
BOTCOMMANDER_ROLE = ["Bot Commander"]


class RACF:
    """Display RACF specifc info.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def racf(self, ctx: Context):
        """RACF Rules + Roles."""
        server = ctx.message.server

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        data = discord.Embed(
            color=discord.Color(value=color),
            title="Rules + Roles",
            description="Important information for all members. Please read.")

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(name=server.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say(
                "I need the `Embed links` permission to send this.")

        out = []
        out.append("**Rules**")
        out.append("<{}>".format(RULES_URL))
        out.append('')
        out.append("**Roles**")
        out.append("<{}>".format(ROLES_URL))
        out.append('')
        out.append("**Discord invite**")
        out.append("<{}>".format(DISCORD_URL))
        await self.bot.say('\n'.join(out))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*CHANGECLAN_ROLES)
    async def changeclan(self, ctx, clan: str=None):
        """Update clan role when moved to a new clan.

        Example: !changeclan Delta
        """
        clans = ["Alpha", "Bravo", "Charlie", "Delta",
                 "Echo", "Foxtrot", "Golf", "Hotel",
                 "Nation", "Royale"]
        author = ctx.message.author
        server = ctx.message.server

        if clan is None:
            await send_cmd_help(ctx)
            return

        if clan not in clans:
            await self.bot.say("{} is not a valid clan.".format(clan))
            return

        clan_roles = [r for r in server.roles if r.name in clans]

        to_remove_roles = set(author.roles) & set(clan_roles)
        to_add_roles = [r for r in server.roles if r.name == clan]

        await self.bot.remove_roles(author, *to_remove_roles)
        await self.bot.say("Removed {} for {}".format(
            ",".join([r.name for r in to_remove_roles]),
            author.display_name))

        await self.bot.add_roles(author, *to_add_roles)
        await self.bot.say("Added {} for {}".format(
            ",".join([r.name for r in to_add_roles]),
            author.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def addrole(self, ctx, member: discord.Member=None,
                      role_name:str=None):
        """Add role to a user.

        Example: !addrole SML Delta

        Role name needs be in quotes if it is a multi-word role.
        """
        server = ctx.message.server
        if member is None:
            await self.bot.say("You must specify a member.")
        elif role_name is None:
            await self.bot.say("You must specify a role.")
        elif role_name in DISALLOWED_ROLES:
            await self.bot.say("You are not allowed to add those roles.")
        elif role_name not in [r.name for r in server.roles]:
            await self.bot.say("{} is not a valid role.".format(role_name))
        else:
            to_add_roles = [r for r in server.roles if r.name == role_name]
            await self.bot.add_roles(member, *to_add_roles)
            await self.bot.say("Added {} for {}".format(
                role_name, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def removerole(self, ctx, member: discord.Member=None,
                         role_name: str=None):
        """Remove role from a user.

        Example: !removerole SML Delta

        Role name needs be in quotes if it is a multi-word role.
        """
        server = ctx.message.server
        if member is None:
            await self.bot.say("You must specify a member.")
        elif role_name is None:
            await self.bot.say("You must specify a role.")
        elif role_name in DISALLOWED_ROLES:
            await self.bot.say("You are not allowed to remove those roles.")
        elif role_name not in [r.name for r in server.roles]:
            await self.bot.say("{} is not a valid role.".format(role_name))
        else:
            to_remove_roles = [r for r in server.roles if r.name == role_name]
            await self.bot.remove_roles(member, *to_remove_roles)
            await self.bot.say("Removed {} from {}".format(
                role_name, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def changerole(self, ctx, member: discord.Member=None, *roles: str):
        """Change roles of a user.

        Example: !changerole SML +Delta "-Foxtrot Lead" "+Delta Lead"

        Multi-word roles must be surrounded by quotes.
        Operators are used as prefix:
        + for role addition
        - for role removal
        """
        server = ctx.message.server
        if member is None:
            await self.bot.say("You must specify a member")
            return
        elif roles is None or not roles:
            await self.bot.say("You must specify a role.")
            return

        server_role_names = [r.name for r in server.roles]
        role_args = []
        flags = ['+', '-']
        for role in roles:
            has_flag = role[0] in flags
            flag = role[0] if has_flag else '+'
            name = role[1:] if has_flag else role

            if name in server_role_names:
                role_args.append({'flag': flag, 'name': name})

        plus = [r['name'] for r in role_args if r['flag'] == '+']
        minus = [r['name'] for r in role_args if r['flag'] == '-']

        for role in server.roles:
            if role.name not in DISALLOWED_ROLES:
                if role.name in minus:
                    await self.bot.remove_roles(member, role)
                    await self.bot.say(
                        "Removed {} from {}".format(
                            role.name, member.display_name))
                if role.name in plus:
                    await self.bot.add_roles(member, role)
                    await self.bot.say(
                        "Added {} for {}".format(
                            role.name, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(mention_everyone=True)
    async def mentionusers(self, ctx, role: str, *msg):
        """Mention users by role.

        Example:
        !mentionusers Delta Anyone who is 4,300+ please move up to Charlie!

        Note: only usable by people with the permission to mention @everyone
        """
        server = ctx.message.server
        server_roles_names = [r.name for r in server.roles]

        if role not in server_roles_names:
            await self.bot.say(
                "{} is not a valid role on this server.".format(role))
        elif not msg:
            await self.bot.say("You have not entered any messages.")
        else:
            out_mentions = []
            for m in server.members:
                if role in [r.name for r in m.roles]:
                    out_mentions.append(m.mention)
            await self.bot.say("{} {}".format(" ".join(out_mentions),
                                              " ".join(msg)))

    @commands.command(pass_context=True, no_pm=True)
    async def avatar(self, ctx, member: discord.Member=None):
        """Display avatar of the user."""
        author = ctx.message.author

        if member is None:
            member = author
        avatar_url = member.avatar_url
        data = discord.Embed()
        data.set_image(url=avatar_url)
        await self.bot.say(embed=data)

    @commands.command(pass_context=True, no_pm=True)
    async def serverinfo2(self, ctx: Context):
        """Show server's informations specific to RACF."""
        server = ctx.message.server
        online = len([m.status for m in server.members
                      if m.status == discord.Status.online or
                      m.status == discord.Status.idle])
        total_users = len(server.members)
        text_channels = len([x for x in server.channels
                             if x.type == discord.ChannelType.text])
        voice_channels = len(server.channels) - text_channels
        passed = (ctx.message.timestamp - server.created_at).days
        created_at = ("Since {}. That's over {} days ago!"
                      "".format(server.created_at.strftime("%d %b %Y %H:%M"),
                                passed))

        role_names = [
            "Leader", "Co-Leader", "High Elder", "Elder",
            "Member", "Honorary Member", "Visitor"]
        role_count = {}
        for role_name in role_names:
            role_count[role_name] = len(
                [m for m in server.members
                    if role_name in [r.name for r in m.roles]])

        colour = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        colour = int(colour, 16)

        data = discord.Embed(
            description=created_at,
            colour=discord.Colour(value=colour))
        data.add_field(name="Region", value=str(server.region))
        data.add_field(name="Users", value="{}/{}".format(online, total_users))
        data.add_field(name="Text Channels", value=text_channels)
        data.add_field(name="Voice Channels", value=voice_channels)
        data.add_field(name="Roles", value=len(server.roles))
        data.add_field(name="Owner", value=str(server.owner))
        data.add_field(name="\a", value="\a", inline=False)

        for role_name in role_names:
            data.add_field(name="{}s".format(role_name),
                           value=role_count[role_name])

        data.set_footer(text="Server ID: " + server.id)

        if server.icon_url:
            data.set_author(name=server.name, url=server.icon_url)
            data.set_thumbnail(url=server.icon_url)
        else:
            data.set_author(name=server.name)

        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("I need the `Embed links` permission "
                               "to send this")

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def member2visitor(self, ctx: Context, *members: discord.Member):
        """Re-assign list of people from members to visitors."""
        server = ctx.message.server
        to_remove_roles = [r for r in server.roles if r.name == 'Member']
        to_add_roles = [r for r in server.roles if r.name == 'Visitor']
        for member in members:
            await self.bot.add_roles(member, *to_add_roles)
            await self.bot.say("Added {} for {}".format(
                *to_add_roles, member.display_name))
            await self.bot.remove_roles(member, *to_remove_roles)
            await self.bot.say("Removed {} from {}".format(
                *to_remove_roles, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def dmusers(self, ctx: Context, msg: str=None,
                      *members: discord.Member):
        """Send a DM to a list of people.

        Example
        !dmusers "Please move up to Charlie" @SML @6john Meridian
        """
        if msg is None:
            await self.bot.say("Please include a message.")
        elif not len(members):
            await self.bot.say("You must include at least one member.")
        else:
            data = discord.Embed(description=msg)
            data.set_author(
                name=ctx.message.author,
                icon_url=ctx.message.author.avatar_url)
            data.set_footer(text=ctx.message.server.name)
            data.add_field(
                name="How to reply",
                value="DM or tag {0.mention} if you want to reply.".format(
                    ctx.message.author))
            for m in members:
                await self.bot.send_message(m, embed=data)
                await self.bot.say("Message sent to {}".format(m.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def changenick(
            self, ctx: Context, member: discord.Member, nickname: str):
        """Change the nickname of a member.

        Example
        !changenick SML "New Nick"
        !changenick @SML "New Nick"
        """
        # await self.bot.change_nickname(member, nickname)
        try:
            await self.bot.change_nickname(member, nickname)
        except discord.HTTPException:
            await self.bot.say(
                "I don’t have permission to do this.")
        else:
            await self.bot.say(f"{member.mention} changed to {nickname}.")

    @commands.command(pass_context=True, no_pm=True)
    async def emojis(self, ctx: Context):
        """Show all emojis available on server."""
        server = ctx.message.server
        out = []
        for emoji in server.emojis:
            # Discord emojis: <:joyless:230104023305420801>
            emoji_str = "<:{0.name}:{0.id}>".format(emoji)
            out.append("{} `:{}:`".format(emoji_str, emoji.name))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True)
    async def listroles(self, ctx: Context):
        """List all the roles on the server."""
        server = ctx.message.server
        if server is None:
            return
        out = []
        out.append("__List of roles on {}__".format(server.name))
        roles = {}
        for role in server.roles:
            roles[role.id] = {'role': role, 'count': 0}
        for member in server.members:
            for role in member.roles:
                roles[role.id]['count'] += 1
        for role in server.role_hierarchy:
            out.append("**{}** ({} members)".format(role.name,
                                                    roles[role.id]['count']))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True)
    async def trophy2rank(self, ctx: Context, trophies:int):
        """Convert trophies to rank.

        log10(rank) = -2.102e-3 * trophies + 14.245
        """
        # log_a(b) = (log_e b / log_e a))
        # (log_a b = 3 => b = a^3)
        rank = 10 ** (-2.102e-3 * int(trophies) + 14.245)
        rank = int(rank)
        await self.bot.say(
            f"With {trophies} trophies, the approximate rank you will get is {rank:d}")
        await self.bot.say("Calculated using 28 data points only so it may not be accurate.")

    @commands.command(pass_context=True, no_pm=True)
    async def rank2trophy(self, ctx: Context, rank:int):
        """Convert rank to trophies.

        log10(rank) = -2.102e-3 * trophies + 14.245
        """
        trophies = (math.log10(int(rank)) - 14.245) / -2.102e-3
        trophies = int(trophies)
        await self.bot.say(
            f"Rank {rank} will need approximately {trophies:d} trophies.")
        await self.bot.say("Calculated using 28 data points only so it may not be accurate.")

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def bankset(
            self, ctx: Context, user: discord.Member, credits: SetParser):
        """Work around to allow MODs to set bank."""
        econ = self.bot.get_cog("Economy")
        await ctx.invoke(econ._set, user, credits)

def setup(bot):
    r = RACF(bot)
    bot.add_cog(r)
