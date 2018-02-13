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

import argparse
import itertools
import os
from collections import defaultdict
from random import choice
import asyncio

import discord
from __main__ import send_cmd_help
from cogs.utils import checks
from cogs.utils.chat_formatting import box
from cogs.utils.chat_formatting import pagify
from cogs.utils.dataIO import dataIO
from discord.ext import commands
from discord.ext.commands import Context

BOT_COMMANDER_ROLES = ["Bot Commander", "High-Elder"]
PATH = os.path.join("data", "mm")
JSON = os.path.join(PATH, "settings.json")


def grouper(n, iterable, fillvalue=None):
    """Helper function to split lists.

    Example:
    grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx
    """
    args = [iter(iterable)] * n
    return (
        [e for e in t if e is not None]
        for t in itertools.zip_longest(*args))


def nested_dict():
    """Recursively nested defaultdict."""
    return defaultdict(nested_dict)


class MemberManagement:
    """Member Management plugin for Red Discord bot."""

    def __init__(self, bot):
        """Init."""
        self.bot = bot
        self.settings = nested_dict()
        self.settings.update(dataIO.load_json(JSON))

    @commands.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions()
    async def mmset(self, ctx):
        """Member management settings."""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @mmset.group(name="role", pass_context=True, no_pm=True)
    async def mmset_role(self, ctx):
        """Role permissions.

        Specify list of roles allowed to run mm.
        This is a per-server setting.
        """
        if ctx.invoked_subcommand is None or \
                isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @mmset_role.command(name="add", pass_context=True, no_pm=True)
    async def mmset_role_add(self, ctx, role_name):
        """Add role by name"""
        server = ctx.message.server
        role = discord.utils.get(server.roles, name=role_name)
        if role is None:
            await self.bot.say("Cannot find that role on this server.")
            return
        role_settings = self.settings[server.id]["roles"]
        role_settings[role.id] = role_name
        roles = [discord.utils.get(server.roles, id=role_id) for role_id in role_settings]
        role_names = [r.name for r in roles]
        await self.bot.say("List of permitted roles updated: {}".format(', '.join(role_names)))
        dataIO.save_json(JSON, self.settings)

    @mmset.group(name="macro", pass_context=True, no_pm=True)
    async def mmset_macro(self, ctx):
        """Add / remove macro."""
        if ctx.invoked_subcommand is None or \
                isinstance(ctx.invoked_subcommand, commands.Group):
            await send_cmd_help(ctx)

    @mmset_macro.command(name="add", pass_context=True, no_pm=True)
    async def mmset_macro_add(self, ctx, name, *, args):
        """Add macro.

        name: name of the macro
        args: list of arguments to run.
        """
        server = ctx.message.server
        role_settings = self.settings[server.id]["macro"]

    def parser(self):
        """Process MM arguments."""
        # Process arguments
        parser = argparse.ArgumentParser(prog='[p]mm')
        # parser.add_argument('key')
        parser.add_argument(
            'roles',
            nargs='*',
            default='_',
            help='Include roles')
        parser.add_argument(
            '-x', '--exclude',
            nargs='+',
            help='Exclude roles')
        parser.add_argument(
            '-o', '--output',
            choices=['id', 'mention', 'mentiononly'],
            help='Output options')
        parser.add_argument(
            '-r1', '--onlyrole',
            action='store_true',
            help='Check members with exactly one role')
        parser.add_argument(
            '-e', '--everyone',
            action='store_true',
            help='Include everyone.')
        parser.add_argument(
            '-s', '--sort',
            choices=['join', 'alpha'],
            default='join',
            help='Sort options')
        parser.add_argument(
            '-r', '--result',
            choices=['embed', 'csv', 'list', 'none'],
            default='embed',
            help='How to display results')
        parser.add_argument(
            '-m', '--macro',
            help='Macro name. Create using [p]mmset')
        return parser

    @commands.command(pass_context=True)
    @commands.has_any_role(*BOT_COMMANDER_ROLES)
    async def mm(self, ctx, *args):
        """Member management by roles.

        !mm [-h] [-x EXCLUDE [EXCLUDE ...]]
             [-o {id,mention,mentiononly}] [-r1] [-e] [-s {join,alpha}]
             [-r {embed,csv,list,none}] [-m MACRO]
             [roles [roles ...]]

        Find members with roles: Member, Elder
        !mm Member Elder

        Find members with roles: Member, Elder but not: Heist, CoC
        !mm Member Elder -exclude Heist CoC
        !mm Member Elder -x Heist CoC

        Output ID
        !mm Alpha Elder --output id
        !mm Alpha Elder -o id

        Optional arguments
        --exclude, -x
            Exclude list of roles
        --output, -o {id, mention, meniononly}
            id: Append list of user ids in the result.
            mention: Append list of user mentions in the result.
            mentiononly: Append list of user mentions only.
        --sort, s {join, alpha}
            join (default): Sort by date joined.
            alpha: Sort alphabetically
        --result, -r {embed, csv, list, none}
            Result display options
            embed (default): Display as Discord Embed.
            csv: Display as comma-separated values.
            list: Display as a list.
            none: Do not display results (show only count + output specified.
        --everyone
            Include everyone. Useful for finding members without specific roles.
        """
        parser = self.parser()
        try:
            pargs = parser.parse_args(args)
        except SystemExit:
            await send_cmd_help(ctx)
            return

        option_output_mentions = (pargs.output == 'mention')
        option_output_id = (pargs.output == 'id')
        option_output_mentions_only = (pargs.output == 'mentiononly')
        option_everyone = pargs.everyone or 'everyone' in pargs.roles
        option_sort_alpha = (pargs.sort == 'alpha')
        option_csv = (pargs.result == 'csv')
        option_list = (pargs.result == 'list')
        option_none = (pargs.result == 'none')
        option_only_role = pargs.onlyrole

        server = ctx.message.server
        server_roles_names = [r.name.lower() for r in server.roles]
        plus = set([r.lower() for r in pargs.roles if r.lower() in server_roles_names])
        minus = set()
        if pargs.exclude is not None:
            minus = set([r.lower() for r in pargs.exclude if r.lower() in server_roles_names])

        # Used for output only, so it won’t mention everyone in chat
        plus_out = plus.copy()

        if option_everyone:
            plus.add('@everyone')
            plus_out.add('everyone')

        if len(plus) < 1:
            help_str = (
                'Syntax Error: You must include at '
                'least one role to display results.')
            await self.bot.say(help_str)
            await send_cmd_help(ctx)
            return

        out = ["**Member Management**"]
        out.append("Listing members who have these roles: {}".format(
                ', '.join(plus_out)))
        if len(minus):
            out.append("but not these roles: {}".format(
                ', '.join(minus)))

        await self.bot.say('\n'.join(out))

        # only output if argument is supplied
        if len(plus):
            # include roles with '+' flag
            # exclude roles with '-' flag
            out_members = set()
            for m in server.members:
                roles = set([r.name.lower() for r in m.roles])
                if option_everyone:
                    roles.add('@everyone')
                exclude = len(roles & minus)
                if not exclude and roles >= plus:
                    out_members.add(m)

            # only role
            if option_only_role:
                out_members = [m for m in out_members if len(m.roles) == 2]

            suffix = 's' if len(out_members) > 1 else ''
            await self.bot.say("**Found {} member{}.**".format(
                len(out_members), suffix))

            # sort join
            out_members = list(out_members)
            out_members.sort(key=lambda x: x.joined_at)

            # sort alpha
            if option_sort_alpha:
                out_members = list(out_members)
                out_members.sort(key=lambda x: x.display_name.lower())

            # embed output
            if not option_output_mentions_only:
                if option_none:
                    pass
                elif option_csv:
                    for page in pagify(
                            self.get_member_csv(out_members), shorten_by=50):
                        await self.bot.say(page)
                elif option_list:
                    for page in pagify(
                            self.get_member_list(out_members), shorten_by=50):
                        await self.bot.say(page)
                else:
                    for data in self.get_member_embeds(out_members, ctx.message.timestamp):
                        try:
                            await self.bot.say(embed=data)
                        except discord.HTTPException:
                            await self.bot.say(
                                "I need the `Embed links` permission "
                                "to send this")

            # Display a copy-and-pastable list
            if option_output_mentions | option_output_mentions_only:
                mention_list = [m.mention for m in out_members]
                await self.bot.say(
                    "Copy and paste these in message to mention users listed:")

                out = ' '.join(mention_list)
                for page in pagify(out, shorten_by=24):
                    await self.bot.say(box(page))

            # Display a copy-and-pastable list of ids
            if option_output_id:
                id_list = [m.id for m in out_members]
                await self.bot.say(
                    "Copy and paste these in message to mention users listed:")
                out = ' '.join(id_list)
                for page in pagify(out, shorten_by=24):
                    await self.bot.say(box(page))

    @staticmethod
    def get_member_csv(members):
        """Return members as a list."""
        names = [m.display_name for m in members]
        return ', '.join(names)

    @staticmethod
    def get_member_list(members):
        """Return members as a list."""
        out = []
        for m in members:
            out.append('+ {}'.format(m.display_name))
        return '\n'.join(out)

    @staticmethod
    def get_member_embeds(members, timestamp):
        """Discord embed of data display."""
        color = ''.join([choice('0123456789ABCDEF') for x in range(6)])
        color = int(color, 16)
        embeds = []

        # split embed output to multiples of 25
        # because embed only supports 25 max fields
        out_members_group = grouper(25, members)

        for out_members_list in out_members_group:
            data = discord.Embed(
                color=discord.Colour(value=color))
            for m in out_members_list:
                value = []
                roles = [r.name for r in m.roles if r.name != "@everyone"]
                value.append(', '.join(roles))

                name = m.display_name
                since_joined = (timestamp - m.joined_at).days

                data.add_field(
                    name=str(name),
                    value=str(
                        ''.join(value) +
                        '\n{} days ago'.format(
                            since_joined)))
            embeds.append(data)
        return embeds

    def get_server_roles(self, server, *role_names):
        """Return list of server roles object by name."""
        if server is None:
            return []
        if len(role_names):
            roles_lower = [r.lower() for r in role_names]
            roles = [
                r for r in server.roles if r.name.lower() in roles_lower
            ]
        else:
            roles = server.roles
        return roles

    @commands.command(pass_context=True, no_pm=True)
    async def listroles(self, ctx: Context, *roles):
        """List all the roles on the server."""
        server = ctx.message.server
        if server is None:
            return
        out = []
        out.append("__List of roles on {}__".format(server.name))
        roles_to_list = self.get_server_roles(server, *roles)

        out_roles = {}
        for role in roles_to_list:
            out_roles[role.id] = {'role': role, 'count': 0}
        for member in server.members:
            for role in member.roles:
                if role in roles_to_list:
                    out_roles[role.id]['count'] += 1
        for role in server.role_hierarchy:
            if role in roles_to_list:
                out.append(
                    "**{}** ({} members)".format(
                        role.name, out_roles[role.id]['count']))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True)
    async def listrolecolors(self, ctx, *roles):
        """List role colors on the server."""
        server = ctx.message.server
        role_objs = self.get_server_roles(server, *roles)
        out = []
        for role in server.role_hierarchy:
            if role in role_objs:
                rgb = role.color.to_tuple()
                out.append('**{name}**: {color_rgb}, {color_hex}'.format(
                    name=role.name,
                    color_rgb=rgb,
                    color_hex='#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
                ))
        for page in pagify("\n".join(out), shorten_by=12):
            await self.bot.say(page)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def changerole(self, ctx, member: discord.Member = None, *roles: str):
        """Change roles of a user.

        Example: !changerole SML +Delta "-Foxtrot Lead" "+Delta Lead"

        Multi-word roles must be surrounded by quotes.
        Operators are used as prefix:
        + for role addition
        - for role removal
        """
        server = ctx.message.server
        author = ctx.message.author
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

            if name.lower() in [r.lower() for r in server_role_names]:
                role_args.append({'flag': flag, 'name': name})

        plus = [r['name'].lower() for r in role_args if r['flag'] == '+']
        minus = [r['name'].lower() for r in role_args if r['flag'] == '-']
        # disallowed_roles = [r.lower() for r in DISALLOWED_ROLES]

        for role in server.roles:
            role_in_minus = role.name.lower() in minus
            role_in_plus = role.name.lower() in plus
            role_in_either = role_in_minus or role_in_plus

            if role_in_either:
                # respect role hiearchy
                if role.position >= author.top_role.position:
                    await self.bot.say(
                        "{} does not have permission to edit {}.".format(
                            author.display_name, role.name))
                else:
                    try:
                        if role_in_minus:
                            await asyncio.sleep(0)
                            await self.bot.remove_roles(member, role)
                        if role_in_plus:
                            await asyncio.sleep(0)
                            await self.bot.add_roles(member, role)
                    except discord.Forbidden:
                        await self.bot.say(
                            "{} does not have permission to edit {}’s roles.".format(
                                author.display_name, member.display_name))
                        continue
                    except discord.HTTPException:
                        if role_in_minus:
                            await self.bot.say(
                                "Failed to remove {}.").format(role.name)
                            continue
                        if role_in_plus:
                            await self.bot.say(
                                "failed to add {}.").format(role.name)
                            continue
                    else:
                        if role_in_minus:
                            await self.bot.say(
                                "Removed {} from {}".format(
                                    role.name, member.display_name))
                        if role_in_plus:
                            await self.bot.say(
                                "Added {} for {}".format(
                                    role.name, member.display_name))

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def searchmember(self, ctx, name=None):
        """Search member on server by name."""
        if name is None:
            await send_cmd_help(ctx)
            return

        server = ctx.message.server
        results = []
        for member in server.members:
            for member_name in [member.display_name, member.name]:
                if name.lower() in member_name.lower():
                    results.append(member)
                    break

        if not len(results):
            await self.bot.say("Cannot find any users with that name.")
            return

        await self.bot.say('Found {} members.'.format(len(results)))

        for member in results:
            out = [
                '---------------------',
                'Display name: {}'.format(member.display_name),
                'Username: {}'.format(str(member)),
                'Roles: {}'.format(', '.join(
                    [r.name for r in member.roles if not r.is_everyone])),
                'id: {}'.format(member.id)
            ]
            await self.bot.say('\n'.join(out))

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def addrole2role(self, ctx: Context, with_role_name, to_add_role_name):
        """Add a role to users with a specific role."""
        server = ctx.message.server
        with_role = discord.utils.get(server.roles, name=with_role_name)
        to_add_role = discord.utils.get(server.roles, name=to_add_role_name)
        if with_role is None:
            await self.bot.say("Cannot find the role **{}** on this server.".format(with_role_name))
            return
        if to_add_role is None:
            await self.bot.say("Cannot find the role **{}** on this server.".format(to_add_role_name))
            return

        server_members = [member for member in server.members]
        for member in server_members:
            if with_role in member.roles:
                if to_add_role not in member.roles:
                    try:
                        await ctx.invoke(self.changerole, member, to_add_role_name)
                    except:
                        pass

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def multiaddrole(self, ctx, role, *members: discord.Member):
        """Add a role to multiple users.

        !multiaddrole rolename User1 User2 User3
        """
        for member in members:
            await ctx.invoke(self.changerole, member, role)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def multiremoverole(self, ctx, role, *members: discord.Member):
        """Remove a role from multiple users.

        !multiremoverole rolename User1 User2 User3
        """
        role = '-{}'.format(role)
        for member in members:
            await ctx.invoke(self.changerole, member, role)

    @commands.command(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_roles=True)
    async def channelperm(self, ctx, member: discord.Member):
        """Return channels viewable by member."""
        author = ctx.message.author
        server = ctx.message.server
        if not member:
            member = author

        text_channels = [c for c in server.channels if c.type == discord.ChannelType.text]
        text_channels = sorted(text_channels, key=lambda c: c.position)
        voice_channels = [c for c in server.channels if c.type == discord.ChannelType.voice]
        voice_channels = sorted(voice_channels, key=lambda c: c.position)

        perm_tests = {
            'read_messages': 'read msg',
            'read_message_history': 'read history',
            'send_messages': 'send msg',
            'manage_messages': 'manage msg',
            'add_reactions': 'react'
        }

        out = []
        for c in text_channels:
            channel_perm = c.permissions_for(member)
            perms = [t for t in perm_tests.keys() if getattr(channel_perm, t)]
            if len(perms):
                out.append("{channel} {perms}".format(channel=c.mention, perms=', '.join(perm_tests[t] for t in perms)))

        for c in voice_channels:
            channel_perm = c.permissions_for(member)
            tests = ['connect']
            perms = [t for t in tests if getattr(channel_perm, t)]
            if len(perms):
                out.append("{channel}: {perms}".format(channel=c.name, perms=', '.join(perms)))

        for page in pagify('\n'.join(out)):
            await self.bot.say(page)


def check_folder():
    """Check folder."""
    if not os.path.exists(PATH):
        os.makedirs(PATH)


def check_file():
    """Check files."""
    if not dataIO.is_valid_json(JSON):
        dataIO.save_json(JSON, {})


def setup(bot):
    """Setup."""
    check_folder()
    check_file()
    n = MemberManagement(bot)
    bot.add_cog(n)
