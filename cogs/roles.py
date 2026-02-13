import discord
from discord.ext import commands, tasks
from data.roles import backup_member_roles, get_member_role_backup, clear_member_role_backup

class Roles(commands.Cog):
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

    # --- HELPERS --------------------------------------------------------------

    def backup_member_roles(self, member: discord.Member):
        role_ids = [role.id for role in member.roles if role != member.guild.default_role]
        backup_member_roles(member.guild.id, member.id,  role_ids)

    async def restore_member_roles(self, member: discord.Member):

        role_ids = get_member_role_backup(member.guild.id, member.id)
        if role_ids is None:
            return False
        
        roles = [member.guild.get_role(rid) for rid in role_ids]
        roles = [r for r in roles if r is not None]

        try:
            await member.add_roles(*roles)
        except discord.Forbidden:
            return False
        
        return True

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            self.backup_member_roles(member)
        except Exception as e:
            print(f"[RoleTools] Failed to backup on member remove: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if get_member_role_backup(guild.id, user.id) is not None:
            return
        

    # --- STRIP COMMAND --------------------------------------------------------

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def strip(self, ctx, mode=None, member: discord.Member=None):
        """Strip roles from a member."""
        prefix = ctx.prefix  # change to your own prefix() resolver if needed

        if mode not in ("all", "staff"):
            embed = self._embed(
                "command: strip",
                "Strip a user off their role(s)",
                ctx
            )
            embed.add_field(
                name="**Aliases**",
                value=self.alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="**Subcommands**",
                value="`all`\n`staff`",
                inline=False
            )
            embed.add_field(
                name="**Utilization**",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}strip <all/staff> <member>\n\u001b[35mexample:\u001b[0m {prefix}strip all john```",
                inline=False
            )
            return await ctx.send(embed=embed)

        if member is None:
            embed = self._embed(
                f"command: strip {mode}",
                "Strip a user off their role(s)",
                ctx
            )
            embed.add_field(
                name="**Aliases**",
                value=self.alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="**Utilization**",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}strip {mode} <member>\n\u001b[35mexample:\u001b[0m {prefix}strip {mode} john```",
                inline=False
            )
            return await ctx.send(embed=embed)

        if member == ctx.author:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You cannot strip yourself.", ctx, include_author=False))

        # Hierarchy safety
        if member.top_role.position >= ctx.author.top_role.position:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You cannot strip **{member.name}** off their role(s) due to hierarchy.", ctx, include_author=False))

        if member.top_role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: **{member.name}** has a higher role than me.", ctx, include_author=False))

        # Backup before modifying
        self.backup_member_roles(member)

        if mode == "all":
            new_roles = [ctx.guild.default_role]

        else:  # mode == "staff"
            def is_staff(role: discord.Role):
                perms = role.permissions
                return (
                    perms.administrator or
                    perms.manage_guild or
                    perms.manage_messages or
                    perms.kick_members or
                    perms.ban_members
                )

            new_roles = [
                role for role in member.roles
                if role == ctx.guild.default_role or not is_staff(role)
            ]

        try:
            await member.edit(roles=new_roles)
            await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Stripped **{member.name}**'s roles (**{mode}**).", ctx, include_author=False))
        except discord.Forbidden:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: I don't have permission to modify their roles.", ctx, include_author=False))

    # --- RESTORE COMMAND ------------------------------------------------------

    @commands.command(aliases=["res"])
    @commands.has_permissions(manage_roles=True)
    async def restore(self, ctx, action=None, member: discord.Member=None):
        """Restore backed-up roles or clear backups."""

        prefix = ctx.prefix

        # --- CASE 1: No arguments -> show help
        if action is None and member is None:
            embed = self._embed(
                "command: restore",
                "Restores a member's role(s) or clears their backup",
                ctx
            )
            embed.add_field(name="**Aliases**", value=f"`{self.alss_ctx(ctx)}`", inline=False)
            embed.add_field(name="**Subcommands**", value="`clear`", inline=False)
            embed.add_field(
                name="**Utilization**",
                value=(
                    f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}restore <member>\n"
                    f"\u001b[35mexample:\u001b[0m {prefix}restore john\n\n"
                    f"\u001b[35msyntax:\u001b[0m {prefix}restore clear <member>\n"
                    f"\u001b[35mexample:\u001b[0m {prefix}restore clear john```"
                ),
                inline=False
            )
            return await ctx.send(embed=embed)

        # --- CASE 2: User typed "restore @member"
        # action contains @member, member is None
        if action != "clear" and member is None:
            # Try to interpret `action` as member
            try:
                member = await commands.MemberConverter().convert(ctx, action)
            except:
                return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Please specify a valid member.", ctx, include_author=False))

        # --- CASE 3: User typed "restore clear" with no member
        if action == "clear" and member is None:
            embed = self._embed(
                "command: restore clear",
                "Deletes a user's role backup",
                ctx
            )
            embed.add_field(name="**Aliases**", value=f"`{self.alss_ctx(ctx)}`", inline=False)
            embed.add_field(
                name="**Utilization**",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}restore clear <member>\n\u001b[35mexample:\u001b[0m {prefix}restore clear john```",
                inline=False
            )
            return await ctx.send(embed=embed)

        # --- Now we have a valid member object
        gid = str(ctx.guild.id)
        uid = str(member.id)

        # --- CASE 4: restore clear <member>
        if action == "clear":
            removed = clear_member_role_backup(ctx.guild.id, member.id)
            if not removed:
                return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No backup found for **{member.name}**.", ctx, include_author=False))

            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Cleared role backup for **{member.name}**.", ctx, include_author=False))

        # --- CASE 5: Normal restore <member>
        success = await self.restore_member_roles(member)

        if success:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Restored **{member.name}**'s roles.", ctx, include_author=False))
        else:
            return await ctx.send(embed=self._embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: No backup saved for **{member.name}** or failed to restore.", ctx, include_author=False))




        # ---------------- DEFAULT RESTORE ACTION ----------------
    

            
                


# --- SETUP --------------------------------------------------------------------

async def setup(bot):
    await bot.add_cog(Roles(bot))
    print("Role cog loaded.")
