import discord
import rethinkdb as r
from discord.ext import commands

from utils.checks import checks
from utils.utils.formats import pagify


class SelfRoles:
    def __init__(self, bot):
        self.bot = bot

    async def get_selfrole(self):
        try:
            return await r.table('selfroles').get(1).get_field('roles').run(self.bot.conn)
        except r.errors.ReqlNonExistenceError:
            return None

    @commands.group(aliases=['sr'])
    async def selfroles(self, ctx):
        """Self Role Management"""
        if not ctx.invoked_subcommand:
            return await ctx.send_cmd_help(ctx)

    @checks.admin_or_permissions(manage_roles=True)
    @selfroles.command(name="add")
    async def _add(self, ctx, *, role: str):
        """Add a role"""
        for ro in ctx.guild.roles:
            if isinstance(role, str):
                if ro.name.lower() == role.lower():
                    role = ro
            else:
                continue

        if isinstance(role, str):
            return await ctx.send(f"We couldn't find a role matching {role}!")
        guild = ctx.guild
        channel = ctx.channel
        roles = await r.table('selfroles').get(1).run(self.bot.conn)
        sr = ""
        for x in roles["roles"]:
            sr = discord.utils.get(guild.roles, id=int(x))
        if role == sr:
            return await ctx.send(f"This role is already self assignable!")
        if not channel.permissions_for(guild.me).manage_roles:
            return await ctx.send(f"I need the permission manage roles!")
        rlist = await self.get_selfrole()
        rlist.append(str(role.id))
        await r.table('selfroles').filter(r.row['id'] == 1).update({"roles": rlist}).run(self.bot.conn)
        await ctx.send(f'I have added **{role.name}** to the self assignable roles!')

    @checks.admin_or_permissions(manage_roles=True)
    @selfroles.command(name="remove")
    async def _del(self, ctx, *, role: str):
        """Remove a role"""
        for ro in ctx.guild.roles:
            if isinstance(role, str):
                if ro.name.lower() == role.lower():
                    role = ro
            else:
                continue

        if isinstance(role, str):
            return await ctx.send(f"We couldn't find a role matching {role}!")
        guild = ctx.guild
        channel = ctx.channel
        roles = await r.table('selfroles').get(1).run(self.bot.conn)
        counter = 0
        for x in roles["roles"]:
            sr = discord.utils.get(guild.roles, id=int(x))
            if sr is None:
                rlist = await self.get_selfrole()
                rlist.remove(str(x))
                await r.table('selfroles').filter(r.row['id'] == 1).update({"roles": rlist}).run(self.bot.conn)
            if role == sr:
                counter += 1
        if counter < 1:
            return await ctx.send("This role isn't self assignable!")
        if not channel.permissions_for(guild.me).manage_roles:
            await ctx.send("I need the permission manage roles!")
            return
        rlist = await self.get_selfrole()
        rlist.remove(str(role.id))
        await r.table('selfroles').filter(r.row['id'] == 1).update({"roles": rlist}).run(self.bot.conn)
        await ctx.send(f"I have removed **{role.name}** from the self assignable roles!")

    @commands.command()
    async def rank(self, ctx, *, role: str):
        """Get, or remove, a self role."""
        for ro in ctx.guild.roles:
            if isinstance(role, str):
                if ro.name.lower() == role.lower():
                    role = ro
            else:
                continue

        if isinstance(role, str):
            return await ctx.send(f"We couldn't find a role matching {role}!")
        guild = ctx.guild
        author = ctx.author
        roles = await r.table('selfroles').get(1).run(self.bot.conn)
        if "roles" in roles:
            for x in roles["roles"]:
                sr = guild.get_role(int(x))
                if sr == role:
                    if role in author.roles:
                        await author.remove_roles(role)
                        await ctx.send(f"I have taken {role.name} from {author.name}!")
                    else:
                        await author.add_roles(role)
                        await ctx.send(f"I have given {role.name} to {author.name}!")

    @selfroles.command(name="list")
    async def _rlist(self, ctx):
        """Shows current self assignable roles"""
        guild = ctx.guild
        msg = ""
        roles = await r.table('selfroles').get(1).run(self.bot.conn)
        for x in roles["roles"]:
            sr = guild.get_role(int(x))
            if sr is None:
                rlist = await self.get_selfrole()
                rlist.remove(str(x))
                await r.table('selfroles').filter(r.row['id'] == 1).update({"roles": rlist}).run(self.bot.conn)
            mbrs = len(sr.members)
            msg += f'{sr.mention} `{mbrs} Members`\n'

        paged = pagify(f"{msg}", delims=",", page_length=1000)
        counter = 0
        for page in paged:
            counter += 1
            em = discord.Embed(color=self.bot.color)
            em.set_author(name=guild.name, icon_url=guild.icon_url)
            em.set_thumbnail(url=self.bot.user.avatar_url)
            em.set_footer(text="To add/remove a role to yourself: =rank {rolename}")
            em.add_field(name=f'Page {counter}', value=f'{page}')
            await ctx.send(embed=em)


def setup(bot):
    bot.add_cog(SelfRoles(bot))
