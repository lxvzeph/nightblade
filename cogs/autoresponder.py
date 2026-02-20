import discord
from discord.ext import commands
from data.db import get_connection
import re
import aiohttp
import io

def fetch_autoresponders(guild_id: int):
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT trigger, response, attachment, filename
            FROM autoresponders
            WHERE guild_id = ?
            """,
            (str(guild_id),)
        )
        return cur.fetchall()


def insert_autoresponder(guild_id, trigger, text, attachment, filename):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO autoresponders
            (guild_id, trigger, response, attachment, filename)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(guild_id), trigger.lower(), text, attachment, filename)
        )


def delete_autoresponder(guild_id, trigger):
    with get_connection() as conn:
        cur = conn.execute(
            """
            DELETE FROM autoresponders
            WHERE guild_id = ? AND trigger = ?
            """,
            (str(guild_id), trigger.lower())
        )
        return cur.rowcount > 0
    
def get_single_autoresponder(guild_id, trigger):
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT response, attachment, filename
            FROM autoresponders
            WHERE guild_id = ? AND trigger = ?
            """,
            (str(guild_id), trigger.lower())
        )
        return cur.fetchone()

# ---------------------------------------------------------
# THE COG
# ---------------------------------------------------------

class AutoResponder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.EMBED_COLOR = 0x2f3136

    async def _download_file(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
        return io.BytesIO(data)

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
        return self.get_aliases_string(ctx.command)

    @staticmethod
    def format_permission(perm: str):
        return perm.replace("_", " ").title()

    @staticmethod
    def command_permissions(cmd):
        if not cmd.checks:
            return []

        perms = []

        for check in cmd.checks:
            if hasattr(check, "permissions"):
                for perm, value in check.permissions.items():
                    if value:
                        perms.append(
                            AutoResponder.format_permission(perm)
                        )

        return perms
    
    # Autoresponder Trigger System
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        content = message.content.lower()
        rows = fetch_autoresponders(message.guild.id)

        URL_REGEX = re.compile(r"^https?://\S+\.(?:gif|mp4|png|jpg|jpeg|webp)$", re.IGNORECASE)

        for trigger, text, attachment, filename in rows:
            if trigger not in content:
                continue

            if text and text.startswith("react: "):
                emoji = text[7:].strip()
                try:
                    await message.add_reaction(emoji)
                except:
                    pass
                return
            
            if text and URL_REGEX.match(text.strip()):
                await message.channel.send(text.strip())
                return
            
            if attachment:
                filedata = await self._download_file(attachment)
                filedata.seek(0)
                file = discord.File(filedata, filename=filename or "attachment")

                if text:
                    await message.channel.send(content=text, file=file)
                else:
                    await message.channel.send(file=file)
                return
            
            if text:
                await message.channel.send(text)
                return

    # ---------------------------------------------------------
    # Command Group: autoresponder
    # ---------------------------------------------------------

    @commands.group(aliases=["aresp"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def autoresponder(self, ctx):
        """Configures an autoresponder system"""
        prefix = ctx.prefix

        # No action provided
        
        embed = self._embed(
            "command: autoresponder",
            "Configures an autoresponder system",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=f"`{self.alss_ctx(ctx)}`",
            inline=False
        )
        embed.add_field(
            name="**Permissions Required**",
            value="`Manage Messages`",
            inline=False
        )
        embed.add_field(
            name="**Subcommands**",
            value="`add`\n`remove`\n`edit`\n`list`",
            inline=False
        )
        embed.add_field(
            name="**Parameters**",
            value="`trigger`\n`response`",
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder <subcommand> <parameters>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder add hi hello```",
            inline=False
        )
        embed.set_footer(
            text="TIP: Use 'react: <emoji>' in '<response>' for a reaction response. You can use links or attach a file."
        )
        await ctx.send(embed=embed)

        # ---------------------------------------------------
        # ADD
        # ---------------------------------------------------
    @autoresponder.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def autoresponder_add(self, ctx, trigger: str = None, *, response: str = None):
        """Sets an autoresponder
        example: autoresponder add hi hello"""
        prefix = ctx.prefix

        if trigger is None or (response is None and not ctx.message.attachments):
            embed = self._embed(
                "command: autoresponder add",
                "Sets an autoresponder",
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
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder add <trigger> <response>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder add hi hello```",
                inline=False
            )
            embed.set_footer(
                text="TIP: Use 'react: <emoji>' in '<response>' for a reaction response."
            )
            return await ctx.send(embed=embed)

        attachment_url = None
        attachment_name = None

        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            attachment_url = attachment.url
            attachment_name = attachment.filename

        insert_autoresponder(
            ctx.guild.id,
            trigger,
            response,
            attachment_url,
            attachment_name
        )

        embed = self._embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Successfully added autoresponder:",
            ctx,
            include_author=False
        )
        embed.add_field(
            name="**Trigger**",
            value=f"`{trigger}`",
            inline=False
        )
        embed.add_field(
            name="**Response**",
            value=f"`{response or 'Attachment Only'}`",
            inline=False
        )
        await ctx.send(embed=embed)            

        # ---------------------------------------------------
        # REMOVE
        # ---------------------------------------------------

    @autoresponder.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def autoresponder_remove(self, ctx, trigger: str = None):
        """Removes an autoresponder
        example: autoresponder remove hi"""
        prefix = ctx.prefix

        if trigger is None:
            embed = self._embed(
                "command: autoresponder remove",
                "Removes an autoresponder",
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
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder remove <trigger>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder remove hi```",
                inline=False
            )
            return await ctx.send(embed=embed)

        removed = delete_autoresponder(ctx.guild.id, trigger)
        if removed:
            await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Removed autoresponder for `{trigger}`.",
                    ctx,
                    include_author=False
                )
            )
        else:
            await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponder found for `{trigger}`.",
                    ctx,
                    include_author=False
                )
            )
        

        # ---------------------------------------------------
        # EDIT
        # ---------------------------------------------------
    @autoresponder.command(name="edit")
    @commands.has_permissions(manage_messages=True)
    async def autoresponder_edit(self, ctx, trigger: str = None, *, response: str = None):
        """Edits an existing autoresponder
        example: autoresponder edit hi greetings"""
        prefix = ctx.prefix

        if trigger is None:
            embed = self._embed(
                "command: autoresponder edit",
                "Edits an existing autoresponder",
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
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder edit <trigger> <new_response>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder edit hi greetings```",
                inline=False
            )
            embed.set_footer(
                text="TIP: Use 'react: <emoji>' in '<response>' for a reaction response."
            )
            return await ctx.send(embed=embed)

        old = get_single_autoresponder(ctx.guild.id, trigger)
        if not old:
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponder found for `{trigger}`.",
                    ctx,
                    include_author=False
                )
            )

        old_text, old_attachment, old_filename = old

        new_text = response if response is not None else old_text
        new_attachment = old_attachment
        new_filename = old_filename

        if ctx.message.attachments:
            att = ctx.message.attachments[0]
            new_attachment = att.url
            new_filename = att.filename

        if new_text is None and not ctx.message.attachments:
            embed = self._embed(
                "command: autoresponder edit",
                "Edits an existing autoresponder",
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
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder edit <trigger> <new_response>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder edit hi greetings```",
                inline=False
            )
            return await ctx.send(embed=embed)

        insert_autoresponder(
            ctx.guild.id,
            trigger,
            new_text,
            new_attachment,
            new_filename
        )

        embed = self._embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Updated autoresponder:",
            ctx,
            include_author=False
        )
        embed.add_field(
            name="**Trigger**",
            value=f"`{trigger}`",
            inline=False
        )
        embed.add_field(
            name="**New response**",
            value=f"`{new_text or 'attachment'}`",
            inline=False
        )
        if new_attachment:
            embed.add_field(
                name="**Attachment**",
                value=f"[{new_filename}]({new_attachment})",
                inline=False
            )
            
        await ctx.send(embed=embed)

        # ---------------------------------------------------
        # LIST
        # ---------------------------------------------------
    @autoresponder.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def autoresponder_list(self, ctx):
        """See a list of all autoresponders"""
        rows = fetch_autoresponders(ctx.guild.id)

        if not rows:
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponders found in this server.",
                    ctx,
                    include_author=False
                )
            )

        lines = "\n".join(f"{trigger} → {text or '[attachment]'}" for trigger, text, _, _ in rows)
        await ctx.send(
            embed=self._embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: List of all autoresponders:\n\n```{lines}```",
                ctx,
                include_author=False
            )
        )

# ---------------------------------------------------------
# SETUP
# ---------------------------------------------------------

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
    print("Autoresponder cog loaded.")



    