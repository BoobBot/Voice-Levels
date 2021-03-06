import sys
from pprint import pprint
from random import randrange

import discord
import math
import rethinkdb as r
import yaml
from discord.ext import commands

with open("config.yml") as config:
    config = yaml.safe_load(config)

description = "Just a bot that grants members exp for being in a voice channel"
bot = commands.AutoShardedBot(command_prefix="vl!", case_insensitive=True, description=description,
                              fetch_offline_members=False)
bot.config = config
bot.handles = {}


#################################################################################
#                               EVENTS
#################################################################################


@bot.event
async def on_ready():
    print("Connected to Discord")
    print(f"Logged in as: {bot.user}")
    print(f"ID: {bot.user.id}")
    print(f"Guild count: {len(bot.guilds)}")

    # Create tables if they don't exist
    try:
        await r.table("guilds").run(bot.conn)
    except r.ReqlOpFailedError:
        await r.table_create("guilds").run(bot.conn)

    try:
        await r.table("users").run(bot.conn)
    except r.ReqlOpFailedError:
        await r.table_create("users").run(bot.conn)

    # Add users on boot
    for guild in [x for x in bot.guilds if x.afk_channel]:
        for voice_channel in [x for x in guild.voice_channels if not x == guild.afk_channel]:
            for member in [x for x in voice_channel.members if not x.bot]:
                user = await get_user(member)
                if not user:
                    await new_user(member)
                await add_to_handles(member)


@bot.event
async def on_message(ctx):
    if not bot.is_ready() or ctx.author.bot:
        return

    await bot.process_commands(ctx)


@bot.event
async def on_guild_join(guild):
    if not await r.table("guilds").get(str(guild.id)).run(bot.conn):
        await r.table("guilds").insert({
            "id": str(guild.id),
            "announce": {
                "enabled": False,
                "whisper": False,
                "message": "%USER% is now voice level: %LEVEL%!"
            },
            "rewards": {
                "keep_old": True,
                "roles": {}
            },
            "users": {}
        }, conflict="update").run(bot.conn)


#################################################################################
#                               DATABASE FUNCTIONS
#################################################################################


async def check_role(member, level):
    roles = await get_roles(member.guild.id)
    pprint(roles)
    for r in roles:
        pprint(r)
    return


async def new_guild(guild_id):
    await r.table("guilds").insert({
        "id": str(guild_id),
        "announce": {
            "enabled": False,
            "whisper": False,
            "channel_id": None,
            "message": "%USER% is now voice level: %LEVEL%!"
        },
        "rewards": {
            "keep_old": True,
            "roles": {}
        },
        "users": {}
    }, conflict="update").run(bot.conn)


async def get_roles(guild_id):
    return await r.table("guilds").get(str(guild_id)).get_field("rewards").get_field("roles").run(bot.conn)


async def get_guild(guild_id):
    return await r.table("guilds").get(str(guild_id)).run(bot.conn)


async def save_guild(guild_dict):
    await r.table('guilds').insert(guild_dict, conflict="update").run(bot.conn)


async def new_user(member):
    guild = member.guild
    guild_id = str(guild.id)
    guild = await get_guild(guild_id)
    guild['users'][str(member.id)] = {"exp": 0, "level": 0, "name": str(member)}
    await save_guild(guild)


async def save_user(user_dict, guild_id):
    guild = await get_guild(guild_id)
    user = guild['users'].get(user_dict['id'], user_dict['id'])
    guild['users'][user_dict['id']] = user_dict
    await save_guild(guild)


async def get_user(member):
    guild = await get_guild(member.guild.id)
    if not guild:
        await new_guild(str(member.guild.id))
    if str(member.id) in guild["users"]:
        return guild["users"][str(member.id)]


#################################################################################
#                               FUNCTIONS
#################################################################################

def check_voice_status(member):
    voice = member.voice
    if not voice:
        return False
    if voice.mute or voice.self_mute or voice.deaf or voice.self_deaf or voice.afk:
        return False
    return True


def get_level(xp):
    rank_constant = 0.1
    sqrt = math.sqrt(xp)
    return math.floor(rank_constant * sqrt)


def get_xp_from_level(level):
    return pow((level + 1) * 10, 2)


async def add_exp_to_member(member):
    # add back to loop
    if check_voice_status(member):
        await add_to_handles(member)
    # do stuff here
    user = await get_user(member)
    if not user:
        await new_user(member)
        user = await get_user(member)
    exp = randrange(3, 6)
    if len([x for x in member.voice.channel.members if not x.bot]) == 1:
        exp = 1
    user["exp"] += exp
    current_level = get_level(user["exp"])
    user['level'] = current_level
    if current_level > user['level']:
        user['level'] = current_level
        print(str(member) + "RANKED UP")
    user["name"] = str(member)
    user["id"] = str(member.id)
    await save_user(user, member.guild.id)
    # print(f"updating exp for {member}")
    # print(user)
    await check_role(member, current_level)


async def add_to_handles(member):
    guild = member.guild
    guild_id = str(guild.id)
    member_id = str(member.id)

    # Add guild to handles
    if guild_id not in bot.handles:
        bot.handles[guild_id] = {}

    # Remove previous handle
    if member_id in bot.handles[guild_id]:
        bot.handles[guild_id].pop(member_id)
    rng_time = 5# randrange(40, 45)
    handle = bot.loop.call_later(rng_time, bot.loop.create_task, add_exp_to_member(member))
    bot.handles[guild_id][member_id] = handle


def check_db():
    try:
        con = r.connect()
        try:
            d = r.db_create("VLLL").run(con)
            print(d)
        except r.ReqlRuntimeError:
            pass
        for t in ["guilds"]:
            try:
                t = r.db("VLLL").table_create(t).run(con)
                print(t)
            except r.ReqlOpFailedError:
                continue
        con.close()
    except r.RqlDriverError as e:
        print(f"{e}\n\rRethinkDb running?\nexiting...")
        sys.exit()


#################################################################################
#                               COMMANDS
#################################################################################


@bot.command()
async def profile(ctx, member: discord.Member = None):
    member = member if member else ctx.author
    user = await get_user(member)
    if not user:
        await new_user(member)
        user = await get_user(member)
    em = discord.Embed()
    em.set_author(icon_url=member.avatar_url, name="Profile for " + member.name)
    em.add_field(name="​",
                 value=f"User: {str(member)}"
                 f"\nLevel: {user['level']}"
                 f"\nExp: {user['exp']}/{get_xp_from_level(user['level'])}")
    em.set_footer(text="Requested by {}".format(str(ctx.message.author)))
    await ctx.send(embed=em)


@bot.command()
async def levels(ctx):
    lol = await r.table('guilds').get(str(ctx.guild.id)).get_field("users").run(bot.conn)
    # pprint(lol)
    t = []
    for k, v in lol.items():
        t.append(v)
    msg = ""
    c = 0
    for v in sorted(t, key=lambda i: i['exp'], reverse=True):
        c += 1
        if c == 1:
            msg += f":trophy:\n**User**: {v['name']}\n**Level**: {v['level']}\n**Exp**: {v['exp']}\n\n"
        else:
            msg += f"#**{c}**\n**User**: {v['name']}\n**Level**: {v['level']}\n**Exp**: {v['exp']}\n\n"
        if c == 5:
            break
    em = discord.Embed()
    em.set_author(icon_url=bot.user.avatar_url, name="Leader-board for " + bot.user.name)
    em.add_field(name="Global leader-board\n", value=msg)
    em.set_footer(text="Requested by {}".format(str(ctx.message.author)))
    await ctx.send(embed=em)


if __name__ == "__main__":
    check_db()
    r.set_loop_type("asyncio")
    bot.conn = bot.loop.run_until_complete(r.connect(db="VLLL"))
    bot.run(bot.config["TOKEN"])
