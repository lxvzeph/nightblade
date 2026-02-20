import discord
from discord.ext import commands


class ServerInfo(commands.Cog):
    """Server information command."""

    def __init__(self, bot: commands.Bot):
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

    @commands.command(aliases=["si"])
    async def serverinfo(self, ctx: commands.Context):
        """See server's info"""

        guild = ctx.guild
        if guild is None:
            return await ctx.send(embed=self._embed("", "This command can only be used in a server.", ctx, include_author=False))

        # ---- BASIC INFO ----
        owner = guild.owner
        created_at = discord.utils.format_dt(guild.created_at, style="F")
        verification = str(guild.verification_level).replace("_", " ").title()

        # ---- MEMBER COUNTS ----
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)

        # ---- GUILD RESOURCES ----
        roles_count = len(guild.roles)
        emojis_count = len(guild.emojis)
        stickers_count = len(guild.stickers)
        boosts = guild.premium_subscription_count
        tier = guild.premium_tier
        emoji_0 = "<:pge:1448561424946429952>"
        emoji_1 = "<:pgf:1448561387520659519>"

        boost_icons = [
            emoji_1 if tier >= 1 else emoji_0,
            emoji_1 if tier >= 2 else emoji_0,
            emoji_1 if tier >= 3 else emoji_0
        ]

        boost_icon_string = "".join(boost_icons)

        # ---- SHARD INFO ----
        shard_id = guild.shard_id if guild.shard_id is not None else 0

        # ---- BUILD EMBED ----
        embed = self._embed(
            "",
            f"Launched on {created_at}",
            ctx
        )

        embed.set_author(name=f"{guild.name} ({guild.id})")

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Owner
        embed.add_field(
            name="**Owned by**",
            value=f"{owner.mention if owner else 'Unknown'}",
            inline=True
        )

        # Verification Level
        embed.add_field(
            name="**Verification**",
            value=verification,
            inline=True
        )
        embed.add_field(
            name="**Boosts**",
            value=(
                f"Total: `{boosts}`\n"
                f"Boosters: `{len(guild.premium_subscribers)}`\n"
                f"{boost_icon_string}"
            ),
            inline=True
        )

        # Member Stats
        embed.add_field(
            name=f"**Members**",
            value=f"All: `{guild.member_count}`\nHumans: `{humans}`\nBots: `{bots}`",
            inline=True
        )
        embed.add_field(
            name="**Channels**",
            value=(
                f"Category: `{len(guild.categories)}`\n"
                f"Text: `{len(guild.text_channels)}`\n"
                f"Voice: `{len(guild.voice_channels)}`"
            ),
            inline=True
        )

        # Other Stats
        embed.add_field(
            name="**Stats**",
            value=(
                f"Roles: `{roles_count}`\n"
                f"Emojis: `{emojis_count}`\n"
                f"Stickers: `{stickers_count}`"
            ),
            inline=True
        )

        embed.set_footer(text=f"Shard: {shard_id}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))
    print("ServerInfo loaded.")
