import random
import time
import discord


DAILY_COOLDOWN = 24 * 3600
DAILY_STREAK_WINDOW = 48 * 3600 
DAILY_BASE = 100
DAILY_STREAK_BONUS = 20         
DAILY_MAX_BONUS_DAYS = 10        
MESSAGE_REWARD_MIN, MESSAGE_REWARD_MAX = 1, 5
MESSAGE_COOLDOWN = 60       
MESSAGE_MIN_LENGTH = 3    


def register(bot, *, balances_data, get_balance, save_balances, format_currency,
             cooldowns_data, save_cooldowns, text_allowed=None):

    last_reward = {}

    async def reward_message(message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        text = message.content.strip()
        if len(text) < MESSAGE_MIN_LENGTH:
            return
        if text_allowed is not None and not text_allowed(message.guild.id, text):
            return

        now = time.time()
        last = last_reward.get(message.author.id)
        if last is not None:
            last_time, last_text = last
            if now - last_time < MESSAGE_COOLDOWN:
                return
            if text.lower() == last_text:
                return

        last_reward[message.author.id] = (now, text.lower())
        user_id = str(message.author.id)
        reward = random.randint(MESSAGE_REWARD_MIN, MESSAGE_REWARD_MAX)
        balances_data[user_id] = get_balance(message.author.id) + reward
        save_balances(balances_data)

    bot.add_listener(reward_message, "on_message")

    @bot.tree.command(name="daily", description="Claim your daily Amber")
    async def daily(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        now = time.time()
        entry = cooldowns_data.setdefault(user_id, {})

        ready_at = entry.get("daily_ready", 0)
        if now < ready_at:
            await interaction.response.send_message(
                f"You already claimed your daily Amber. Come back <t:{int(ready_at)}:R>.",
                ephemeral=True,
            )
            return

        last_claim = entry.get("daily_last")
        if last_claim is not None and now - last_claim <= DAILY_STREAK_WINDOW:
            streak = entry.get("daily_streak", 0) + 1
        else:
            streak = 1

        bonus = min(streak - 1, DAILY_MAX_BONUS_DAYS) * DAILY_STREAK_BONUS
        reward = DAILY_BASE + bonus

        entry["daily_ready"] = now + DAILY_COOLDOWN
        entry["daily_last"] = now
        entry["daily_streak"] = streak
        balances_data[user_id] = get_balance(interaction.user.id) + reward
        save_balances(balances_data)
        save_cooldowns(cooldowns_data)

        streak_text = (
            f" Streak: **{streak}** days (+{bonus} bonus)." if streak > 1 else ""
        )
        await interaction.response.send_message(
            f"You claimed **{format_currency(reward)}**!{streak_text}\n"
            f"New balance: **{format_currency(balances_data[user_id])}**."
        )