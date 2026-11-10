import asyncio
import json
import random
import time
from pathlib import Path

import discord
from discord import app_commands

MAX_BET = 50_000

GUESS_COOLDOWN = 30 * 60
GUESS_MAX_TRIES = 7
GUESS_BASE_REWARD = 40

HANGMAN_COOLDOWN = 30 * 60
HANGMAN_MAX_MISTAKES = 6
HANGMAN_PER_LETTER = 10
HANGMAN_PER_LIFE = 15
WORDS_FILE = Path("data") / "words.json"

SUITS = "♠♥♦♣"
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

HANGMAN_ART = [
    "  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========",
]


def load_hangman_words() -> list[str]:
    try:
        with open(WORDS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    words = {w.lower() for w in data.get("allWords", []) if w.isalpha() and 4 <= len(w) <= 12}
    return sorted(words)


HANGMAN_WORDS = load_hangman_words()


def new_deck():
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


def hand_value(hand):
    total, aces = 0, 0
    for rank, _ in hand:
        if rank == "A":
            total += 11
            aces += 1
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def show_hand(hand, hide_second=False):
    if hide_second:
        return f"`{hand[0][0]}{hand[0][1]}` `??`"
    return " ".join(f"`{r}{s}`" for r, s in hand)


def register(bot, *, balances_data, get_balance, save_balances, format_currency,
             cooldowns_data, save_cooldowns, **_ignored):
    active: set[int] = set()

    for _name in ("coinflip", "rps", "blackjack", "guess", "hangman"):
        bot.tree.remove_command(_name)

    def credit(uid: int, amount: int):
        if amount:
            balances_data[str(uid)] = get_balance(uid) + amount
            save_balances(balances_data)

    def cd_left(uid: int, name: str, seconds: int) -> float:
        last = cooldowns_data.get("_games", {}).get(f"{name}:{uid}", 0)
        return max(0.0, last + seconds - time.time())

    def cd_set(uid: int, name: str):
        cooldowns_data.setdefault("_games", {})[f"{name}:{uid}"] = time.time()
        save_cooldowns(cooldowns_data)

    async def start_bet(interaction: discord.Interaction, bet: int) -> bool:
        uid = interaction.user.id
        if uid in active:
            await interaction.response.send_message(
                "You already have a game running - finish it first.", ephemeral=True)
            return False
        if get_balance(uid) < bet:
            await interaction.response.send_message(
                f"You don't have enough Amber. Your balance is **{format_currency(get_balance(uid))}**.",
                ephemeral=True)
            return False
        credit(uid, -bet)
        return True

    async def start_free(interaction: discord.Interaction, name: str, seconds: int) -> bool:
        uid = interaction.user.id
        if uid in active:
            await interaction.response.send_message(
                "You already have a game running - finish it first.", ephemeral=True)
            return False
        left = cd_left(uid, name, seconds)
        if left > 0:
            await interaction.response.send_message(
                f"You can play **/{name}** again <t:{int(time.time() + left)}:R>.", ephemeral=True)
            return False
        cd_set(uid, name)
        return True

    def net_text(bet: int, payout: int) -> str:
        net = payout - bet
        if net > 0:
            return f"**+{format_currency(net)}**"
        if net < 0:
            return f"**-{format_currency(-net)}**"
        return "**±0**"

    class OwnedView(discord.ui.View):
        uid: int

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.uid:
                await interaction.response.send_message("This isn't your game.", ephemeral=True)
                return False
            return True

        def lock(self):
            for child in self.children:
                child.disabled = True

    class ReplayView(OwnedView):


        def __init__(self, uid: int, launcher):
            super().__init__(timeout=60)
            self.uid = uid
            self.launcher = launcher 
            self.message = None

        @discord.ui.button(label="Play again", emoji="🔁", style=discord.ButtonStyle.success)
        async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if await self.launcher(interaction):
                self.stop()

        @discord.ui.button(label="End", emoji="🛑", style=discord.ButtonStyle.danger)
        async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.stop()
            await interaction.response.edit_message(view=None)

        async def on_timeout(self):
            if self.message:
                try:
                    await self.message.edit(view=None)
                except discord.HTTPException:
                    pass

    async def respond(interaction: discord.Interaction, edit: bool, **kwargs):

        if edit:
            await interaction.response.edit_message(**kwargs)
            return interaction.message
        await interaction.response.send_message(**kwargs)
        return await interaction.original_response()

    # ---------------------------------------------------------------- coinflip
    async def run_coinflip(interaction: discord.Interaction, bet: int, side: str, edit: bool = False) -> bool:
        if not await start_bet(interaction, bet):
            return False
        uid = interaction.user.id
        result = random.choice(["heads", "tails"])
        won = result == side
        payout = bet * 2 if won else 0
        credit(uid, payout)
        view = ReplayView(uid, lambda i: run_coinflip(i, bet, side, True))
        view.message = await respond(
            interaction, edit,
            content=(f"🪙 The coin landed on **{result}**. "
                     f"{'You win!' if won else 'You lose.'} {net_text(bet, payout)}\n"
                     f"Balance: {format_currency(get_balance(uid))}"),
            view=view)
        return True

    @bot.tree.command(name="coinflip", description="Bet Amber on a coin flip (double or nothing)")
    @app_commands.describe(bet="How much Amber to bet", side="Heads or tails?")
    @app_commands.choices(side=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    async def coinflip(interaction: discord.Interaction,
                       bet: app_commands.Range[int, 1, MAX_BET],
                       side: app_commands.Choice[str]):
        await run_coinflip(interaction, bet, side.value)

    # --------------------------------------------------------------------- rps
    class RPSView(OwnedView):
        def __init__(self, uid: int, bet: int):
            super().__init__(timeout=30)
            self.uid, self.bet, self.message = uid, bet, None

        async def play(self, interaction: discord.Interaction, choice: str):
            bot_choice = random.choice(list(RPS_BEATS))
            if choice == bot_choice:
                payout, text = self.bet, "It's a tie - bet returned."
            elif RPS_BEATS[choice] == bot_choice:
                payout, text = self.bet * 2, "You win!"
            else:
                payout, text = 0, "You lose."
            credit(self.uid, payout)
            active.discard(self.uid)
            self.stop()
            bet = self.bet
            replay = ReplayView(self.uid, lambda i: run_rps(i, bet, True))
            await interaction.response.edit_message(content=(
                f"You: {RPS_EMOJI[choice]} **{choice}**  vs  Phoebe: {RPS_EMOJI[bot_choice]} **{bot_choice}**\n"
                f"{text} {net_text(self.bet, payout)}\n"
                f"Balance: {format_currency(get_balance(self.uid))}"
            ), view=replay)
            replay.message = interaction.message

        @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
        async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.play(interaction, "rock")

        @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
        async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.play(interaction, "paper")

        @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
        async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.play(interaction, "scissors")

        async def on_timeout(self):
            active.discard(self.uid)
            self.lock()
            if self.message:
                try:
                    await self.message.edit(content="⏰ Timed out - bet forfeited.", view=None)
                except discord.HTTPException:
                    pass

    async def run_rps(interaction: discord.Interaction, bet: int, edit: bool = False) -> bool:
        if not await start_bet(interaction, bet):
            return False
        active.add(interaction.user.id)
        view = RPSView(interaction.user.id, bet)
        view.message = await respond(
            interaction, edit, content=f"Betting **{format_currency(bet)}**. Pick your move:", view=view)
        return True

    @bot.tree.command(name="rps", description="Rock paper scissors against Phoebe.")
    @app_commands.describe(bet="How much Amber to bet")
    async def rps(interaction: discord.Interaction, bet: app_commands.Range[int, 1, MAX_BET]):
        await run_rps(interaction, bet)

    # --------------------------------------------------------------- blackjack
    class BlackjackView(OwnedView):
        def __init__(self, uid: int, bet: int):
            super().__init__(timeout=60)
            self.uid, self.bet, self.message = uid, bet, None
            self.deck = new_deck()
            self.player = [self.deck.pop(), self.deck.pop()]
            self.dealer = [self.deck.pop(), self.deck.pop()]

        def embed(self, result: str | None = None, color: discord.Color | None = None):
            reveal = result is not None
            e = discord.Embed(title="🃏 Blackjack", color=color or discord.Color.blurple())
            e.add_field(name=f"Your hand ({hand_value(self.player)})",
                        value=show_hand(self.player), inline=False)
            e.add_field(name=f"Dealer ({hand_value(self.dealer) if reveal else '?'})",
                        value=show_hand(self.dealer, hide_second=not reveal), inline=False)
            e.set_footer(text=f"Bet: {format_currency(self.bet)}")
            if result:
                e.description = result
            return e

        def replay_view(self) -> ReplayView:
            bet = self.bet
            return ReplayView(self.uid, lambda i: run_blackjack(i, bet, True))

        def finalize(self, outcome: str) -> discord.Embed:
            payout, text, color = {
                "blackjack": (self.bet + self.bet * 3 // 2, "Blackjack! Pays 3:2.", discord.Color.green()),
                "win": (self.bet * 2, "You win!", discord.Color.green()),
                "push": (self.bet, "Push - bet returned.", discord.Color.gold()),
                "lose": (0, "Dealer wins.", discord.Color.red()),
                "bust": (0, "Bust! You went over 21.", discord.Color.red()),
                "timeout": (0, "Timed out - bet forfeited.", discord.Color.red()),
            }[outcome]
            credit(self.uid, payout)
            active.discard(self.uid)
            self.lock()
            self.stop()
            return self.embed(f"{text} {net_text(self.bet, payout)}", color)

        async def _finish(self, interaction: discord.Interaction, outcome: str):
            replay = self.replay_view()
            await interaction.response.edit_message(embed=self.finalize(outcome), view=replay)
            replay.message = interaction.message

        async def dealer_turn(self, interaction: discord.Interaction):
            while hand_value(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
            p, d = hand_value(self.player), hand_value(self.dealer)
            outcome = "win" if d > 21 or p > d else "push" if p == d else "lose"
            await self._finish(interaction, outcome)

        @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
        async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.player.append(self.deck.pop())
            value = hand_value(self.player)
            if value > 21:
                await self._finish(interaction, "bust")
            elif value == 21:
                await self.dealer_turn(interaction)
            else:
                await interaction.response.edit_message(embed=self.embed(), view=self)

        @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
        async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.dealer_turn(interaction)

        async def on_timeout(self):
            if self.uid in active:
                embed = self.finalize("timeout")
                if self.message:
                    try:
                        await self.message.edit(embed=embed, view=None)
                    except discord.HTTPException:
                        pass

    async def run_blackjack(interaction: discord.Interaction, bet: int, edit: bool = False) -> bool:
        if not await start_bet(interaction, bet):
            return False
        active.add(interaction.user.id)
        view = BlackjackView(interaction.user.id, bet)

        if hand_value(view.player) == 21:
            outcome = "push" if hand_value(view.dealer) == 21 else "blackjack"
            replay = view.replay_view()
            replay.message = await respond(interaction, edit, embed=view.finalize(outcome), view=replay)
            return True

        view.message = await respond(interaction, edit, embed=view.embed(), view=view)
        return True

    @bot.tree.command(name="blackjack", description="Play blackjack against her")
    @app_commands.describe(bet="How much Amber to bet")
    async def blackjack(interaction: discord.Interaction, bet: app_commands.Range[int, 1, MAX_BET]):
        await run_blackjack(interaction, bet)

    # ------------------------------------------------------------------- guess
    class GuessModal(discord.ui.Modal, title="Make a guess"):
        number = discord.ui.TextInput(label="Pick a number from 1 to 100", min_length=1, max_length=3)

        def __init__(self, game: "GuessView"):
            super().__init__()
            self.game = game

        async def on_submit(self, interaction: discord.Interaction):
            try:
                guess = int(self.number.value)
            except ValueError:
                await interaction.response.send_message("Numbers only!", ephemeral=True)
                return
            if not 1 <= guess <= 100:
                await interaction.response.send_message("Pick a number between 1 and 100.", ephemeral=True)
                return
            await self.game.handle(interaction, guess)

    class GuessView(OwnedView):
        def __init__(self, uid: int):
            super().__init__(timeout=120)
            self.uid = uid
            self.target = random.randint(1, 100)
            self.tries = 0
            self.history: list[str] = []
            self.message = None

        def embed(self, note: str | None = None, color: discord.Color | None = None):
            left = GUESS_MAX_TRIES - self.tries
            e = discord.Embed(
                title="🔢 Guess the Number",
                description=note or "I'm thinking of a number between **1 and 100**.",
                color=color or discord.Color.blurple(),
            )
            if self.history:
                e.add_field(name="Guesses", value="\n".join(self.history), inline=False)
            e.set_footer(text=f"Tries left: {left}  |  Fewer tries = bigger reward")
            return e

        @discord.ui.button(label="Guess", emoji="🔢", style=discord.ButtonStyle.primary)
        async def guess(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(GuessModal(self))

        async def handle(self, interaction: discord.Interaction, guess: int):
            self.tries += 1
            if guess == self.target:
                reward = GUESS_BASE_REWARD * (GUESS_MAX_TRIES + 1 - self.tries)
                credit(self.uid, reward)
                self.history.append(f"{guess} ✅")
                await self._end(interaction, discord.Color.green(),
                                f"🎉 Correct in **{self.tries}** tries! You earned **{format_currency(reward)}**.")
            elif self.tries >= GUESS_MAX_TRIES:
                self.history.append(f"{guess} ❌")
                await self._end(interaction, discord.Color.red(),
                                f"Out of tries! The number was **{self.target}**.")
            else:
                hint = "higher ⬆️" if guess < self.target else "lower ⬇️"
                self.history.append(f"{guess} → go {hint}")
                await interaction.response.edit_message(embed=self.embed(), view=self)

        async def _end(self, interaction, color, note):
            active.discard(self.uid)
            self.stop()
            replay = ReplayView(self.uid, lambda i: run_guess(i, True))
            await interaction.response.edit_message(embed=self.embed(note, color), view=replay)
            replay.message = interaction.message

        async def on_timeout(self):
            active.discard(self.uid)
            if self.message:
                try:
                    await self.message.edit(
                        embed=self.embed(f"⏰ Time's up! The number was **{self.target}**.",
                                         discord.Color.red()),
                        view=None)
                except discord.HTTPException:
                    pass

    async def run_guess(interaction: discord.Interaction, edit: bool = False) -> bool:
        if not await start_free(interaction, "guess", GUESS_COOLDOWN):
            return False
        active.add(interaction.user.id)
        view = GuessView(interaction.user.id)
        view.message = await respond(interaction, edit, embed=view.embed(), view=view)
        return True

    @bot.tree.command(name="guess", description="Guess the number.")
    async def guess_cmd(interaction: discord.Interaction):
        await run_guess(interaction)

    # ----------------------------------------------------------------- hangman
    class HangmanLetterModal(discord.ui.Modal, title="Guess a letter"):
        letter = discord.ui.TextInput(label="Single letter (a-z)", min_length=1, max_length=1)

        def __init__(self, game: "HangmanView"):
            super().__init__()
            self.game = game

        async def on_submit(self, interaction: discord.Interaction):
            ch = self.letter.value.strip().lower()
            if len(ch) != 1 or not ch.isalpha() or not ch.isascii():
                await interaction.response.send_message("Letters a-z only!", ephemeral=True)
                return
            if ch in self.game.guessed:
                await interaction.response.send_message(
                    f"You already guessed **{ch}**.", ephemeral=True)
                return
            await self.game.handle_letter(interaction, ch)

    class HangmanSolveModal(discord.ui.Modal, title="Guess the whole word"):
        word = discord.ui.TextInput(label="Your answer", min_length=1, max_length=20)

        def __init__(self, game: "HangmanView"):
            super().__init__()
            self.game = game

        async def on_submit(self, interaction: discord.Interaction):
            await self.game.handle_word(interaction, self.word.value.strip().lower())

    class HangmanView(OwnedView):
        def __init__(self, uid: int):
            super().__init__(timeout=180)
            self.uid = uid
            self.word = random.choice(HANGMAN_WORDS)
            self.guessed: list[str] = []
            self.mistakes = 0
            self.message = None

        def masked(self, reveal: bool = False) -> str:
            return " ".join(c if reveal or c in self.guessed else "_" for c in self.word)

        def embed(self, note: str | None = None, color: discord.Color | None = None, reveal: bool = False):
            e = discord.Embed(
                title="🪢 Hangman",
                description=f"```\n{HANGMAN_ART[self.mistakes]}\n```\n# `{self.masked(reveal)}`",
                color=color or discord.Color.blurple(),
            )
            if note:
                e.add_field(name="\u200b", value=note, inline=False)
            wrong = [c for c in self.guessed if c not in self.word]
            right = [c for c in self.guessed if c in self.word]
            e.add_field(name="Wrong", value=" ".join(wrong).upper() or "-", inline=True)
            e.add_field(name="Correct", value=" ".join(right).upper() or "-", inline=True)
            e.set_footer(text=f"Lives left: {HANGMAN_MAX_MISTAKES - self.mistakes}  |  {len(self.word)} letters")
            return e

        @discord.ui.button(label="Guess letter", emoji="🔤", style=discord.ButtonStyle.primary)
        async def letter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(HangmanLetterModal(self))

        @discord.ui.button(label="Guess word", emoji="💡", style=discord.ButtonStyle.secondary)
        async def word_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(HangmanSolveModal(self))

        def lives_left(self) -> int:
            return HANGMAN_MAX_MISTAKES - self.mistakes

        async def _win(self, interaction: discord.Interaction):
            reward = len(self.word) * HANGMAN_PER_LETTER + self.lives_left() * HANGMAN_PER_LIFE
            credit(self.uid, reward)
            await self._end(interaction, discord.Color.green(),
                            f"🎉 You got it! The word was **{self.word}**. "
                            f"You earned **{format_currency(reward)}**.", reveal=True)

        async def _lose(self, interaction: discord.Interaction):
            await self._end(interaction, discord.Color.red(),
                            f"💀 You're out of lives! The word was **{self.word}**.", reveal=True)

        async def handle_letter(self, interaction: discord.Interaction, ch: str):
            self.guessed.append(ch)
            if ch in self.word:
                if all(c in self.guessed for c in self.word):
                    await self._win(interaction)
                else:
                    await interaction.response.edit_message(
                        embed=self.embed(f"✅ **{ch.upper()}** is in the word!"), view=self)
            else:
                self.mistakes += 1
                if self.mistakes >= HANGMAN_MAX_MISTAKES:
                    await self._lose(interaction)
                else:
                    await interaction.response.edit_message(
                        embed=self.embed(f"❌ No **{ch.upper()}** in the word."), view=self)

        async def handle_word(self, interaction: discord.Interaction, attempt: str):
            if attempt == self.word:
                await self._win(interaction)
                return
            self.mistakes += 1
            if self.mistakes >= HANGMAN_MAX_MISTAKES:
                await self._lose(interaction)
            else:
                await interaction.response.edit_message(
                    embed=self.embed(f"❌ **{attempt}** isn't the word. You lost a life."), view=self)

        async def _end(self, interaction, color, note, reveal=False):
            active.discard(self.uid)
            self.stop()
            replay = ReplayView(self.uid, lambda i: run_hangman(i, True))
            await interaction.response.edit_message(
                embed=self.embed(note, color, reveal=reveal), view=replay)
            replay.message = interaction.message

        async def on_timeout(self):
            active.discard(self.uid)
            if self.message:
                try:
                    await self.message.edit(
                        embed=self.embed(f"⏰ Time's up! The word was **{self.word}**.",
                                         discord.Color.red(), reveal=True),
                        view=None)
                except discord.HTTPException:
                    pass

    async def run_hangman(interaction: discord.Interaction, edit: bool = False) -> bool:
        if not HANGMAN_WORDS:
            await interaction.response.send_message(
                "Hangman is unavailable right now (word list missing).", ephemeral=True)
            return False
        if not await start_free(interaction, "hangman", HANGMAN_COOLDOWN):
            return False
        active.add(interaction.user.id)
        view = HangmanView(interaction.user.id)
        view.message = await respond(interaction, edit, embed=view.embed(), view=view)
        return True

    @bot.tree.command(name="hangman", description="Guess the words.")
    async def hangman_cmd(interaction: discord.Interaction):
        await run_hangman(interaction)