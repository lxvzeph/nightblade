import discord
from discord.ext import commands
import asyncio
from discord import app_commands
from data.sticky import (
     get_sticky,
     set_sticky,
     update_sticky_message_id,
     delete_sticky,
     get_all_stickies
)

class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sticky_messages = get_all_stickies()
        self.active_timers = {}
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

    def get_aliases_string(self, command):
        if not command.aliases:
            return "`n/a`"
        return ", ".join(f"{a}" for a in command.aliases)

    def alss_ctx(self, ctx):
        cmd = self.bot.get_command(ctx.command.name)
        return self.get_aliases_string(cmd)

    # ---------- PREFIX / SLASH BASE ----------
    @commands.hybrid_group(name="sticky", description="Manages sticky messages")
    @commands.has_permissions(manage_messages=True)
    async def sticky(self, ctx):
        """Sets a sticky message in a channel"""
        if ctx.invoked_subcommand is not None:
            return

        embed = self._embed(
            "command: sticky",
            "Sets a sticky message in a channel",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=self.alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="**Permissions Required**",
            value="`Manage Messages`",
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value="```ansi\n\u001b[35msyntax:\u001b[0m /sticky```",
            inline=False
        )
        await ctx.send(embed=embed)  # public instruction message

    # ---------- ADD ----------
    @sticky.command(name="add", description="Adds a sticky message to a channel.")
    @app_commands.describe(
    message="The message or message ID to set as a sticky message",
    channel="Channel to set the message in (optional)")
    @commands.has_permissions(manage_messages=True)
    async def sticky_add(self, ctx, *, message: str, channel: discord.TextChannel = None):
        """Sets a sticky message for a channel"""
        channel = channel or ctx.channel

        if not message:
            embed = self._embed(
                "command: sticky add",
                "Sets a sticky message for a channel",
                ctx
            )
            embed.add_field(
                name="**Aliases**",
                value=self.alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="**Permissions Required**",
                value="`Manage Messages`",
                inline=False
            )
            embed.add_field(
                name="**Utilization**",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m /sticky add <message> [channel]\n\u001b[35mexample:\u001b[0m /sticky add hello #general```",
                inline=False
            )
            return await ctx.send(embed=embed)

        # ----- 1 sticky per channel check -----
        if str(channel.id) in self.sticky_messages:
            embed = discord.Embed(
                description=f"<:xcross:1438691789379735612>  {channel.mention} Max amount of sticky message(s). Remove it first.",
                color=discord.Color.from_str("#963939")
            )
            if ctx.interaction:
                await ctx.reply(embed=embed, ephemeral=True)
            else:
                msg = await ctx.reply(embed=embed, mention_author=False)
                await asyncio.sleep(5)
                await msg.delete()
                await ctx.message.delete()
            return

        sent = None
        embeds = None
        files = None

        try:
            if message.isdigit():
                # ----- Copy message by ID -----
                msg_to_copy = await channel.fetch_message(int(message))
                content = msg_to_copy.content or None
                embeds = msg_to_copy.embeds if msg_to_copy.embeds else None
                files = [await a.to_file() for a in msg_to_copy.attachments] if msg_to_copy.attachments else None

                sent = await channel.send(content=content, embeds=embeds, files=files)

            else:
                # ----- Plain text input -----
                content = message
                sent = await channel.send(content)
                embeds = None
                files = None

            # ----- Save sticky info -----
            set_sticky(channel.id, content, [e.to_dict() for e in embeds] if embeds else [], [f.filename for f in files] if files else [], sent.id)
            self.sticky_messages[str(channel.id)] = {"content": content, "embeds": [e.to_dict() for e in embeds] if embeds else [], "attachments": [f.filename for f in files] if files else [], "message_id": sent.id}

        except discord.NotFound:
            embed = discord.Embed(
                description=f"<:xcross:1438691789379735612> Couldn't find that message ID.",
                color=discord.Color.from_str("#963939")
            )
            if ctx.interaction:
                await ctx.reply(embed=embed, ephemeral=True)
            else:
                msg = await ctx.reply(embed=embed, mention_author=False)
                await asyncio.sleep(5)
                await msg.delete()
                await ctx.message.delete()
            return

        # ----- Confirmation reply -----
        embed = discord.Embed(
            description=f"Sticky message set in {channel.mention}.",
            color=discord.Color.from_str("#71906e")
        )
        embed.set_footer(text="TIP: When using message ID, make sure to keep the original message.")
        
        if ctx.interaction:
            await ctx.reply(embed=embed, ephemeral=True)
        else:
            msg = await ctx.reply(embed=embed, mention_author=False)
            await asyncio.sleep(5)
            await msg.delete()
            await ctx.message.delete()

    # ---------- REMOVE ----------
    @sticky.command(name="remove", description="Removes the sticky message from a channel.")
    @app_commands.describe(
    channel="Channel to remove a sticky message from (optional)")
    @commands.has_permissions(manage_messages=True)
    async def sticky_remove(self, ctx, channel: discord.TextChannel = None):
        """Removes the sticky message from a channel"""
        channel = channel or ctx.channel
        if str(channel.id) not in self.sticky_messages:
            embed = discord.Embed(description="<:xcross:1438691789379735612>  No sticky message set for this channel.", color=discord.Color.from_str("#963939"))
            
            if ctx.interaction:
                await ctx.reply(embed=embed, ephemeral=True)
            else:
                msg = await ctx.reply(embed=embed, mention_author=False)
                await asyncio.sleep(5)
                await msg.delete()
                await ctx.message.delete()
            return
            
        data = self.sticky_messages[str(channel.id)]
        try:
            msg = await channel.fetch_message(data["message_id"])
            await msg.delete()
        except discord.NotFound:
            pass
            
        delete_sticky(channel.id)
        del self.sticky_messages[str(channel.id)]
        
        if channel.id in self.active_timers:
            self.active_timers[channel.id].cancel()
            del self.active_timers[channel.id]
            
        embed = discord.Embed(description=f"Sticky message removed in {channel.mention}.", color=discord.Color.from_str("#71906e"))
        
        if ctx.interaction:
            await ctx.reply(embed=embed, ephemeral=True)
        else:
            msg = await ctx.reply(embed=embed, mention_author=False)
            await asyncio.sleep(5)
            await msg.delete()
            await ctx.message.delete()



    # ---------- ON MESSAGE ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.startswith(";sticky"):
            return

        channel = message.channel

        if str(channel.id) not in self.sticky_messages:
            return

        sticky = self.sticky_messages[str(channel.id)]

        # ----- Delete the previous sticky message if it exists -----
        try:
            old_msg_id = sticky.get("message_id")
            if old_msg_id:
                old_msg = await channel.fetch_message(old_msg_id)
                await asyncio.sleep(5)
                await old_msg.delete()
        except discord.NotFound:
            pass  # If the old sticky was deleted manually, ignore
        
        # ----- Prepare embeds -----
        embeds = [discord.Embed.from_dict(e) for e in sticky.get("embeds", [])] if sticky.get("embeds") else None

        # ----- Prepare files (optional, extend if you want attachments) -----
        files = []

        # ----- Resend sticky -----
        sent = await channel.send(
            content=sticky.get("content"),
            embeds=embeds if embeds else None,
            files=files if files else None
        )

        # ----- Update sticky message ID -----
        update_sticky_message_id(channel.id, sent.id)
        sticky["message_id"] = sent.id  # keep in-memory dict in sync


async def setup(bot):
    await bot.add_cog(Sticky(bot))
    print("Sticky cog loaded.")