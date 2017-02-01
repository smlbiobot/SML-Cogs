import discord
from discord.ext import commands
from .utils import checks
from random import choice


class SML:
    """Cog / Plugin for RedDiscord-Bot"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def chansend(self, channel : str, message : str):
        """Send message to channel"""
        channel_obj = [c for c in self.bot.get_all_channels() if channel == c.name]
        if channel_obj is not None:
            channel_obj = channel_obj[0]

        await self.bot.send_typing(channel_obj)
        await self.bot.send_message(channel_obj, message)

    @commands.command(pass_context=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def memberlist(self, ctx, member: discord.Member = None):
        """List all members with roles assigned"""

        server = ctx.message.server

        for m in server.members:
            member_roles = [r.name for r in m.roles if r.name !="@everyone"]
            r_str = ', '.join(member_roles)
            m_name = m.nick if m.nick else m.name
            await self.bot.say("**{}** has these roles: {}".format(m_name, r_str))

    @commands.command(pass_context=True)
    async def mm(self, ctx, *args):
        """
        Member management
        Get a list of users that satisfy these roles
        e.g.
        !mm S M -L
        !mm +S +M -L
        fetches a list of users who has the roles S, M but not the role L.
        S is the same as +S. + is an optional prefix for includes.

        """

        server = ctx.message.server

        server_roles_names = [r.name for r in server.roles]

        # get list of arguments which are valid server role names
        # as dictionary {flag, name}

        out=["**Member Management**"]

        role_args = []
        flags = ['+','-']
        for arg in args:
            has_flag = arg[0] in flags
            flag = arg[0] if has_flag else '+'
            name = arg[1:] if has_flag else arg

            if name in server_roles_names:
                role_args.append({'flag': flag, 'name': name})

        # debug: flag / name from arguments
        plus  = set([r['name'] for r in role_args if r['flag'] == '+'])
        minus = set([r['name'] for r in role_args if r['flag'] == '-'])

        if len(plus) < 1:
            out.append("You must include at least one role to display.")
            out.append("Usage: !mm [+include_roles] [-exclude_roles]")
            out.append("e.g. !mm +A +B -C")
            out.append("will output members who have both role A and B but not C")
        else:
            out.append(f"Listing members who have these roles: {', '.join(plus)}")
        if len(minus) != 0:
            out.append(f"but not these roles: {', '.join(minus)}")

        await self.bot.say('\n'.join(out))

        # only output if argument is supplied
        if len(plus):
            # include roles with '+' flag
            # exclude roles with '-' flag
            out_members = set()
            for m in server.members:
                roles = set([r.name for r in m.roles])
                exclude = len(roles & minus)
                if not exclude and roles >= plus:
                    out_members.add(m)

            

            # embed output
            # passed = (ctx.message.timestamp - server.created_at).days
            # created_at = ("Since {}. That's over {} days ago!"
            #               "".format(server.created_at.strftime("%d %b %Y %H:%M"),
            #                         passed))
            colour = ''.join([choice('0123456789ABCDEF') for x in range(6)])
            colour = int(colour, 16)

            data = discord.Embed(
                description='List',
                colour=discord.Colour(value=colour))
            
            for m in out_members:
                value = []
                roles = [r.name for r in m.roles if r.name != "@everyone"]
                value.append(f"Roles: {', '.join(roles)}")

                data.add_field(name=str(m.name), value=str(' | '.join(value)))
            
            try:
                await self.bot.say(embed=data)
            except discord.HTTPException:
                await self.bot.say("I need the `Embed links` permission "
                                   "to send this")


def setup(bot):
    bot.add_cog(SML(bot))
