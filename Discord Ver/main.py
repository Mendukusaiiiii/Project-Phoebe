import discord
from discord.ext import commands
import json
import asyncio
import aiohttp

CONFIG_FILE = "config.json"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
user_memory = {}
active_channel_id = config.get("channel_id")
binary_tasks = {}  

@bot.event
async def on_ready():
    print(f"Hey hey Cosmos!")
    print(f"{bot.user} is now online!")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="YOU"),
        status=discord.Status.idle
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    global active_channel_id
    active_channel_id = ctx.channel.id
    config["channel_id"] = active_channel_id
    save_config(config)
    await ctx.send(f"Bot is now active: <#{active_channel_id}>")
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="unsetup")
@commands.has_permissions(administrator=True)
async def unsetup(ctx):
    global active_channel_id
    if "channel_id" in config:
        removed_channel = config.pop("channel_id", None)
        save_config(config)
        active_channel_id = None
        await ctx.send(f"Channel setup removed: <#{removed_channel}>")
        try:
            await ctx.message.delete()
        except Exception:
            pass
    else:
        await ctx.send("No setup channel found to remove.")
        try:
            await ctx.message.delete()
        except Exception:
            pass

@bot.command(name="help")
async def custom_help(ctx):
    help_text = "Al1ce CMDS:\n" \
                "\n" \
                "`/help` - show help message\n" \
                "`/setup` - setup bot in a channel\n" \
                "`/unsetup` - remove setup channel\n" \
                "`/clearmemory` - clears memory"
               
    await ctx.send(help_text)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="say")
async def say(ctx, *, message: str):
    await ctx.send(message)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="clearmemory")
async def clear_memory(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        del user_memory[user_id]
    await ctx.send("Your memory has been cleared!")
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="test")
async def binary(ctx):
    
    import random
    channel_id = ctx.channel.id
    
    if channel_id in binary_tasks and binary_tasks[channel_id] is not None:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return
    
    async def spam_binary():
        try:
            while True:
                binary_str = ''.join(random.choice(['0', '1']) for _ in range(random.randint(8, 32)))
                await ctx.send(binary_str)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    task = asyncio.create_task(spam_binary())
    binary_tasks[channel_id] = task
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.command(name="stoptest")
async def stop_binary(ctx):
    channel_id = ctx.channel.id
    
    if channel_id not in binary_tasks or binary_tasks[channel_id] is None:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        return
    
    binary_tasks[channel_id].cancel()
    binary_tasks[channel_id] = None
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.event
async def on_message(message):
    global active_channel_id

    if message.author.bot:
        return

    await bot.process_commands(message)

    
    if active_channel_id is None or message.channel.id != active_channel_id:
        return

    if message.content.startswith("/"):
        return

    await message.channel.typing()
    user_id = str(message.author.id)
    user_memory.setdefault(user_id, [])
    user_memory[user_id].append({"role": "user", "content": message.content})

    messages = [{"role": "system", "content": config["system_context"]}] + user_memory[user_id]

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": config["model"],
                "messages": messages
            }
            async with session.post(f"{config['api_base']}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_detail = await resp.text()
                    print(f"[API ERROR] {resp.status}: {error_detail}")
                    await message.reply(config.get("error_message", "API Error, try again later."))
                    return
                response = await resp.json()
                reply = response["choices"][0]["message"]["content"]
                user_memory[user_id].append({"role": "assistant", "content": reply})
                await message.reply(reply)
    except Exception as e:
        await message.reply(config.get("error_message", "Internal error occurred."))
        print(f"[ERROR] {e}")

bot.run("") #Replace with your own bot token