import discord
import asyncio
import contextlib
import random
import json
import os
from discord.ext import commands
from copy import deepcopy

BASE_DIR = os.getcwd()
COUNTRIES_FILE = os.path.join(BASE_DIR, "countries.json")

with open(COUNTRIES_FILE, "r", encoding="utf-8") as f:
    COUNTRIES = json.load(f)

COUNTDOWN_EMOJIS = ["3️⃣", "2️⃣", "1️⃣"]

LIFE_FULL = "<:fullheart:1467676312910041149>"
LIFE_EMPTY = "<:emptyheart:1467676774535266307>"

LIVES = 3

async def countdown(embed_msg, total_time: int, state: dict):
    try:
        await asyncio.sleep(max(0, total_time - 4))
        state["started"] = True

        for emoji in COUNTDOWN_EMOJIS:
            await embed_msg.add_reaction(emoji)
            await asyncio.sleep(1)

    except asyncio.TimeoutError:
        pass

class Flag(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = 0x2f3136
        self.running_games = {}
        self.reset_events = {}
        self.current_countdown = {}

    def _embed(self, title, description, ctx_or_msg, include_author=True, color=None):

        try:
            bot_avatar = self.bot.user.avatar.url
        except:
            bot_avatar = None

        final_color = discord.Color(color) if isinstance(color, int) else color
        if final_color is None:
            final_color = discord.Color(self.EMBED_COLOR)

        embed = discord.Embed(
            title=title if title else "",
            description=description,
            color=final_color
        )

        if include_author:
            if isinstance(ctx_or_msg, discord.Message):
                guild = ctx_or_msg.guild

            else:
                guild = ctx_or_msg.guild

            if guild:
                bot_display_name = guild.me.display_name
            else:
                bot_display_name = self.bot.user.name
            
            embed.set_author(
                name=bot_display_name,
                icon_url=bot_avatar or self.bot.user.avatar.url
            )

        return embed
    
    @staticmethod
    def render_lives(remaining: int):
        return (LIFE_FULL * remaining + LIFE_EMPTY * (LIVES - remaining))

    @commands.command(aliases=["country"])
    @commands.cooldown(2, 6, commands.BucketType.user)
    async def flag(self, ctx, difficulty: str | None = None):
        if difficulty:
            difficulty = difficulty.lower()
        
        if not difficulty:
            difficulty = random.choices(
                ["medium", "easy", "hard", "insane"],
                weights=[0.5, 0.3, 0.15, 0.05],
                k=1
            )[0]

        country = random.choice(COUNTRIES[difficulty])
        answer = country["name"].lower()

        embed = discord.Embed(
            title="Guess the Country!",
            description="You have **30 seconds** to guess.\nType your answer in the chat.",
            color=0x2f3136
        )
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )
        embed.set_thumbnail(url=country["flag"])
        embed.add_field(
            name="Difficulty",
            value=difficulty.capitalize(),
            inline=False
        )
        embed.set_footer(text="Type 'skip', 'idk', or 'pass' to skip")

        embed_msg = await ctx.send(embed=embed)

        TIME_LIMIT = 30
        countdown_state = {"started": False}

        countdown_task = asyncio.create_task(
            countdown(embed_msg, TIME_LIMIT, countdown_state)
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        correct = False
        start = asyncio.get_running_loop().time()

        while True:
            remaining = TIME_LIMIT - (asyncio.get_running_loop().time() - start)
            if remaining <= 0:
                break

            try:
                guess = await self.bot.wait_for(
                    "message",
                    timeout=remaining,
                    check=check
                )
            except asyncio.TimeoutError:
                break

            guess_text = guess.content.lower().strip()
            valid_answers = {country["name"].lower()}
            SKIP_WORDS = {"skip", "idk", "pass"}

            for alias in country.get("aliases", []):
                valid_answers.add(alias.lower())

            if guess_text in SKIP_WORDS:
                countdown_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await countdown_task
                with contextlib.suppress(Exception):
                    await embed_msg.clear_reactions()

                embed.color = discord.Color(0x963939)
                embed.description = f"**Skipped!** The answer was **{country["name"]}**"
                embed.set_footer(text=None)
                await embed_msg.edit(embed=embed)
                correct = True
                break

            if guess_text in valid_answers:
                if countdown_state["started"]:
                    countdown_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await countdown_task

                    with contextlib.suppress(Exception):
                        await embed_msg.clear_reactions()

                embed.color = discord.Color.from_rgb(113, 144, 110)
                embed.description = f"**Correct!** The answer is **{country['name']}**"
                embed.set_footer(text=None)
                await embed_msg.edit(embed=embed)

                correct = True
                break

        countdown_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await countdown_task

        try:
            await embed_msg.clear_reactions()
        except:
            pass

        if not correct:
            embed.color = discord.Color.from_rgb(150, 57, 57)
            embed.description = f"**Time's up!** The answer was **{country['name']}**"
            embed.set_footer(text=None)
            await embed_msg.edit(embed=embed)

    @flag.error
    async def flag_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: This command is on `{error.retry_after:.1f}`s cooldown.",
                    ctx,
                    include_author=False
                )
            )

    @commands.group(aliases=["countries"], invoke_without_command=True)
    async def flags(self, ctx):

        channel_id = ctx.channel.id

        if channel_id in self.running_games:
            await ctx.send(
                embed=self._embed(
                    "",
                    "<a:sword_spin:1211611749426667560> A game is already queued or in progress.",
                    ctx,
                    include_author=False
                )
            )
            return
        
        self.running_games[channel_id] = ctx.author.id
        
        queue_embed = self._embed(
            "Guess the Country!",
            "React with `✅` to join. Game starting in **30 seconds**.",
            ctx
        )
        queue_embed.add_field(
            name="How to Play",
            value=(
                "Each player has a limited time to guess the flag\n"
                "The game will start easy and get progressively harder\n"
                "Each player will be given **3 lives**, you lose all of them and you will be eliminated\n"
                "Last player standing wins.\n"
                "Good luck!"
            ),
            inline=False
        )
        queue_embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        queue_msg = await ctx.send(embed=queue_embed)
        await queue_msg.add_reaction("✅")
        await asyncio.sleep(30)

        queue_msg = await ctx.channel.fetch_message(queue_msg.id)
        reaction = discord.utils.get(queue_msg.reactions, emoji="✅")

        players = []
        if reaction:
            async for user in reaction.users():
                if not user.bot:
                    players.append(user)

        if len(players) < 2:
            self.running_games.pop(channel_id, None)
            cancel_embed = self._embed(
                "",
                "<a:sword_spin:1211611749426667560> Not enough players. Game cancelled.",
                ctx,
                include_author=False
            )
            await ctx.send(embed=cancel_embed)
            return

        self.reset_events[channel_id] = asyncio.Event()
        
        try:
            lives = {player.id: 3 for player in players}
    
            draw_pools = {
                diff: random.sample(COUNTRIES[diff], k=len(COUNTRIES[diff]))
                for diff in COUNTRIES
            }
    
            def draw_country(difficulty):
                pool = draw_pools[difficulty]
    
                if not pool:
                    pool.extend(random.sample(COUNTRIES[difficulty], k=len(COUNTRIES[difficulty])))
    
                return pool.pop()
    
            rounds = (
                [("easy", 20)] * 6 +
                [("medium", 15)] * 8 +
                [("hard", 10)] * 10
            )
    
            round_index = 0
    
            while len(players) > 1:
                
                difficulty, time_limit = (
                    rounds.pop(0) if rounds else ("insane", 8)
                )
    
                for player in players[:]:
                    if len(players) <= 1:
                        break
    
                    if lives[player.id] <= 0:
                        continue
    
                    country = draw_country(difficulty)
                    answer = country["name"].lower()
    
                    flag_embed = self._embed(
                        "Guess the Country!",
                        f"You have **{time_limit} seconds** to guess!",
                        ctx,
                        include_author=False)
                    flag_embed.set_thumbnail(url=country["flag"])
                    flag_embed.add_field(
                        name="Difficulty",
                        value=difficulty.capitalize(),
                        inline=False
                    )
                    flag_embed.set_footer(text="Typing 'skip', 'idk', or 'pass' will skip your turn.")
                    embed_msg = await ctx.send(content=player.mention, embed=flag_embed)
                    countdown_state = {"started": False}

                    countdown_task = asyncio.create_task(
                        countdown(embed_msg, time_limit, countdown_state)
                    )
                    self.current_countdown[channel_id] = countdown_task
    
                    def check(m):
                        return m.author == player and m.channel == ctx.channel
                    
                    start = asyncio.get_running_loop().time()
                    correct = False
    
                    while True:
                        remaining = time_limit - (asyncio.get_running_loop().time() - start)
                        if remaining <= 0:
                            break

                        if self.reset_events.get(channel_id, asyncio.Event()).is_set():
                            countdown_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await countdown_task
                            with contextlib.suppress(Exception):
                                await embed_msg.clear_reactions()
                            return
    
                        try:
                            guess = await asyncio.wait_for(
                                self.bot.wait_for("message", check=check),
                                timeout=min(remaining, 1.0)
                            )
                        except asyncio.TimeoutError:
                            continue

                        guess_text = guess.content.lower().strip()
                        valid_answers = {country["name"].lower()}
                        SKIP_WORDS = {"skip", "pass"}

                        for alias in country.get("aliases", []):
                            valid_answers.add(alias.lower())

                        if guess_text in SKIP_WORDS:
                            countdown_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await countdown_task
                            with contextlib.suppress(Exception):
                                await embed_msg.clear_reactions()

                            lives[player.id] -= 1

                            if lives[player.id] <= 0:
                                elim_embed = self._embed(
                                    "",
                                    f"**Skipped!** The answer was **{country["name"]}**\n"
                                    f"**{player.name}** has been eliminated!",
                                    ctx, include_author=False
                                )
                                await ctx.send(embed=elim_embed)
                                players.remove(player)
                            else:
                                skip_embed = self._embed(
                                    "",
                                    f"**Skipped!** The answer was **{country["name"]}**\n"
                                    f"**{player.name}'s** lives: {self.render_lives(lives[player.id])}",
                                    ctx, include_author=False
                                )
                                await ctx.send(embed=skip_embed)
                            correct = True
                            break
    
                        if guess_text in valid_answers:
                            if countdown_state["started"]:
                                countdown_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await countdown_task

                                with contextlib.suppress(Exception):
                                    await embed_msg.clear_reactions()

                            await guess.add_reaction("✅")
                            correct = True
                            break
                        else:
                            await guess.add_reaction("❌")

                    countdown_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await countdown_task

                    with contextlib.suppress(Exception):
                        await embed_msg.clear_reactions()
    
                    if not correct:
                        lives[player.id] -= 1
    
                        if lives[player.id] <= 0:
                            elim_embed = self._embed(
                                "",
                                f"**Time's up!** The answer was **{country['name']}**\n"
                                f"**{player.name}** has been eliminated!",
                                ctx,
                                include_author=False
                            )
                            await ctx.send(embed=elim_embed)
                            players.remove(player)
                        else:
                            timeout_embed = self._embed(
                                "",
                                f"**Time's up!** The answer was **{country['name']}**\n"
                                f"**{player.name}'s** lives: {self.render_lives(lives[player.id])}",
                                ctx,
                                include_author=False
                            )
                            await ctx.send(embed=timeout_embed)

    
                round_index += 1
    
            winner = players[0]
            win_embed = self._embed(
                "",
                f"🏆 **{winner.name}** won the game!",
                ctx,
                include_author=False
            )
            await ctx.send(embed=win_embed)

        finally:
            self.running_games.pop(channel_id, None)
            self.current_countdown.pop(channel_id, None)
            self.reset_events.pop(channel_id, None)

    @flags.command(name="reset", aliases=["stop"])
    async def flags_reset(self, ctx):
        channel_id = ctx.channel.id

        if channel_id not in self.running_games:
            return await ctx.send(embed=self._embed(
                "", "<a:sword_spin:1211611749426667560> No game is currently running in this channel.",
                ctx, include_author=False
            ))
        
        if self.running_games[channel_id] != ctx.author.id:
            return await ctx.send(embed=self._embed(
                "", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Only the host can reset the game.",
                ctx, include_author=False
            ))
        
        if channel_id in self.reset_events:
            self.reset_events[channel_id].set()

        task = self.current_countdown.pop(channel_id, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self.running_games.pop(channel_id, None)

        await ctx.send(embed=self._embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: The game has been reset.",
            ctx, include_author=False
        ))

async def setup(bot):
    await bot.add_cog(Flag(bot))
    print("Flag cog loaded.")

