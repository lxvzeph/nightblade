import discord
from discord.ext import commands
import json
import os

BASE_DIR = os.getcwd()
AUTORESP_FILE = os.path.join(BASE_DIR, "autoresponders.json")


# ---------------------------------------------------------
# Load + Save Helpers
# ---------------------------------------------------------

def load_autoresponders():
    if not os.path.exists(AUTORESP_FILE):
        return {}
    with open(AUTORESP_FILE, "r") as f:
        return json.load(f)

def save_autoresponders(data):
    with open(AUTORESP_FILE, "w") as f:
        json.dump(data, f, indent=4)


autoresponders = load_autoresponders()


def get_guild_autoresponders(guild_id):
    return autoresponders.setdefault(str(guild_id), {})

def set_autoresponder(guild_id, trigger, response):
    guild_data = get_guild_autoresponders(guild_id)
    guild_data[trigger.lower()] = response
    save_autoresponders(autoresponders)

def remove_autoresponder(guild_id, trigger):
    guild_data = get_guild_autoresponders(guild_id)
    t = trigger.lower()
    if t in guild_data:
        del guild_data[t]
        save_autoresponders(autoresponders)
        return True
    return False





# ---------------------------------------------------------
# THE COG
# ---------------------------------------------------------

class AutoResponder(commands.Cog):

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

    def get_aliases_string(self, command):
        if not command.aliases:
            return "`n/a`"
        return ", ".join(f"{a}" for a in command.aliases)

    def alss_ctx(self, ctx):
        cmd = self.bot.get_command(ctx.command.name)
        return self.get_aliases_string(cmd)

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

    @staticmethod
    def perms_ctx(ctx):
        if ctx.command.name == "autoresponder":
            return "`Manage Messages`"
        return "`n/a`"

    async def _download_file(self, url: str):
        import aiohttp, io
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
        return io.BytesIO(data)


    # Autoresponder Trigger System
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        import re
        URL_REGEX = re.compile(r"^https?://\S+\.(?:gif|mp4|png|jpg|jpeg|webp)$", re.IGNORECASE)


        if message.author.bot or not message.guild:
            return

        guild_data = autoresponders.get(str(message.guild.id), {})

        content = message.content.lower()

        for trigger, response in guild_data.items():
            if trigger in content:
                if isinstance(response, str):
                    text = response
                    attachment_url = None
                else:
                    text = response.get("text") or ""
                    attachment_url = response.get("attachment")

                if text.startswith("react: "):
                    emoji = text[7:].strip()
                    try:
                        await message.add_reaction(emoji)
                    except:
                        pass
                    return

                if text.strip() and URL_REGEX.match(text.strip()):
                    await message.channel.send(text.strip())
                    return

                if attachment_url:
                    filedata = await self._download_file(attachment_url)
                    filedata.seek(0)
                    filename = response.get("filename", "attachment.png")
                    file = discord.File(filedata, filename=filename)

                    if text:
                        await message.channel.send(text, file=file)
                    else:
                        await message.channel.send(file=file)
                    return
                if text:
                    await message.channel.send(text)
                return



    # ---------------------------------------------------------
    # Command Group: autoresponder
    # ---------------------------------------------------------

    @commands.command(aliases=["aresp"])
    @commands.has_permissions(manage_messages=True)
    async def autoresponder(self, ctx, action=None, trigger=None, *, response=None):
        prefix = ctx.prefix

        # No action provided
        if action is None:
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
                value=self.perms_ctx(ctx),
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
            return await ctx.send(embed=embed)

        action = action.lower()

        # ---------------------------------------------------
        # ADD
        # ---------------------------------------------------
        if action == "add":
            if not ctx.author.guild_permissions.manage_messages:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You need `Manage Messages` to use this action.",
                        ctx,
                        include_author=False
                    )
                )

            if trigger is None or (response is None and not ctx.message.attachments):
                embed = self._embed(
                    "command: autoresponder add",
                    "Sets an autoresponder",
                    ctx
                )
                embed.add_field(
                    name="**Aliases**",
                    value=f"`{self.alss_ctx(ctx)} add`",
                    inline=False
                )
                embed.add_field(
                    name="**Permissions Required**",
                    value=self.perms_ctx(ctx),
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


            

            set_autoresponder(ctx.guild.id, trigger,
            {
                "text": response,
                "attachment": attachment_url,
                "filename": attachment_name
            })
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
            return await ctx.send(embed=embed)

        # ---------------------------------------------------
        # REMOVE
        # ---------------------------------------------------
        if action == "remove":
            if not ctx.author.guild_permissions.manage_messages:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You need `Manage Messages` to use this action.",
                        ctx,
                        include_author=False
                    )
                )
            if trigger is None:
                embed = self._embed(
                    "command: autoresponder remove",
                    "Removes an autoresponder",
                    ctx
                )
                embed.add_field(
                    name="**Aliases**",
                    value=f"`{self.alss_ctx(ctx)} remove`",
                    inline=False
                )
                embed.add_field(
                    name="**Permissions Required**",
                    value=self.perms_ctx(ctx),
                    inline=False
                )
                embed.add_field(
                    name="**Utilization**",
                    value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autoresponder remove <trigger>\n\u001b[35mexample:\u001b[0m {prefix}autoresponder remove hi```",
                    inline=False
                )
                return await ctx.send(embed=embed)

            removed = remove_autoresponder(ctx.guild.id, trigger)
            if removed:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Removed autoresponder for `{trigger}`.",
                        ctx,
                        include_author=False
                    )
                )
            else:
                return await ctx.send(
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
        if action == "edit":
            if not ctx.author.guild_permissions.manage_messages:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You need `Manage Messages` to use this action.",
                        ctx,
                        include_author=False
                    )
                )
            if trigger is None:
                embed = self._embed(
                    "command: autoresponder edit",
                    "Edits an existing autoresponder",
                    ctx
                )
                embed.add_field(
                    name="**Aliases**",
                    value=f"`{self.alss_ctx(ctx)} remove`",
                    inline=False
                )
                embed.add_field(
                    name="**Permissions Required**",
                    value=self.perms_ctx(ctx),
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

            guild_data = get_guild_autoresponders(ctx.guild.id)
            if trigger.lower() not in guild_data:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponder found for `{trigger}`.",
                        ctx,
                        include_author=False
                    )
                )

            key = trigger.lower()

            if key not in guild_data:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponder found for `{trigger}`.",
                        ctx,
                        include_author=False
                    )
                )

            old = guild_data[key]

            if isinstance(old, str):
                old_text = old
                old_attachment = None
                old_filename = None
            else:
                old_text = old.get("text")
                old_attachment = old.get("attachment")
                old_filename = old.get("filename")

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

            autoresponders[str(ctx.guild.id)][key] = {
                "text": new_text,
                "attachment": new_attachment,
                "filename": new_filename
            }
            save_autoresponders(autoresponders)

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
                
            return await ctx.send(embed=embed)

        # ---------------------------------------------------
        # LIST
        # ---------------------------------------------------
        if action == "list":
            guild_data = get_guild_autoresponders(ctx.guild.id)

            if not guild_data:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No autoresponders found in this server.",
                        ctx,
                        include_author=False
                    )
                )

            lines = "\n".join([f"{k} → {v}" for k, v in guild_data.items()])
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: List of all autoresponders:\n\n```{lines}```",
                    ctx,
                    include_author=False
                )
            )

        # ---------------------------------------------------
        # INVALID ACTION
        # ---------------------------------------------------
        await ctx.send(
            embed=self._embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Unknown action `{action}`.\nMust be: `add`, `remove`, `edit`, `list`.",
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



    