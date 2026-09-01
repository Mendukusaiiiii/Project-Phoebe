import os
import random
import asyncio
import json
import re
import datetime

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv

CONFIG_FILE = "config.json"
FILTER_FILE = "filtered_words.json"
WARNINGS_FILE = "warnings.json"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def load_filter_words():
    if not os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, "w") as f:
            json.dump({}, f, indent=4)
        return {}
    with open(FILTER_FILE, "r") as f:
        return json.load(f)


def save_filter_words(data):
    with open(FILTER_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_warnings():
    if not os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "w") as f:
            json.dump({}, f, indent=4)
        return {}
    with open(WARNINGS_FILE, "r") as f:
        return json.load(f)


def save_warnings(data):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)


config = load_config()
filter_words = load_filter_words()


load_dotenv()

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN environment variable is not set. "
    )

OWNER_ID = os.environ.get("OWNER_ID")
if not OWNER_ID:
    raise RuntimeError(
        "OWNER_ID environment variable is not set. "
    )
OWNER_ID = int(OWNER_ID)
print(f"[CONFIG] OWNER_ID loaded as: {OWNER_ID}")


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        print(f"[OWNER CHECK] interaction.user.id={interaction.user.id} vs OWNER_ID={OWNER_ID} -> {interaction.user.id == OWNER_ID}")
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

user_memory = {}
active_channels = config.setdefault("channels", {})
binary_tasks = {}

mod_roles = config.setdefault("mod_roles", {})   
admin_roles = config.setdefault("admin_roles", {}) 


def has_mod_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == OWNER_ID:
            return True
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.moderate_members:
            return True
        guild_roles = mod_roles.get(str(interaction.guild_id), [])
        if isinstance(interaction.user, discord.Member):
            return any(r.id in guild_roles for r in interaction.user.roles)
        return False
    return app_commands.check(predicate)


def has_admin_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == OWNER_ID:
            return True
        if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
            return True
        guild_roles = admin_roles.get(str(interaction.guild_id), [])
        if isinstance(interaction.user, discord.Member):
            return any(r.id in guild_roles for r in interaction.user.roles)
        return False
    return app_commands.check(predicate)


_legacy_warnings = config.pop("warnings", None)
warnings_data = load_warnings()
if _legacy_warnings:
    print("[MIGRATION] Found legacy warnings in config.json. Merging into warnings.json.")
    for guild_id, users in _legacy_warnings.items():
        guild_entry = warnings_data.setdefault(guild_id, {})
        for user_id, entries in users.items():
            guild_entry.setdefault(user_id, [])
            guild_entry[user_id].extend(entries)
    save_warnings(warnings_data)
    save_config(config)

scheduled_unbans = config.setdefault("scheduled_unbans", [])  # [{guild_id, user_id, unban_at}]

DURATION_PATTERN = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
MAX_TIMEOUT_SECONDS = 28 * 86400


def parse_duration(duration: str | None) -> int | None:
    if duration is None:
        return None
    duration = duration.strip().lower()
    if duration in ("", "perm", "permanent", "forever"):
        return None
    match = DURATION_PATTERN.match(duration)
    if not match:
        raise ValueError(f"Invalid duration format: {duration}")
    amount, unit = match.groups()
    return int(amount) * DURATION_UNITS[unit]


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "permanently"
    units = [("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)]
    parts = []
    remaining = seconds
    for name, size in units:
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value} {name}{'s' if value != 1 else ''}")
    return "for " + " ".join(parts) if parts else "briefly"


def _remove_scheduled_unban(guild_id: int, user_id: int):
    scheduled_unbans[:] = [
        e for e in scheduled_unbans
        if not (e["guild_id"] == guild_id and e["user_id"] == user_id)
    ]
    save_config(config)


async def issue_warning(guild: discord.Guild, member: discord.Member, reason: str, moderator_id: int) -> tuple[int, bool]:
    guild_id = str(guild.id)
    user_id = str(member.id)

    warnings_data.setdefault(guild_id, {}).setdefault(user_id, [])
    warnings_data[guild_id][user_id].append({
        "reason": reason,
        "moderator": str(moderator_id),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
    })
    save_warnings(warnings_data)

    warn_count = len(warnings_data[guild_id][user_id])

    dm_sent = True
    try:
        await member.send(
            f"You have been warned in **{guild.name}**.\n\n"
            f"**Reason:** {reason}\n"
            f"This is the #{warn_count} warning for you in the server."
        )
    except discord.Forbidden:
        dm_sent = False

    return warn_count, dm_sent


_banned_word_pattern_cache = {}


def get_banned_word_pattern(guild_id: str):
    words = filter_words.get(guild_id, [])
    if not words:
        return None
    cached = _banned_word_pattern_cache.get(guild_id)
    if cached is None or cached[0] != words:
        escaped = [re.escape(w) for w in words]
        pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)
        _banned_word_pattern_cache[guild_id] = (list(words), pattern)
        return pattern
    return cached[1]



SPAM_REPEAT_THRESHOLD = 5
SPAM_WINDOW_SECONDS = 60
spam_tracker = {}


def check_spam(message: discord.Message) -> bool:
    content = message.content.strip().lower()
    if not content:
        return False

    key = (message.guild.id, message.channel.id, message.author.id)
    now = datetime.datetime.now(datetime.UTC)
    entry = spam_tracker.get(key)

    if entry and entry["content"] == content and (now - entry["last_time"]).total_seconds() <= SPAM_WINDOW_SECONDS:
        entry["count"] += 1
        entry["last_time"] = now
    else:
        entry = {"content": content, "count": 1, "last_time": now}

    spam_tracker[key] = entry

    if entry["count"] >= SPAM_REPEAT_THRESHOLD:
        entry["count"] = 0
        return True
    return False


async def unban_user(guild_id: int, user_id: int):
    guild = bot.get_guild(guild_id)
    if guild is not None:
        try:
            await guild.unban(discord.Object(id=user_id), reason="Temporary ban duration expired")
            print(f"[UNBAN] Unbanned user {user_id} from guild {guild_id}")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print(f"[UNBAN ERROR] Missing permission to unban {user_id} in guild {guild_id}")
    _remove_scheduled_unban(guild_id, user_id)


async def schedule_unban(guild_id: int, user_id: int, delay_seconds: float):
    await asyncio.sleep(delay_seconds)
    await unban_user(guild_id, user_id)

#
_legacy_channel_id = config.pop("channel_id", None)
if _legacy_channel_id is not None:
    print(f"[MIGRATION] Found legacy channel_id={_legacy_channel_id}. "
          "Please re-run /setup in the server to register it under 'channels'.")
    save_config(config)


@bot.event
async def on_ready():
    print(f"Hey hey Cosmos!")
    print(f"{bot.user} is now online!")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="YOU"),
        status=discord.Status.idle
    )

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"[SYNC ERROR] {e}")

    now = datetime.datetime.now(datetime.UTC)
    for entry in list(scheduled_unbans):
        unban_at = datetime.datetime.fromisoformat(entry["unban_at"])
        if unban_at.tzinfo is None:

            unban_at = unban_at.replace(tzinfo=datetime.UTC)
        delay = (unban_at - now).total_seconds()
        if delay <= 0:
            asyncio.create_task(unban_user(entry["guild_id"], entry["user_id"]))
        else:
            asyncio.create_task(schedule_unban(entry["guild_id"], entry["user_id"], delay))


@bot.tree.command(name="setup", description="Set the channel as the bot's active channel")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def setup(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    active_channels[guild_id] = interaction.channel.id
    save_config(config)
    await interaction.response.send_message(f"Bot is now active in this server: <#{interaction.channel.id}>")


@bot.tree.command(name="unsetup", description="Remove the configured active channel")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def unsetup(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    if guild_id in active_channels:
        removed_channel = active_channels.pop(guild_id)
        save_config(config)
        await interaction.response.send_message(f"Channel setup removed for this server: <#{removed_channel}>")
    else:
        await interaction.response.send_message("No setup channel found for this server.")



@bot.tree.command(name="setmodrole", description="Designate a role as a moderator")
@app_commands.describe(role="The role to grant moderator command access")
@app_commands.default_permissions(administrator=True)
@has_admin_role()
async def setmodrole(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild_id)
    roles = mod_roles.setdefault(guild_id, [])
    if role.id in roles:
        await interaction.response.send_message(f"{role.mention} is already a mod role.", ephemeral=True)
        return
    roles.append(role.id)
    save_config(config)
    await interaction.response.send_message(f"{role.mention} can now use moderator commands.", ephemeral=True)


@bot.tree.command(name="removemodrole", description="Remove a role's moderator command access")
@app_commands.describe(role="The role to remove")
@app_commands.default_permissions(administrator=True)
@has_admin_role()
async def removemodrole(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild_id)
    roles = mod_roles.setdefault(guild_id, [])
    if role.id not in roles:
        await interaction.response.send_message(f"{role.mention} isn't a mod role.", ephemeral=True)
        return
    roles.remove(role.id)
    save_config(config)
    await interaction.response.send_message(f"Removed moderator access from {role.mention}.", ephemeral=True)


@bot.tree.command(name="modroles", description="List the server's configured moderator roles")
@app_commands.default_permissions(administrator=True)
@has_admin_role()
async def modroles(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    roles = mod_roles.get(guild_id, [])
    if not roles:
        await interaction.response.send_message("No mod roles are configured for this server.", ephemeral=True)
        return
    listing = ", ".join(f"<@&{r}>" for r in roles)
    await interaction.response.send_message(f"**Mod roles:** {listing}", ephemeral=True)


@bot.tree.command(name="setadminrole", description="Designate a role as an admin role")
@app_commands.describe(role="The role to grant admin command access")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def setadminrole(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild_id)
    roles = admin_roles.setdefault(guild_id, [])
    if role.id in roles:
        await interaction.response.send_message(f"{role.mention} is already an admin role.", ephemeral=True)
        return
    roles.append(role.id)
    save_config(config)
    await interaction.response.send_message(f"{role.mention} can now use admin commands.", ephemeral=True)


@bot.tree.command(name="removeadminrole", description="Remove a role's admin command access")
@app_commands.describe(role="The role to remove")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def removeadminrole(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild_id)
    roles = admin_roles.setdefault(guild_id, [])
    if role.id not in roles:
        await interaction.response.send_message(f"{role.mention} isn't an admin role.", ephemeral=True)
        return
    roles.remove(role.id)
    save_config(config)
    await interaction.response.send_message(f"Removed admin access from {role.mention}.", ephemeral=True)


@bot.tree.command(name="adminroles", description="List the server's configured admin roles")
@app_commands.default_permissions(administrator=True)
@has_admin_role()
async def adminroles(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    roles = admin_roles.get(guild_id, [])
    if not roles:
        await interaction.response.send_message("No admin roles are configured for this server.", ephemeral=True)
        return
    listing = ", ".join(f"<@&{r}>" for r in roles)
    await interaction.response.send_message(f"**Admin roles:** {listing}", ephemeral=True)


@bot.tree.command(name="warn", description="Warns a user.")
@app_commands.describe(user="The user to warn", reason="Reason for the warning")
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    warn_count, dm_sent = await issue_warning(interaction.guild, user, reason, interaction.user.id)

    confirmation = f"⚠️ {user.mention} has been warned. (Total warnings: {warn_count})"
    if not dm_sent:
        confirmation += "\n*Could not DM the user, they may have DMs disabled.*"

    await interaction.response.send_message(confirmation, ephemeral=True)


@bot.tree.command(name="mute", description="Set a timeout on a user for a set duration")
@app_commands.describe(
    user="The user to mute",
    reason="Reason for the mute",
    duration="Duration, e.g. 10m, 2h, 3d (max 28d)"
)
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def mute(interaction: discord.Interaction, user: discord.Member, reason: str, duration: str):
    try:
        duration_seconds = parse_duration(duration)
    except ValueError:
        await interaction.response.send_message(
            "Invalid duration format. Use something like `10m`, `2h`, `3d` (max 28d).",
            ephemeral=True
        )
        return

    if duration_seconds is None:
        await interaction.response.send_message(
            "Mutes can't be permanent - Discord timeouts are capped at 28 days. Please provide a duration.",
            ephemeral=True
        )
        return

    if duration_seconds > MAX_TIMEOUT_SECONDS:
        await interaction.response.send_message(
            "That duration is too long - Discord timeouts are capped at 28 days.",
            ephemeral=True
        )
        return

    until = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)
    duration_text = format_duration(duration_seconds)

    dm_sent = True
    try:
        await user.send(
            f"You have been muted in **{interaction.guild.name}**.\n\n"
            f"**Reason:** {reason}\n"
            f"**Duration:** {duration_text}"
        )
    except discord.Forbidden:
        dm_sent = False

    try:
        await user.timeout(until, reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to mute that user.", ephemeral=True
        )
        return

    confirmation = f"🔇 {user.mention} has been muted {duration_text}.\n**Reason:** {reason}"
    if not dm_sent:
        confirmation += "\n*Could not DM the user before the mute.*"

    await interaction.response.send_message(confirmation, ephemeral=True)


@bot.tree.command(name="ban", description="Ban a user, optionally for a set duration")
@app_commands.describe(
    user="The user to ban",
    reason="Reason for the ban",
    duration="Optional: e.g. 10m, 2h, 3d, 1w. Leave blank for a permanent ban."
)
@app_commands.default_permissions(ban_members=True)
@has_mod_role()
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str, duration: str = None):
    try:
        duration_seconds = parse_duration(duration)
    except ValueError:
        await interaction.response.send_message(
            "Invalid duration format. Use something like `10m`, `2h`, `3d`, `1w`, or leave it blank for a permanent ban.",
            ephemeral=True
        )
        return

    guild = interaction.guild
    duration_text = format_duration(duration_seconds)

    dm_sent = True
    try:
        await user.send(
            f"You have been banned from **{guild.name}**.\n\n"
            f"**Reason:** {reason}\n"
            f"**Duration:** {duration_text}"
        )
    except discord.Forbidden:
        dm_sent = False

    try:
        await guild.ban(user, reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to ban that user.", ephemeral=True
        )
        return

    if duration_seconds:
        unban_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=duration_seconds)
        scheduled_unbans.append({
            "guild_id": guild.id,
            "user_id": user.id,
            "unban_at": unban_at.isoformat()
        })
        save_config(config)
        asyncio.create_task(schedule_unban(guild.id, user.id, duration_seconds))

    confirmation = f"🔨 {user.mention} has been banned {duration_text}.\n**Reason:** {reason}"
    if not dm_sent:
        confirmation += "\n*Could not DM the user before the ban.*"

    await interaction.response.send_message(confirmation, ephemeral=True)


@bot.tree.command(name="filteradd", description="Adds a word or phrase to the automod filter")
@app_commands.describe(word="The word or phrase to filter")
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def filteradd(interaction: discord.Interaction, word: str):
    guild_id = str(interaction.guild_id)
    word = word.strip().lower()
    words = filter_words.setdefault(guild_id, [])
    if word in words:
        await interaction.response.send_message(f"`{word}` is already in the filter list.", ephemeral=True)
        return
    words.append(word)
    save_filter_words(filter_words)
    await interaction.response.send_message(f"Added `{word}` to the automod filter.", ephemeral=True)


@bot.tree.command(name="filterremove", description="Remove a word or phrase from the automod filter for this server")
@app_commands.describe(word="The word or phrase to remove")
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def filterremove(interaction: discord.Interaction, word: str):
    guild_id = str(interaction.guild_id)
    word = word.strip().lower()
    words = filter_words.setdefault(guild_id, [])
    if word not in words:
        await interaction.response.send_message(f"`{word}` isn't in the filter list.", ephemeral=True)
        return
    words.remove(word)
    save_filter_words(filter_words)
    await interaction.response.send_message(f"Removed `{word}` from the automod filter.", ephemeral=True)


@bot.tree.command(name="filterlist", description="View the server's automod filter list")
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def filterlist(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    words = filter_words.get(guild_id, [])
    if not words:
        await interaction.response.send_message("No filtered words are set for this server.", ephemeral=True)
        return
    listing = ", ".join(f"`{w}`" for w in words)
    await interaction.response.send_message(f"**Filtered words:** {listing}", ephemeral=True)


@bot.tree.command(name="warnings", description="View a user's warning history")
@app_commands.describe(user="The user to check")
@app_commands.default_permissions(moderate_members=True)
@has_mod_role()
async def warnings_cmd(interaction: discord.Interaction, user: discord.Member):
    guild_id = str(interaction.guild_id)
    user_id = str(user.id)

    entries = warnings_data.get(guild_id, {}).get(user_id, [])

    if not entries:
        await interaction.response.send_message(
            f"{user.mention} has no warnings on record.", ephemeral=True
        )
        return

    lines = [f"**Warnings for {user.mention} ({len(entries)} total):**\n"]
    for i, entry in enumerate(entries, start=1):
        moderator = f"<@{entry['moderator']}>"
        timestamp = entry["timestamp"].split("T")[0]  # just the date
        lines.append(f"**#{i}** — {timestamp} by {moderator}\n> {entry['reason']}")

    message_text = "\n".join(lines)

    if len(message_text) > 1900:
        message_text = message_text[:1900] + "\n... (truncated)"

    await interaction.response.send_message(message_text, ephemeral=True)


@bot.tree.command(name="help", description="Help me!")
async def custom_help(interaction: discord.Interaction):
    help_text = (
        "Bot CMDS:\n"
        "\n"
        "`/help`        - show help message\n"
        "`/clearmemory` - clears AI memory\n"

    )
    await interaction.response.send_message(help_text)


@bot.tree.command(name="say", description="Make the bot say something")
@app_commands.describe(message="What the bot should say")
@app_commands.default_permissions(administrator=True)
@has_admin_role()
async def say(interaction: discord.Interaction, message: str):
    await interaction.channel.send(message)
    await interaction.response.send_message("Sent.", ephemeral=True)


@bot.tree.command(name="clearmemory", description="Clear your conversation memory")
async def clear_memory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in user_memory:
        del user_memory[user_id]
    await interaction.response.send_message("Your memory has been cleared!")


@bot.tree.command(name="test", description="Starts spamming random binaries on repeat")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def binary(interaction: discord.Interaction):
    channel_id = interaction.channel.id

    if channel_id in binary_tasks and binary_tasks[channel_id] is not None:
        await interaction.response.send_message("Already running in this channel.", ephemeral=True)
        return

    channel = interaction.channel
    await interaction.response.send_message("Starting binary spam.", ephemeral=True)

    async def spam_binary():
        try:
            while True:
                binary_str = ''.join(random.choice(['0', '1']) for _ in range(random.randint(8, 32)))
                await channel.send(binary_str)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(spam_binary())
    binary_tasks[channel_id] = task


@bot.tree.command(name="stoptest", description="Stops the binary spam")
@app_commands.default_permissions(administrator=True)
@is_owner()
async def stop_binary(interaction: discord.Interaction):
    channel_id = interaction.channel.id

    if channel_id not in binary_tasks or binary_tasks[channel_id] is None:
        await interaction.response.send_message("Nothing is running in this channel.", ephemeral=True)
        return

    binary_tasks[channel_id].cancel()
    binary_tasks[channel_id] = None
    await interaction.response.send_message("Stopped.", ephemeral=True)


@setup.error
@unsetup.error
@binary.error
@stop_binary.error
@setmodrole.error
@removemodrole.error
@modroles.error
@setadminrole.error
@removeadminrole.error
@adminroles.error
@warn.error
@mute.error
@ban.error
@filteradd.error
@filterremove.error
@filterlist.error
@warnings_cmd.error
@say.error
async def owner_only_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
    else:
        raise error


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.guild is None:
        return

    if not message.author.guild_permissions.moderate_members:
        guild_id = str(message.guild.id)

        if check_spam(message):
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

            reason = f"Automatically flagged for spamming {SPAM_REPEAT_THRESHOLD} times in a row"
            warn_count, dm_sent = await issue_warning(message.guild, message.author, reason, bot.user.id)

            notice = f"{message.author.mention} was warned for spamming. (Warning #{warn_count})"
            if not dm_sent:
                notice += " *(Could not DM the user.)*"
            try:
                await message.channel.send(notice, delete_after=10)
            except discord.Forbidden:
                pass
            return

        # Banned word filter
        pattern = get_banned_word_pattern(guild_id)
        if pattern is not None:
            match = pattern.search(message.content)
            if match:
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass

                reason = f"Automatically flagged for inappropriate language (matched: \"{match.group(0)}\")"
                warn_count, dm_sent = await issue_warning(message.guild, message.author, reason, bot.user.id)

                notice = f"{message.author.mention}'s message was removed for inappropriate language. (Warning #{warn_count})"
                if not dm_sent:
                    notice += " *(Could not DM the user.)*"
                try:
                    await message.channel.send(notice, delete_after=10)
                except discord.Forbidden:
                    pass
                return

    guild_id = str(message.guild.id)
    active_channel_id = active_channels.get(guild_id)

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


if __name__ == "__main__":
    bot.run(TOKEN)
