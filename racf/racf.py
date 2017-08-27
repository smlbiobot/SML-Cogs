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
import itertools
from random import choice

import discord
from __main__ import send_cmd_help
from discord.ext import commands
from discord.ext.commands import Context

import cogs
from cogs.economy import SetParser
from cogs.utils import checks
from cogs.utils.chat_formatting import pagify

RULES_URL = "https://www.reddit.com/r/CRRedditAlpha/comments/584ba2/reddit_alpha_clan_family_rules/"
ROLES_URL = "https://www.reddit.com/r/CRRedditAlpha/wiki/roles"
DISCORD_URL = "http://discord.gg/racf"

welcome_msg = "Hi {}! Are you in the Reddit Alpha Clan Family (RACF) / " \
              "interested in joining our clans / just visiting?"

CHANGECLAN_ROLES = ["Leader", "Co-Leader", "Elder", "High Elder", "Member"]
BS_CHANGECLAN_ROLES = ["Member", "Brawl-Stars"]
DISALLOWED_ROLES = ["SUPERMOD", "MOD", "AlphaBot"]
HEIST_ROLE = "Heist"
RECRUIT_ROLE = "Recruit"
TOGGLE_ROLES = ["Member", "Visitor"]
TOGGLEABLE_ROLES = [
    "Heist", "Practice", "Tourney", "Recruit", "CoC",
    "Battle-Bay", "RACF-Tourney", "Brawl-Stars", "vc-crew"]
TOGGLE_PERM = {
    "Member": [
        "Heist", "Practice", "Tourney", "Recruit", "CoC",
        "Battle-Bay", "RACF-Tourney", "Brawl-Stars", "vc-crew",
        "BSPlay"
    ],
    "Visitor": [
        "BSPlay", "Heist", "Recruit"
    ]
}
MEMBER_DEFAULT_ROLES = ["Member", "Tourney", "Practice"]
CLANS = [
    "Alpha", "Bravo", "Charlie", "Delta",
    "Echo", "Foxtrot", "Golf", "Hotel"]
BS_CLANS = [
    "BS-Alpha", "BS-Bravo", "BS-Charlie"]
BS_CLANS_PREFIX = 'BS-'
BOTCOMMANDER_ROLE = ["Bot Commander"]
HE_BOTCOMMANDER_ROLES = ["Bot Commander", "High-Elder"]
COMPETITIVE_CAPTAIN_ROLES = ["Competitive-Captain", "Bot Commander"]
COMPETITIVE_TEAM_ROLES = [
    "CRL", "RPL-NA", "RPL-EU", "RPL-APAC", "MLG",
    "ClashWars", "CRL-Elite", "CRL-Legends", "CRL-Rockets"]
KICK5050_MSG = (
    "Sorry, but you were 50/50 and we have kicked you from the clan. "
    "Please join one of our feeders for now. "
    "Our clans are Alpha / Bravo / Charlie / Delta / "
    "Echo / Foxtrot / Golf / Hotel with the red rocket emblem. "
    "Good luck on the ladder!")
BS_KICK5050_MSG = (
    "Sorry, but you were 50/50 and we have "
    "kicked you from the Brawl Stars band. "
    "Please join one of our feeders for now. "
    "Our clans are Alpha / Bravo / Charlie "
    "with the red skull emblem. "
    "Good luck in your future games!")
VISITOR_RULES = (
    "Welcome to the **Reddit Alpha Clan Family** (RACF) Discord server. "
    "As a visitor, you agree to follow the following rules: \n"
    "\n"
    "+ No spamming.\n"
    "+ No advertisement of any kind, "
    "e.g. Facebook / Twitter / YouTube / Friend Invite Links\n"
    "+ Use #bot-commands for bot features, e.g. `!deck` / `!crdata`\n"
    "+ Use #casino for bot commands related to casino, "
    "e.g. `!payday` / `!slot` / `!heist`\n"
    "\n"
    "Failure to follow these rules will get you kicked from the server. "
    "Repeat offenders will be banned.\n"
    "\n"
    "If you would like to invite your friends to join this server, "
    "you may use this Discord invite: <http://discord.gg/racf> \n"
    "\n"
    "Additional help and information: <http://racfdocs.smlbiobot.com> \n"
    "\n"
    "Thanks + enjoy!")
MEMBER_MSG = (
    "Welcome to the **Reddit Alpha Clan Family** (RACF) Discord server. "
    "Please check out <http://racfdocs.smlbiobot.com> for an overview of our family rules, "
    "together with help documentation on a plethora of bot commands for you to use and enjoy."
    "\n\n"
    "Thanks + enjoy!"
)
ELDER_MSG = (
    "Congratulations on your recent promotion to Elder! \n"
    "\n"
    "You have the following responsibilities as elder in the RACF:\n"
    "+ Accept new members.\n"
    "+ When accepting new members, you should:\n"
    ".. + Make sure that the person meets trophy requirements."
    ".. + Ask if the person is new to the RACF.\n"
    ".. + Ask that person to join our Discord server: http://discord.gg/racf\n"
    ".. + Let them know about the 50/50 kicking policy.\n"
    "+ Not allowed to kick 50/50.\n"
    "\n"
    "Please consult !rules and !roles on the RACF server for more info."
)
ELDER_REFRESH_MSG = (
    "\n"
    "You have the following responsibilities as elder in the RACF:\n"
    "+ Accept new members.\n"
    "+ When accepting new members, you should:\n"
    ".. + Make sure that the person meets trophy requirements.\n"
    ".. + Ask if the person is new to the RACF.\n"
    ".. + Ask that person to join our Discord server: http://discord.gg/racf\n"
    ".. + Let them know about the 50/50 kicking policy.\n"
    "+ Not allowed to kick 50/50.\n"
    "\n"
    "Please consult !rules and !roles on the RACF server for more info."
)
CLAN_PERMISSION = {
    '2CCCP': {
        'tag': '2CCCP',
        'role': 'Alpha',
        'assign_role': True,
        'member': True
    },
    '2U2GGQJ': {
        'tag': '2U2GGQJ',
        'role': 'Bravo',
        'assign_role': True,
        'member': True
    },
    '2QUVVVP': {
        'tag': '2QUVVVP',
        'role': 'Charlie',
        'assign_role': True,
        'member': True
    },
    'Y8GYCGV': {
        'tag': 'Y8GYCGV',
        'role': 'Delta',
        'assign_role': True,
        'member': True
    },
    'LGVV2CG': {
        'tag': 'LGVV2CG',
        'role': 'Echo',
        'assign_role': True,
        'member': True
    },
    'QUYCYV8': {
        'tag': 'QUYCYV8',
        'role': 'Foxtrot',
        'assign_role': True,
        'member': True
    },
    'GUYGVJY': {
        'tag': 'GUYGVJY',
        'role': 'Golf',
        'assign_role': True,
        'member': True
    },
    'UGQ28YU': {
        'tag': 'UGQ28YU',
        'role': 'Hotel',
        'assign_role': True,
        'member': True
    },
    'R8PPJQG': {
        'tag': 'R8PPJQG',
        'role': 'eSports',
        'assign_role': False,
        'member': True
    },
    '22LR8JJ2': {
        'tag': '22LR8JJ2',
        'role': 'Mini',
        'assign_role': True,
        'member': False
    },
    '2Q09VJC8': {
        'tag': '2Q09VJC8',
        'role': 'Mini2',
        'assign_role': True,
        'member': False
    },
}

BAND_PERMISSION = {
    'LQQ': {
        'tag': 'LQQ',
        'role': 'BS-Alpha',
        'assign_role': True,
        'member': False
    },
    '82RQLR': {
        'tag': '82RQLR',
        'role': 'BS-Bravo',
        'assign_role': True,
        'member': False
    },
    '98VLYJ': {
        'tag': '98VLYJ',
        'role': 'BS-Charlie',
        'assign_role': True,
        'member': False
    },
    'Q0YG8V': {
        'tag': 'Q0YG8V',
        'role': 'BS-Delta',
        'assign_role': True,
        'member': False
    }

}


def grouper(n, iterable, fillvalue=None):
    """Group lists into lists of items.

    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


class RACF:
    """Display RACF specifc info.

    Note: RACF specific plugin for Red
    """

    def __init__(self, bot):
        """Constructor."""
        self.bot = bot

    @commands.group(aliases=['r'], pass_context=True, no_pm=True)
    async def racf(self, ctx):
        """RACF commands."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @racf.command(name="info", pass_context=True, no_pm=True)
    async def racf_info(self, ctx: Context):
        """RACF Rules + Roles."""
        server = ctx.message.server

        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)

        em = discord.Embed(
            color=discord.Color(value=color),
            title="Rules + Roles",
            description="Important information for all members. Please read.")

        if server.icon_url:
            em.set_author(name=server.name, url=server.icon_url)
            em.set_thumbnail(url=server.icon_url)
        else:
            em.set_author(name=server.name)

        em.add_field(name='Documentation', value='http://racfdocs.smlbiobot.com')

        try:
            await self.bot.say(embed=em)
        except discord.HTTPException:
            await self.bot.say(
                "I need the `Embed links` permission to send this.")

    @racf.command(name="verify", aliases=['v'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racf_verify(self, ctx, member: discord.Member, tag):
        """Verify CR members by player tag."""

        # - Set their tags
        await ctx.invoke(self.crsettag, tag, member)

        # - Lookup profile
        crp = self.bot.get_cog('CRProfile')

        try:
            player = await crp.player_data(tag)
        except asyncio.TimeoutError:
            await self.bot.send_message(
                ctx.message.channel,
                "Getting profile info resulted in a timeout. "
                "API may be down or player tag cannot be found. "
                "Aborting…")
            return

        # - Check clan
        if player.clan_tag not in CLAN_PERMISSION.keys():
            await self.bot.say("User is not in our clans.")
            return

        # - Check allow role assignment
        perm = CLAN_PERMISSION[player.clan_tag]
        if not perm['assign_role']:
            await self.bot.say('User belong to a clan that requires roster verifications.')
            return

        # - Change nickname to IGN
        try:
            await self.bot.change_nickname(member, player.username)
        except discord.HTTPException:
            await self.bot.say(
                "I don’t have permission to change nick for this user.")
        else:
            await self.bot.say("{} changed to {}.".format(member.mention, player.username))

        # - Assign role - not members
        mm = self.bot.get_cog("MemberManagement")
        if not perm['member']:
            await ctx.invoke(mm.changerole, member, perm['role'])
        else:
            channel = discord.utils.get(
                ctx.message.server.channels, name="family-chat")
            await ctx.invoke(mm.changerole, member, perm['role'], 'member', 'tourney', 'practice', '-visitor')
            if channel is not None:
                await self.bot.say(
                    "{} Welcome! Main family chat at {} — enjoy!".format(
                        member.mention, channel.mention))

        # - Send welcome message + link to documentation
        await ctx.invoke(self.dmusers, MEMBER_MSG, member)

    @racf.command(name="bsverify", aliases=['bv'], pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def racf_bsveify(self, ctx, member: discord.Member, tag):
        """Verify BS members by player tag."""

        # - Set tags
        bsdata = self.bot.get_cog("BSData")
        await ctx.invoke(bsdata.bsdata_settag, tag, member)

        # - Lookup profile
        try:
            player = await bsdata.get_player_data(tag)
        except asyncio.TimeoutError:
            await self.bot.send_message(
                ctx.message.channel,
                "Getting profile info resulted in a timeout. "
                "API may be down or player tag cannot be found. "
                "Aborting…")
            return


        # - Check clan
        band_tag = None
        try:
            band_tag = player["band"]["tag"]
        except KeyError:
            await self.bot.say("Profile API may be down. Abording…")
            return

        if band_tag not in BAND_PERMISSION.keys():
            await self.bot.say("User is not in our clans.")
            return

        # - Assign roles
        role = BAND_PERMISSION[band_tag]["role"]
        await ctx.invoke(self.brawlstars, member, role)


    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*CHANGECLAN_ROLES)
    async def changeclan(self, ctx, clan: str = None):
        """Update clan role when moved to a new clan.

        Example: !changeclan Delta
        """
        clans = [c.lower() for c in CLANS]
        await self.do_changeclan(ctx, clan, clans)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BS_CHANGECLAN_ROLES)
    async def bschangeclan(self, ctx, clan: str = None):
        """Update clan role when moved to a new clan.

        Example: !bschangeclan BS-Delta
        """
        if clan is None:
            await send_cmd_help(ctx)
            return
        if not clan.lower().startswith(BS_CLANS_PREFIX.lower()):
            clan = BS_CLANS_PREFIX + clan
        clans = [c.lower() for c in BS_CLANS]
        await self.do_changeclan(ctx, clan, clans)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def bselder(self, ctx, member: discord.Member):
        """Add bs-elder role for member.

        TMP command for bs leader who’s not a bot comamnder.
        """
        role = discord.utils.get(ctx.message.server.roles, name="BS-Elder")
        await self.bot.add_roles(member, role)
        await self.bot.say(
            "Added {} for {}".format(
                role.name, member.display_name))

    async def do_changeclan(self, ctx, clan: str = None, clans=[]):
        """Perform clan changes."""
        author = ctx.message.author
        server = ctx.message.server

        if clan is None:
            await send_cmd_help(ctx)
            return

        if clan.lower() not in clans:
            await self.bot.say(
                "{} is not a clan you can self-assign.".format(clan))
            return

        clan_roles = [r for r in server.roles if r.name.lower() in clans]

        to_remove_roles = set(author.roles) & set(clan_roles)
        to_add_roles = [
            r for r in server.roles if r.name.lower() == clan.lower()]

        await self.bot.remove_roles(author, *to_remove_roles)
        await self.bot.say("Removed {} for {}".format(
            ",".join([r.name for r in to_remove_roles]),
            author.display_name))

        await self.bot.add_roles(author, *to_add_roles)
        await self.bot.say("Added {} for {}".format(
            ",".join([r.name for r in to_add_roles]),
            author.display_name))

    async def changerole(self, ctx, member: discord.Member = None, *roles: str):
        """Change roles of a user.

        Uses the changerole command in the MM cog.
        """
        mm = self.bot.get_cog("MemberManagement")
        if mm is None:
            await self.bot.say(
                "You must load MemberManagement for this to run.")
            return
        await ctx.invoke(mm.changerole, member, *roles)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def addrole(
            self, ctx, member: discord.Member = None, *, role_name: str = None):
        """Add role to a user.

        Example: !addrole SML Delta
        """
        await self.changerole(ctx, member, role_name)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def removerole(
            self, ctx, member: discord.Member = None, *, role_name: str = None):
        """Remove role from a user.

        Example: !removerole SML Delta
        """
        role_name = '-{}'.format(role_name)
        await self.changerole(ctx, member, role_name)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def multiaddrole(self, ctx, role, *members: discord.Member):
        """Add a role to multiple users.

        !multiaddrole rolename User1 User2 User3
        """
        for member in members:
            await self.changerole(ctx, member, role)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def multiremoverole(self, ctx, role, *members: discord.Member):
        """Remove a role from multiple users.

        !multiremoverole rolename User1 User2 User3
        """
        role = '-{}'.format(role)
        for member in members:
            await self.changerole(ctx, member, role)

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
    @checks.mod_or_permissions(mention_everyone=True)
    async def mentionrole(self, ctx, role_name: str, *, msg):
        """Mention a role with message.

        Temporarily make a role mentionable and send a message.
        Delete message sending the command so it won’t be a dupe.
        """
        server = ctx.message.server

        # role = discord.utils.get(server.roles, name=role_name)
        # find role regardless of casing
        role = None
        for r in server.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
        if role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(
                    role_name))
            return

        orig_mentionable = role.mentionable
        await self.bot.edit_role(server, role, mentionable=True)
        await self.bot.say(
            '**{author.mention}** ({author.id}): '
            '{role.mention} {message}'.format(
                author=ctx.message.author,
                role=role,
                message=msg))
        await self.bot.edit_role(server, role, mentionable=orig_mentionable)
        await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True)
    async def avatar(self, ctx, member: discord.Member = None):
        """Display avatar of the user."""
        author = ctx.message.author

        if member is None:
            member = author
        await self.bot.say(member.avatar_url)

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
    async def member2roles(self, ctx: Context, with_role, new_role):
        """Add role to a list of users with specific roles."""
        server = ctx.message.server
        with_role = discord.utils.get(server.roles, name=with_role)
        new_role = discord.utils.get(server.roles, name=new_role)
        if with_role is None:
            await self.bot.say('{} is not a valid role'.format(with_role))
            return
        if new_role is None:
            await self.bot.say('{} is not a valid role.'.format(new_role))
            return
        members = [m for m in server.members if with_role in m.roles]
        for member in members:
            await self.bot.add_roles(member, new_role)
            await self.bot.say("Added {} for {}".format(
                new_role, member.display_name))

    @commands.command(pass_context=True, no_pm=True, aliases=["m2v"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def member2visitor(self, ctx: Context, *members: discord.Member):
        """Re-assign list of people from members to visitors."""
        server = ctx.message.server
        to_add_roles = [r for r in server.roles if r.name == 'Visitor']
        for member in members:
            to_remove_roles = [
                r for r in member.roles if r.name in MEMBER_DEFAULT_ROLES]
            to_remove_roles.extend([
                r for r in member.roles if r.name in CLANS])
            to_remove_roles.extend([
                r for r in member.roles if r.name in ['eSports']])
            await self.bot.add_roles(member, *to_add_roles)
            await self.bot.say("Added {} for {}".format(
                ", ".join([r.name for r in to_add_roles]), member.display_name))
            await self.bot.remove_roles(member, *to_remove_roles)
            await self.bot.say("Removed {} from {}".format(
                ", ".join([r.name for r in to_remove_roles]), member.display_name))

    @commands.command(pass_context=True, no_pm=True, aliases=["v2m"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitor2member(
            self, ctx: Context, member: discord.Member, *roles):
        """Assign visitor to member and add clan name."""
        server = ctx.message.server
        roles_param = MEMBER_DEFAULT_ROLES.copy()
        roles_param.extend(roles)
        roles_param.append("-Visitor")
        channel = discord.utils.get(
            ctx.message.server.channels, name="family-chat")
        # print(roles_param)
        await self.changerole(ctx, member, *roles_param)
        if channel is not None:
            await self.bot.say(
                "{} Welcome! Main family chat at {} — enjoy!".format(
                    member.mention, channel.mention))

        await ctx.invoke(self.dmusers, MEMBER_MSG, member)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def dmusers(self, ctx: Context, msg: str = None,
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
            # data.add_field(
            #     name="How to reply",
            #     value="DM or tag {0.mention} if you want to reply.".format(
            #         ctx.message.author))
            for m in members:
                try:
                    await self.bot.send_message(m, embed=data)
                    await self.bot.say(
                        "Message sent to {}".format(m.display_name))
                except discord.errors.Forbidden:
                    await self.bot.say(
                        "{} does not accept DMs from me.".format(
                            m.display_name))
                    raise

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def changenick(
            self, ctx: Context, member: discord.Member, *, nickname: str):
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
            await self.bot.say("{} changed to {}.".format(member.mention, nickname))

    @commands.command(pass_context=True, no_pm=True)
    async def emojis(self, ctx: Context, embed=False):
        """Show all emojis available on server."""
        server = ctx.message.server

        if embed:
            emoji_list = [emoji for emoji in server.emojis if not emoji.managed]
            emoji_lists = grouper(25, emoji_list)
            for emoji_list in emoji_lists:
                em = discord.Embed()
                for emoji in emoji_list:
                    if emoji is not None:
                        em.add_field(
                            name=str(emoji), value="`:{}:`".format(emoji.name))
                await self.bot.say(embed=em)
        else:
            out = []
            for emoji in server.emojis:
                # only include in list if not managed by Twitch
                if not emoji.managed:
                    emoji_str = str(emoji)
                    out.append("{} `:{}:`".format(emoji_str, emoji.name))
            for page in pagify("\n".join(out), shorten_by=12):
                await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True)
    async def toggleheist(self, ctx: Context):
        """Self-toggle heist role."""
        author = ctx.message.author
        server = ctx.message.server
        heist_role = discord.utils.get(
            server.roles, name=HEIST_ROLE)
        if heist_role in author.roles:
            await self.bot.remove_roles(author, heist_role)
            await self.bot.say(
                "Removed {} role from {}.".format(
                    HEIST_ROLE, author.display_name))
        else:
            await self.bot.add_roles(author, heist_role)
            await self.bot.say(
                "Added {} role for {}.".format(
                    HEIST_ROLE, author.display_name))

    @commands.command(pass_context=True, no_pm=True)
    async def togglerecruit(self, ctx: Context):
        """Self-toggle heist role."""
        author = ctx.message.author
        server = ctx.message.server
        role = discord.utils.get(
            server.roles, name=RECRUIT_ROLE)
        if role in author.roles:
            await self.bot.remove_roles(author, role)
            await self.bot.say(
                "Removed {} role from {}.".format(
                    RECRUIT_ROLE, author.display_name))
        else:
            await self.bot.add_roles(author, role)
            await self.bot.say(
                "Added {} role for {}.".format(
                    RECRUIT_ROLE, author.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*TOGGLE_ROLES)
    async def togglerole(self, ctx: Context, role_name):
        """Self-toggle role assignments."""
        author = ctx.message.author
        server = ctx.message.server
        # toggleable_roles = [r.lower() for r in TOGGLEABLE_ROLES]

        member_role = discord.utils.get(server.roles, name="Member")
        is_member = member_role in author.roles

        if is_member:
            toggleable_roles = TOGGLE_PERM["Member"]
        else:
            toggleable_roles = TOGGLE_PERM["Visitor"]

        toggleable_roles = sorted(toggleable_roles)

        toggleable_roles_lower = [r.lower() for r in toggleable_roles]

        if role_name.lower() in toggleable_roles_lower:
            role = [
                r for r in server.roles
                if r.name.lower() == role_name.lower()]

            if len(role):
                role = role[0]
                if role in author.roles:
                    await self.bot.remove_roles(author, role)
                    await self.bot.say(
                        "Removed {} role from {}.".format(
                            role.name, author.display_name))
                else:
                    await self.bot.add_roles(author, role)
                    await self.bot.say(
                        "Added {} role for {}.".format(
                            role_name, author.display_name))
            else:
                await self.bot.say(
                    "{} is not a valid role on this server.".format(role_name))
        else:
            out = []
            out.append(
                "{} is not a toggleable role for you.".format(role_name))
            out.append(
                "Toggleable roles for you: {}.".format(
                    ", ".join(toggleable_roles)))
            await self.bot.say("\n".join(out))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*COMPETITIVE_CAPTAIN_ROLES)
    async def teamadd(self, ctx, member: discord.Member, role):
        """Add competitive team member roles."""
        server = ctx.message.server
        competitive_team_roles = [r.lower() for r in COMPETITIVE_TEAM_ROLES]
        if role.lower() not in competitive_team_roles:
            await self.bot.say(
                "{} is not a competitive team role.".format(role))
            return
        if role.lower() not in [r.name.lower() for r in server.roles]:
            await self.bot.say("{} is not a role on this server.".format(role))
            return
        roles = [r for r in server.roles if r.name.lower() == role.lower()]
        await self.bot.add_roles(member, *roles)
        await self.bot.say("Added {} for {}".format(role, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*COMPETITIVE_CAPTAIN_ROLES)
    async def teamremove(self, ctx, member: discord.Member, role):
        """Remove competitive team member roles."""
        server = ctx.message.server
        competitive_team_roles = [r.lower() for r in COMPETITIVE_TEAM_ROLES]
        if role.lower() not in competitive_team_roles:
            await self.bot.say(
                "{} is not a competitive team role.".format(role))
            return
        if role.lower() not in [r.name.lower() for r in server.roles]:
            await self.bot.say("{} is not a role on this server.".format(role))
            return
        roles = [r for r in server.roles if r.name.lower() == role.lower()]
        await self.bot.remove_roles(member, *roles)
        await self.bot.say(
            "Removed {} from {}".format(role, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*COMPETITIVE_CAPTAIN_ROLES)
    async def teamlist(self, ctx, role_name):
        """List team members with specific competitive roles.

        Default CSV output.
        """
        server = ctx.message.server
        competitive_team_roles = [r.lower() for r in COMPETITIVE_TEAM_ROLES]
        if role_name.lower() not in competitive_team_roles:
            await self.bot.say(
                "{} is not a competitive team role.".format(role_name))
            return
        role = discord.utils.get(server.roles, name=role_name)
        if role is None:
            await self.bot.say(
                '{} is not a valid role on this server.'.format(role_name))
            return
        members = [m for m in server.members if role in m.roles]
        members = sorted(members, key=lambda x: x.display_name)
        out = ', '.join([m.display_name for m in members])
        await self.bot.say(
            'List of members with {}:\n'
            '{}'.format(role_name, out))

    @commands.command(pass_context=True, no_pm=True, aliases=["k5"])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def kick5050(self, ctx, member: discord.Member):
        """Notify member that they were kicked for lower trophies.

        Remove clan tags in the process.
        """
        await ctx.invoke(self.dmusers, KICK5050_MSG, member)
        member_clan = [
            '-{}'.format(r.name) for r in member.roles if r.name in CLANS]
        if len(member_clan):
            await self.changerole(ctx, member, *member_clan)
        else:
            await self.bot.say("Member has no clan roles to remove.")

    @commands.command(pass_context=True, no_pm=True, aliases=["bsk5", "bk5"])
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def bskick5050(self, ctx, member: discord.Member):
        """Notify member that they were kicked for lower trophies.

        Remove clan tags in the process.
        """
        await ctx.invoke(self.dmusers, BS_KICK5050_MSG, member)
        member_clan = [
            '-{}'.format(r.name) for r in member.roles if r.name in BS_CLANS]
        if len(member_clan):
            await self.changerole(ctx, member, *member_clan)
        else:
            await self.bot.say("Member has no clan roles to remove.")

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def recruit(self, ctx, member: discord.Member):
        """Assign member with recruit roles and give them info.

        Command detects origin:
        If command is invoked from default channel, add Visitor role.
        If command in invoked from other channels, only add Recruit role.
        """
        recruit_roles = ["Recruit"]
        add_visitor_role = False
        if ctx.message.channel.is_default:
            recruit_roles.append("Visitor")
            add_visitor_role = True
        await self.changerole(ctx, member, *recruit_roles)
        channel = discord.utils.get(
            ctx.message.server.channels, name="esports-recruiting")
        if channel is not None:
            await self.bot.say(
                "{} Please see pinned messages "
                "in {} for eSports information.".format(
                    member.mention, channel.mention))
        if add_visitor_role:
            visitor_channel = discord.utils.get(
                ctx.message.server.channels, name="visitors")
            if visitor_channel is not None:
                await self.bot.say(
                    "{} You can now chat in {} — enjoy!".format(
                        member.mention, visitor_channel.mention))
            await ctx.invoke(self.visitorrules, member)

    @commands.command(pass_context=True, no_pm=True)
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitor(self, ctx, member: discord.Member):
        """Assign member with visitor roles and give them info."""
        visitor_roles = ["Visitor"]
        channel = discord.utils.get(
            ctx.message.server.channels, name="visitors")
        await self.changerole(ctx, member, *visitor_roles)
        if channel is not None:
            await self.bot.say(
                "{} You can now chat in {} — enjoy!".format(
                    member.mention, channel.mention))
        await ctx.invoke(self.visitorrules, member)

    @commands.command(pass_context=True, no_pm=True, aliases=['bs'])
    @commands.has_any_role(*HE_BOTCOMMANDER_ROLES)
    async def brawlstars(self, ctx, member: discord.Member, *roles):
        """Assign member with visitor and brawl-stars roles."""
        bs_roles = ["Brawl-Stars"]
        if discord.utils.get(member.roles, name="Member") is None:
            if discord.utils.get(member.roles, name="Guest") is None:
                if discord.utils.get(member.roles, name="Visitor") is None:
                    bs_roles.append("Visitor")
        channel = discord.utils.get(
            ctx.message.server.channels, name="brawl-stars")
        await self.changerole(ctx, member, *bs_roles)
        if channel is not None:
            await self.bot.say(
                "{} You can now chat in {} — enjoy!".format(
                    member.mention, channel.mention))
        if "Visitor" in bs_roles:
            await ctx.invoke(self.visitorrules, member)

        # Add additional roles if present
        if len(roles):
            await self.changerole(ctx, member, *roles)

    @commands.command(pass_context=True, no_pm=True, aliases=['vrules', 'vr'])
    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    async def visitorrules(self, ctx, *members: discord.Member):
        """DM server rules to user."""
        try:
            await ctx.invoke(self.dmusers, VISITOR_RULES, *members)
            await self.bot.say(
                "A list of rules has been sent via DM to {}.".format(
                    ", ".join([m.display_name for m in members])))
        except discord.errors.Forbidden:
            await self.bot.say(
                '{} {}'.format(
                    " ".join([m.mention for m in members]),
                    VISITOR_RULES))

    @commands.command(pass_context=True, no_pm=True)
    async def pay(self, ctx, amt, *members: discord.Member):
        """Pay amount to member(s).

        If more than one person is specificed, equally divide the credits.
        """
        bank = self.bot.get_cog('Economy').bank
        amt = int(amt)
        split_amt = int(amt / (len(members)))
        for member in members:
            if member != ctx.message.author:
                try:
                    bank.transfer_credits(
                        ctx.message.author, member, split_amt)
                except cogs.economy.NoAccount:
                    await self.bot.say(
                        "{} has no account.".format(member.display_name))
        split_msg = ""
        if len(members) > 1:
            split_msg = ' ({} credits each)'.format(split_amt)
        await self.bot.say(
            "{} has transfered {} credits{} to {}.".format(
                ctx.message.author.display_name,
                amt,
                split_msg,
                ", ".join([m.display_name for m in members])))

    @commands.command(pass_context=True, no_pm=True)
    async def skill(self, ctx, pb, *cardlevels):
        """Calculate skill level based on card levels.

        !skills 5216 c12 c12 r10 r9 e5 e4 l2 l1
        c = commons
        r = rares
        e = epics
        l = legendaries
        """
        if not pb.isdigit():
            await self.bot.say("PB (Personal Best) must be a number.")
            await send_cmd_help(ctx)
            return
        if len(cardlevels) != 8:
            await self.bot.say("You must enter exactly 8 cards.")
            await send_cmd_help(ctx)
            return
        rarities = {
            'c': 0,
            'r': 2,
            'e': 5,
            'l': 8
        }
        rarity_names = {
            'c': 'Common',
            'r': 'Rare',
            'e': 'Epic',
            'l': 'Legendary'
        }
        cards = [{'r': cl[0], 'l': int(cl[1:])} for cl in cardlevels]

        common_levels = []
        for card in cards:
            rarity = card['r']
            level = int(card['l'])
            if rarity not in rarities:
                await self.bot.say('{} is not a valid rarity.'.format(rarity))
                return
            common_level = level + rarities[rarity]
            common_levels.append(common_level)

        pb = int(pb)
        skill = pb / sum(common_levels) * 8

        out = []
        out.append('You have entered:')
        out.append(
            ', '.join(
                ['{} ({})'.format(
                    rarity_names[card['r']], card['l']) for card in cards]))
        out.append(
            'With a PB of {}, your skill level is {}.'.format(pb, skill))

        await self.bot.say('\n'.join(out))

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        """Test."""
        await self.bot.say("test")

    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    @commands.command(pass_context=True, no_pm=True)
    async def iosfix(self, ctx: Context, *members: discord.Member):
        """Quick fix to iOS bug.

        Remove all roles from members and then re-add them."""
        await self.bot.say("iOS Fix")
        await self.run_iosfix(ctx, *members)

    @commands.command(pass_context=True, no_pm=True)
    async def iosfixme(self, ctx: Context):
        """Self-Quick fix to iOS bug."""
        await self.bot.say("iOS Fix me")
        await self.run_iosfix(ctx, ctx.message.author)

    @checks.serverowner_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def say(self, ctx, *, msg):
        """Have bot say stuff. Remove command after run."""
        message = ctx.message
        await self.bot.delete_message(message)
        await self.bot.say(msg)

    @commands.command(pass_context=True, no_pm=True)
    async def crsettag(self, ctx, tag, member: discord.Member = None):
        """Set CR tags for members.

        This is the equivalent of running:
        !crclan settag [tag] [member]
        !crprofile settag [tag] [member]

        If those cogs are not loaded, it will just ignore it.
        """
        crclan = self.bot.get_cog("CRClan")
        crprofile = self.bot.get_cog("CRProfile")

        if crclan is not None:
            await ctx.invoke(crclan.crclan_settag, tag, member)
        if crprofile is not None:
            await ctx.invoke(crprofile.crprofile_settag, tag, member)

    @commands.has_any_role(*BOTCOMMANDER_ROLE)
    @commands.command(pass_context=True, no_pm=True)
    async def elder(self, ctx, *members: discord.Member):
        """Elder promotion DM + role change."""
        elder_roles = ["Elder"]
        for member in members:
            await self.changerole(ctx, member, *elder_roles)
            try:
                await ctx.invoke(self.dmusers, ELDER_MSG, member)
            except discord.errors.Forbidden:
                await self.bot.say(
                    "Unable to send DM to {}. User might have a stricter DM setting.".format(member))

    @checks.mod_or_permissions()
    @commands.command(pass_context=True, no_pm=True)
    async def reelder(self, ctx, msg):
        """Refresher for elders."""
        elder_role = "Elder"
        server = ctx.message.server
        for member in server.members:
            member_role_names = [r.name for r in member.roles]
            if "Elder" in member_role_names:
                try:
                    await ctx.invoke(self.dmusers, '{}\n{}'.format(msg, ELDER_REFRESH_MSG), member)
                except discord.errors.Forbidden:
                    await self.bot.say(
                        "Unable to send DM to {}. User might have a stricter DM setting.".format(member))

    async def run_iosfix(self, ctx: Context, *members: discord.Member):
        """Actual fix to allow members without the bot commander to run on themselves."""
        for member in members:
            roles = member.roles.copy()
            for role in roles:
                if not role.is_everyone:
                    try:
                        await self.bot.remove_roles(member, role)
                        await self.bot.add_roles(member, role)
                        await self.bot.say(
                            "Removed and re-added {} to {}.".format(
                                role, member))
                    except discord.errors.Forbidden:
                        await self.bot.say(
                            "I am not allowed to remove {} from {}.".format(
                                role, member))


def setup(bot):
    r = RACF(bot)
    bot.add_cog(r)
