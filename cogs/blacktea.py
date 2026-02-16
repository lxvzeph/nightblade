import discord
import asyncio
import contextlib
import json
import os
import random
from discord.ext import commands

BASE_DIR = os.getcwd()
SUBSTRINGS_FILE = os.path.join(BASE_DIR, "substrings.json")
WORDS_FILE = os.path.join(BASE_DIR, "words.json")

with open(SUBSTRINGS_FILE, "r", encoding="utf-8") as f:
    SUBSTRINGS = json.load(f)

with open(WORDS_FILE, "r", encoding="utf-8") as f:
    WORDS = {
        w.lower()
        for w in json.load(f)
        if isinstance(w, str) and w.isalpha()
    }

TIME_LIMITS = {
    "easy": 20,
    "medium": 15,
    "hard": 10
}

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

LIFE_FULL = "<:fullheart:1467676312910041149>"
LIFE_EMPTY = "<:emptyheart:1467676774535266307>"

LIVES = 3

COUNTDOWN_EMOJIS = ["3️⃣", "2️⃣", "1️⃣"]

async def countdown(embed_msg, total_time: int, state: dict):
    try:
        await asyncio.sleep(max(0, total_time - 4))
        state["started"] = True

        for emoji in COUNTDOWN_EMOJIS:
            await embed_msg.add_reaction(emoji)
            await asyncio.sleep(1)

    except asyncio.TimeoutError:
        pass

class BlackTea(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = 0x2f3136
        self.running_games = {}
        self.reset_events = {}
        self.current_countdown = {}

    @staticmethod
    def render_lives(remaining: int):
        return (
            LIFE_FULL * remaining + LIFE_EMPTY * (LIVES - remaining)
        )

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
    
    @commands.group(invoke_without_command=True, aliases=["bt"])
    async def blacktea(self, ctx):

        channel_id = ctx.channel.id

        if channel_id in self.running_games:
            return await ctx.send(embed=self._embed(
                "",
                f"<a:sword_spin:1211611749426667560> A game is already queued or in progress.",
                ctx, include_author=False
            ))
        
        self.running_games[channel_id] = ctx.author.id
        
        queue_embed = self._embed(
            "Blacktea",
            "React with `✅` to join. The game will start in **30 seconds**.",
            ctx
        )
        queue_embed.add_field(
            name="How to Play",
            value=(
                "Each player must type a word containing a given substring\n"
                "The game starts easy and gets progressively harder\n"
                "Each player will be given **3 lives**\n"
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
            await ctx.send(embed=self._embed(
                "",
                "<a:sword_spin:1211611749426667560> Not enough players, Game cancelled.",
                ctx,
                include_author=False
            ))
            return
        
        lives = {p.id: 3 for p in players}
        used_words = set()

        rounds = (
            ["easy"] * 10 +
            ["medium"] * 5
        )

        round_index = 0
        self.reset_events[channel_id] = asyncio.Event()

        try:
            while len(players) > 1:
                
                player = players[round_index % len(players)]
    
                if lives[player.id] <= 0:
                    round_index += 1
                    continue
    
                difficulty = rounds.pop(0) if rounds else "hard"
                time_limit = TIME_LIMITS[difficulty]
    
                substring = random.choice(list(SUBSTRINGS.keys()))
    
                bt_embed = self._embed(
                    "☕",
                    f"Type a word containing: `{substring}`\n"
                    f"You have **{time_limit} seconds**",
                    ctx,
                    include_author=False
                )
                bt_embed.add_field(
                    name="Difficulty",
                    value=difficulty.capitalize(),
                    inline=False
                )
                embed_msg = await ctx.send(content=player.mention, embed=bt_embed)
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
    
                    word = guess.content.lower().strip()
                    
                    if (
                        word in WORDS
                        and substring in word
                        and word not in used_words
                    ):
                        if countdown_state["started"]:
                            countdown_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await countdown_task
    
                            with contextlib.suppress(Exception):
                                await embed_msg.clear_reactions()
    
                        await guess.add_reaction("✅")
                        used_words.add(word)
                        correct = True
                        break
                    else: await guess.add_reaction("❌")
    
                countdown_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await countdown_task
    
                with contextlib.suppress(Exception):
                    await embed_msg.clear_reactions()
    
                if not correct:
                    lives[player.id] -= 1
    
                    if lives[player.id] <= 0:
                        await ctx.send(
                            embed=self._embed(
                                "",
                                f"**Time's up!** {player.name} has lost a life!\n"
                                f"**{player.name}** has been eliminated!",
                                ctx,
                                include_author=False
                            )
                        )
                        players.remove(player)
                    else:
                        await ctx.send(embed=self._embed(
                            "",
                            f"**Time's up!** {player.name} has lost a life!\n**{player.name}**'s lives: {self.render_lives(lives[player.id])}",
                            ctx,
                            include_author=False
                        ))
                
                round_index += 1
            
            winner = players[0]
            await ctx.send(
                embed=self._embed(
                    "",
                    f"🏆 **{winner.name}** won the game!",
                    ctx,
                    include_author=False
                )
            )
        finally:
            self.running_games.pop(channel_id, None)
            self.current_countdown.pop(channel_id, None)
            self.reset_events.pop(channel_id, None)

    @blacktea.command(name="reset", aliases=["stop"])
    async def blacktea_reset(self, ctx):
        channel_id = ctx.channel.id

        if channel_id not in self.running_games:
            return await ctx.send(embed=self._embed(
                "",
                "<a:sword_spin:1211611749426667560> No game is currently running in this channel.",
                ctx, include_author=False
            ))
        
        if self.running_games[channel_id] != ctx.author.id:
            return await ctx.send(embed=self._embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Only the host can reset the game.",
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
    await bot.add_cog(BlackTea(bot))
    print("Blacktea cog loaded.")
                
