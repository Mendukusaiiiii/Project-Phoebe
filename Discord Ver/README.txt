Discord AI Bot

ABOUT:
A Python-based Discord bot that integrates with an AI API to provide AI-generated responses.
Includes a moderation system with warnings, mutes, temporary and permanent bans, spam detection, and a banned word filter.

FEATURES:

User memory

Channel lock and unlock

Native Discord slash commands (appear in the "/" picker with descriptions)

Moderation commands: /warn, /mute, /ban (with optional duration and auto-unban), /warnings (view history)

Automod: spam detection for repeated messages, configurable banned word filter (/filteradd, /filterremove, /filterlist)

Role-based permissions: assign mod/admin bot-command access to roles without needing Discord’s native Administrator or Moderate Members permission (/setmodrole, /removemodrole, /modroles, /setadminrole, /removeadminrole, /adminroles)

Owner-only utility commands: /setup, /unsetup, /test, /stoptest

/say command to make the bot post a message

PROJECT FILES:

bot.py - Main Python script that runs the bot

config.json - Configuration file (API key, model, settings, active channels, mod/admin roles, scheduled unbans)

filtered_words.json - Per-server banned word list (auto-created if missing)

warnings.json - Per-server, per-user warning history (auto-created if missing)

requirements.txt - Python dependencies for Katabump or local hosting

.env - Stores Discord bot token and owner ID (not committed or shared)

SETUP INSTRUCTIONS:

Step 1: Edit config.json
Update the following fields:

api_key: Replace with your OpenRouter API key

system_context: Customize the assistant personality

error_message: Change the fallback message shown on error

Note: channels, mod_roles, admin_roles, and scheduled_unbans are managed automatically by the bot.

Step 2: Create .env
Do not put your token directly in bot.py. Create a file named ".env" in the same folder as bot.py and add:
DISCORD_BOT_TOKEN=<YOUR_BOT_TOKEN>
OWNER_ID=<YOUR_DISCORD_USER_ID>

OWNER_ID is required for owner-only commands and full mod/admin access.
Ensure requirements.txt includes python-dotenv.

Step 3: Sync slash commands
Commands register automatically on startup (bot.tree.sync runs in on_ready).
Global sync may take up to an hour; for faster testing, sync to a single server.

Step 4: Permissions
Moderation commands are available to:

The bot owner (OWNER_ID)

Users with native Discord permissions (Administrator or Moderate Members)

Roles registered via /setmodrole or /setadminrole

MODERATION NOTES:

/warn and /mute DM the user automatically (fallback if DMs are closed)

/mute uses Discord’s native timeout, maximum 28 days

/ban supports optional durations (10m, 2h, 3d, 1w). Omit for permanent ban. Temporary bans are tracked in config.json and auto-unban even after restarts

Spam detection: 5 identical messages within 60 seconds are auto-deleted and issue a warning. Users with Moderate Members permission are exempt

Banned word filter: matching messages are auto-deleted and issue a warning. Users with Moderate Members permission are exempt

STATUS (inside on_ready in bot.py):
status = discord.Status.idle   # Options: online, idle, dnd, invisible
activity = discord.Activity(type=discord.ActivityType.watching, name="<YOUR_STATUS_MESSAGE>")

Dock Image Needed:
Python 3.14
