import yaml
from discord.ext import commands
import rethinkdb as r

with open("config.yml") as config:
    config = yaml.safe_load(config)


description = "Just a bot that grants members exp for being in a voice channel"
bot = commands.AutoShardedBot(command_prefix="vl!", case_insensitive=True, description=description)
bot.config = config
bot.handles = {}

database = bot.config["DATABASE"]
r.set_loop_type("asyncio")
bot.conn = bot.loop.run_until_complete(r.connect(db="test"))


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


# @bot.event
# async def on_voice_state_update(member, before, after):
#     print(bot.handles)
#     guild = member.guild
#     guild_id = str(guild.id)
#     member_id = str(member.id)
#
#     # Returns on mute/deafen
#     if before.channel == after.channel or member.bot:
#         return
#
#     # Add guild to handles
#     if guild_id not in bot.handles:
#         bot.handles[guild_id] = {}
#
#     # AFK channel checks
#     if not guild.afk_channel or after.channel == guild.afk_channel:
#         if member_id in bot.handles[guild_id]:
#             bot.handles[guild_id][member_id].cancel()
#         return
#
#     # Cancel if they leave VC
#     if not after.channel:
#         if bot.handles[guild_id][member_id]:
#             bot.handles[guild_id][member_id].cancel()
#
#     handle = bot.loop.call_later(60, bot.loop.create_task, await add_exp_to_member(member))
#     bot.handles[guild_id][member_id] = handle


#################################################################################
#                               FUNCTIONS
#################################################################################

async def add_exp_to_member(member):
    guild = member.guild
    guild_id = str(guild.id)
    member_id = str(member.id)
    handle = bot.loop.call_later(1, bot.loop.create_task, add_exp_to_member(member))
    bot.handles[guild_id][member_id] = handle
    print(f"Would be updating exp for {member}")


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

    #coro = await add_exp_to_member(member)
    print("this?")
    handle = bot.loop.call_later(1, bot.loop.create_task, add_exp_to_member(member))
    bot.handles[guild_id][member_id] = handle

#################################################################################
#                               COMMANDS
#################################################################################


bot.run(bot.config["TOKEN"])
