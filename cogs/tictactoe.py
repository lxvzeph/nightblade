import discord
from discord.ext import commands

EMPTY = "<:empty:1472583072393461791>"
X_MARK = "<:whitex:1472569473008668703>"
O_MARK = "<:whitecircle:1472570536348614708>"

WINNING_COMBOS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6)
]

def check_winner(board):
    for a, b, c in WINNING_COMBOS:
        if board[a] != EMPTY and board[a] == board[b] == board[c]:
            return board[a]
    return None

def is_draw(board):
    return all(cell != EMPTY for cell in board) and check_winner(board) is None

class TicTacToeButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(
            emoji=EMPTY,
            label="\u200b",
            style=discord.ButtonStyle.secondary,
            row=index // 3
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view

        if interaction.user.id != view.current_player.id:
            return await interaction.response.send_message(
                embed=view.cog._embed(
                    "", f"<a:sword_spin:1211611749426667560> {interaction.user.mention}: It's not your turn.",
                    view.ctx, include_author=False
                ),
                ephemeral=True
            )
        
        if view.board[self.index] != EMPTY:
            return await interaction.response.send_message(
                embed=view.cog._embed(
                    "", f"<a:sword_spin:1211611749426667560> {interaction.user.mention}: That cell is already taken.",
                    view.ctx, include_author=False
                ),
                ephemeral=True
            )
        
        mark = X_MARK if view.current_player == view.player_x else O_MARK
        view.board[self.index] = mark
        self.emoji = discord.PartialEmoji.from_str(mark)
        self.label = "\u200b"
        self.style = (
            discord.ButtonStyle.danger if mark == X_MARK
            else discord.ButtonStyle.primary
        )
        self.disabled = True

        winner_mark = check_winner(view.board)
        if winner_mark:
            winner = view.player_x if winner_mark == X_MARK else view.player_o
            view.disable_all()
            view.stop()
            embed = view.cog._embed(
                "Tic-Tac-Toe",
                f"🏆 **{winner.name}** wins!",
                view.ctx, include_author=False
            )
            return await interaction.response.edit_message(embed=embed, view=view)
        
        if is_draw(view.board):
            view.disable_all()
            view.stop()
            return await interaction.response.edit_message(
                embed=view.cog._embed(
                    "",
                    "<:whitex:1472569473008668703> **It's a draw!** <:whitecircle:1472570536348614708>",
                    view.ctx, include_author=False
                ), view=view
            )
        
        view.current_player = (
            view.player_o if view.current_player == view.player_x
            else view.player_x
        )
        await interaction.response.edit_message(embed=view.make_embed(), view=view)

class TicTacToeView(discord.ui.View):
    def __init__(self, ctx, cog, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x
        self.board = [EMPTY] * 9
        self.message = None

        for i in range(9):
            self.add_item(TicTacToeButton(i))

    def make_embed(self):
        embed = self.cog._embed(
            "Tic-Tac-Toe",
            f"**{self.current_player.name}**'s turn "
            f"{'<:whitex:1472569473008668703>' if self.current_player == self.player_x else '<:whitecircle:1472570536348614708>'}\n\n"
            f"-# {self.player_x.name} <:whitex:1472569473008668703> vs. {self.player_o.name} <:whitecircle:1472570536348614708>",
            self.ctx, include_author=False
        )
        return embed
    
    def disable_all(self):
        for child in self.children:
            child.disabled = True

    async def on_timeout(self):
        self.disable_all()
        try:
            embed = self.cog._embed(
                "Tic-Tac-Toe",
                f" Game timed out. **{self.current_player.display_name}** took too long.",
                self.ctx, include_author=False
            )
            await self.message.edit(embed=embed, view=None)
        except:
            pass
        self.stop()

class TicTacToeChallenge(discord.ui.View):
    def __init__(self, ctx, cog, challenger: discord.Member, challenged: discord.Member):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.cog = cog
        self.challenger = challenger
        self.challenged = challenged
        self.message = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            return await interaction.response.send_message(
                embed=self.cog._embed(
                    "", f"<a:sword_spin:1211611749426667560> {interaction.user.mention}: This challenge is not for you.",
                    self.ctx, include_author=False
                ),
                ephemeral=True
            )
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None,
            embed=self.cog._embed(
                "", f"<a:sword_spin:1211611749426667560> {self.challenged.mention} accepted the challenge!",
                self.ctx, include_author=False
            ),
            view=None
        )
        game = TicTacToeView(self.ctx, self.cog, self.challenger, self.challenged)
        game.message = await self.ctx.send(embed=game.make_embed(), view=game)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged.id:
            return await interaction.response.send_message(
                embed=self.cog._embed(
                    "", f"<a:sword_spin:1211611749426667560> {interaction.user.mention}: This challenge is not for you.",
                    self.ctx, include_author=False
                ),
                ephemeral=True
            )
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None,
            embed=self.cog._embed(
                "", f"<a:sword_spin:1211611749426667560> **{self.challenged.name}** declined the challenge.",
                self.ctx, include_author=False
            ),
            view=None
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content=None,
                embed=self.cog._embed(
                    "", f"<a:sword_spin:1211611749426667560> Challenge expired. **{self.challenged.name}** did not respond.",
                    self.ctx, include_author=False
                ),
                view=None
            )
        except:
            pass
        self.stop()

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = 0x2f3136

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
    
    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, member: discord.Member = None):
        prefix = ctx.prefix

        if member is None:
            embed = self._embed(
                "command: tictactoe",
                "Challenge a member to a Tic-Tac-Toe game", ctx
            )
            embed.add_field(
                name="Aliases",
                value="`ttt`",
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}tictactoe <member>\n\u001b[35mexample: \u001b[0m{prefix}tictactoe @zeph```",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        if member == ctx.author:
            return await ctx.send(embed=self._embed(
                "", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: You cannot challenge yourself.",
                ctx, include_author=False
            ))

        if member.bot:
            return await ctx.send(embed=self._embed(
                "", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: You cannot challenge a bot.",
                ctx, include_author=False
            ))
        
        challenge_view = TicTacToeChallenge(ctx, self, ctx.author, member)
        challenge_view.message = await ctx.send(
            content=member.mention,
            embed=self._embed(
                "Tic-Tac-Toe",
                f"**{ctx.author.name}** is challenging you to a game!\nYou have **30 seconds** to respond.",
                ctx, include_author=False
            ), view=challenge_view
        )

async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
    print("TicTacToe cog loaded.")


