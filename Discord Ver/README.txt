Phoebe - Discord AI Bot

ABOUT:
A Python Discord bot that responds with AI-generated messages in a configured
server channel. It also includes moderation and automod tools, per-user
encrypted conversation memory, and an Amber (𝓐) economy with a shop,
inventories, and collectible roles.

FEATURES:

- AI chat powered by an OpenAI-compatible chat completions API.
- Replies to messages in the channel configured with /setup.
- Per-user conversation memory, encrypted at rest. Use /clearmemory to erase
  your conversation history.
- Native Discord slash commands, synced automatically when the bot starts.
- Moderation: /warn, /mute (Discord timeout, up to 28 days), /ban (temporary
  or permanent, with automatic unban), and /warnings.
- Automod: repeated-message spam detection and a per-server word/phrase filter
  managed with /filteradd, /filterremove, and /filterlist.
- Role-based bot command access managed with /setmodrole, /removemodrole,
  /modroles, /setadminrole, /removeadminrole, and /adminroles.
- Amber economy: earn Amber by chatting, claim it with /daily, check balances,
  transfer Amber, and spend it in /shop. Use /inventory to view owned items.
- Shop supports limited-stock items and custom/title roles. Sold-out limited
  items are automatically moved to the archive and are no longer purchasable.
- /say posts a message as the bot. The owner-only /test and /stoptest commands
  start and stop a repeating binary-message test in the current channel.

PROJECT FILES:

- main.py - Main bot script; run this file to start the bot.
- components/earn.py - Amber chat rewards and /daily command.
- components/shop.py - Shop, inventory, role purchases, and sold-out item
  archiving.
- requirements.txt - Python package dependencies.
- .env - Local environment variables for the Discord token, owner ID, and
  memory encryption key. Keep this file private and do not commit real values.
- data/config.json - AI API settings and bot/server settings.
- data/filtered_words.json - Per-server banned words and phrases.
- data/warnings.json - Per-server, per-user warning histories.
- data/memory.json - Encrypted per-user AI conversation memory.
- data/balances.json - User Amber balances.
- data/cooldowns.json - Daily claim cooldowns and streaks.
- data/shop_items.json - Active shop catalog, including limited-item stock.
- data/archived_items.json - Sold-out limited items; managed by the bot.
- data/inventory.json - User-owned shop items, role selections, and stock counts.

SETUP:

1. Install Python and dependencies

   From this folder, install the packages:

       python -m pip install -r requirements.txt

2. Configure data/config.json

   Set the following values:

   - api_key - Your AI provider API key.
   - api_base - The provider's OpenAI-compatible API base URL. The bot appends
     /chat/completions.
   - model - The model name supported by your provider.
   - system_context - The AI assistant's instructions/personality.
   - error_message - The message shown when an AI request fails.

   The bot adds and maintains server settings such as channels, mod_roles,
   admin_roles, and scheduled_unbans.

3. Configure .env

   Add these values to a .env file in this folder, or set them in your hosting
   provider's environment settings:

       DISCORD_BOT_TOKEN=<YOUR_BOT_TOKEN>
       OWNER_ID=<YOUR_DISCORD_USER_ID>
       MEMORY_ENCRYPTION_KEY=<A_RANDOM_SECRET>

   OWNER_ID is required for owner-only commands. MEMORY_ENCRYPTION_KEY is
   required to load and save conversation memory. Generate a strong key with:

       python -c "import secrets; print(secrets.token_urlsafe(32))"

   Keep the same memory key between restarts and back up the key securely.
   Losing or changing it prevents the bot from decrypting existing memory.
   Do not put credentials directly in main.py or share your .env file.

4. Configure the Discord application

   Enable the Message Content Intent in the Discord Developer Portal. Invite
   the bot with the application-command scope and the permissions it needs:
   view channels, read message history, send messages, manage messages
   (automod deletion), moderate members, ban members, and manage roles (for
   shop role features). The bot's role must be high enough to manage the roles
   it creates or assigns.

5. Start the bot and sync commands

   Run from this folder so the relative data/ paths resolve correctly:

       python main.py

   Slash commands are synced globally when the bot becomes ready. Global
   command updates can take time to appear in Discord.

6. Configure an AI chat channel

   In the desired server channel, run /setup as the bot owner. AI replies are
   only generated for messages in that configured channel. Run /unsetup as
   the owner to remove the channel configuration.

COMMANDS:

- General: /help, /setup, /unsetup, /say.
- Moderation: /warn, /mute, /ban, /warnings.
- Automod filter: /filteradd, /filterremove, /filterlist.
- Role access: /setmodrole, /removemodrole, /modroles, /setadminrole,
  /removeadminrole, /adminroles.
- AI memory: /clearmemory.
- Economy: /balance, /transfer, /addbalance, /daily, /shop, /inventory.
- Owner test utility: /test, /stoptest.

PERMISSIONS:

- The bot owner (OWNER_ID) has access to owner-only commands and bypasses the
  bot's moderator/admin role checks.
- Moderator commands accept the owner, members with Discord's Moderate Members
  permission, or members with a role configured using /setmodrole.
- Admin-role management accepts the owner, members with Discord's Administrator
  permission, or members with a role configured using /setadminrole. Setting or
  removing admin roles is restricted to the bot owner.
- /addbalance, /setup, /unsetup, /test, and /stoptest are owner-only.
- The bot also needs the corresponding Discord permissions to carry out
  moderation actions; bot-command access does not grant the bot permissions.

MODERATION NOTES:

- /warn and /mute attempt to DM the affected user. The command still proceeds
  if DMs are closed and reports that the DM could not be sent.
- /mute uses Discord's native timeout and accepts durations such as 10m, 2h,
  or 3d, with a maximum of 28 days.
- /ban accepts durations such as 10m, 2h, 3d, or 1w. Leave duration blank for
  a permanent ban. Scheduled temporary unbans are saved in data/config.json
  and restored when the bot starts again.
- Five identical messages in a row within the 60-second spam window in a server
  channel are deleted and generate a warning. Members with Moderate Members
  permission are exempt from automod.
- A message matching a server's filtered word or phrase is deleted and
  generates a warning. Members with Moderate Members permission are exempt.

PRESENCE:

The current status is set in main.py inside on_ready:

    activity=discord.Activity(type=discord.ActivityType.watching, name="YOU")
    status=discord.Status.idle

Discord status options include online, idle, dnd, and invisible.
