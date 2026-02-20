# cogs/license.py
import random
import string
import asyncio
import discord
from discord.ext import commands
from data.licenses import (
    get_license,
    get_all_keys,
    create_license,
    set_activated,
    delete_license
)

# >>> EDIT THESE BEFORE USE <<<
OFFICIAL_SERVER_ID = 1069850380114067487
AUTHORIZED_ROLE_IDS = [1125010550200471632, 1426420301578895493]
# ------------------------------

def generate_license_key(existing_keys=set()):
    chars = string.ascii_uppercase + string.digits
    while True:
        p1 = ''.join(random.choice(chars) for _ in range(4))
        p2 = ''.join(random.choice(chars) for _ in range(4))
        key = f"NGHT-{p1}-{p2}"
        if key not in existing_keys:
            return key

class License(commands.Cog):
    """License management cog: genkey, activate, licenseinfo, revoke, deactivate."""

    EMBED_COLOR = 0x2f3136

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_check(self._global_license_check)

    # ---------- helpers ----------
    def _all_keys(self):
        return get_all_keys()

    def _guild_is_activated(self, guild_id: int):
        entry = get_license(guild_id)
        return bool(entry and entry.get("activated"))

    def _embed(self, title: str = "", description: str = "", ctx: commands.Context | None = None,
               include_author: bool = False, color: int | None = None):
        """Create embed with bot author when include_author True. ctx optional."""
        color = color or self.EMBED_COLOR
        embed = discord.Embed(title=title, description=description, color=color)
        if include_author:
            try:
                bot_user = self.bot.user
                embed.set_author(name=bot_user.name, icon_url=bot_user.avatar.url if bot_user.avatar else None)
            except Exception:
                pass
        return embed

    # ---------- global check ----------
    async def _global_license_check(self, ctx: commands.Context):
        # allow non-command contexts
        if ctx.command is None:
            return True

        # allow DMs
        if ctx.guild is None:
            return True

        cmd_name = ctx.command.name.lower()

        # Always allow official server (staff can work there)
        if ctx.guild.id == OFFICIAL_SERVER_ID:
            return True

        # Always allow activate command anywhere
        if cmd_name == "activate":
            return True

        if cmd_name == "genkey":
            return True

        if cmd_name == "revoke":
            return True

        # If guild is activated, allow
        if self._guild_is_activated(ctx.guild.id):
            return True

        # Not activated: block (reply with consistent embed)
        embed = self._embed(
            description=f"<a:sword_spin:1211611749426667560>  This bot is not activated in this server, use `activate` to proceed.",
            include_author=False
        )
        # reply and then raise to block execution
        try:
            await ctx.send(embed=embed)
        except Exception:
            # swallow if reply fails
            pass
        raise commands.CheckFailure("Guild not activated")

    # ---------------- COMMANDS ----------------

    @commands.command()
    async def genkey(self, ctx: commands.Context, guild_id: int | None = None):
        """Generate a one-time key for a specific guild"""
        prefix = ctx.prefix

        # restrict to official server; global check already lets official server through,
        # but here we still guard to ensure this command used in official server context.
        if ctx.guild.id != OFFICIAL_SERVER_ID:
            embed = self._embed(
                description="<a:sword_spin:1211611749426667560>  This command only works in the official server.",
                include_author=False
            )
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(3)
            await msg.delete()
            return
        
        # syntax helper when missing arg
        if guild_id is None:
            embed = self._embed(
                title="command: genkey",
                description="Generate a one-time key for a specific guild",
                ctx=ctx,
                include_author=True
            )
            embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}genkey <serverID>\n\u001b[35mexample:\u001b[0m {prefix}genkey 18643710398134652```", inline=False)
            return await ctx.send(embed=embed)

        # role check for authorized staff
        author_role_ids = [r.id for r in ctx.author.roles]
        if not any(rid in author_role_ids for rid in AUTHORIZED_ROLE_IDS):
            embed = self._embed(description="You are not authorized to generate keys.", include_author=False)
            msg = await ctx.reply(embed=embed, mention_author=False)
            await asyncio.sleep(3)
            await msg.delete()
            return

        entry = get_license(guild_id)
        guild_obj = self.bot.get_guild(int(guild_id))

        if guild_obj is None:
            embed = self._embed("", "<a:sword_spin:1211611749426667560>  Cannot generate a key for a server I'm not in.", include_author=False)
            embed.set_footer(text=f"TIP:  Invite {self.bot.user.name} to a server before generating a key for it.")
            return await ctx.send(embed=embed)

        if entry:
            if entry.get("activated"):
                status = "Activated"
                embed = self._embed("", "A license already exists for that guild.", include_author=False)
                embed.set_author(name=f"{guild_obj.name}\n({guild_id})")
                embed.add_field(name="**Key**", value=f"```{entry['key']}```", inline=False)
                embed.add_field(name="**Status**", value=f"{status}", inline=False)
                return await ctx.send(embed=embed)

            if "key" in entry:
                key_display = entry["key"]

                status = "Activated" if entry.get("activated") else "Not activated"

                embed = self._embed("", "A license already exists for that guild.", include_author=False)
                embed.set_author(name=f"{guild_obj.name}\n({guild_id})")
                embed.add_field(name="**Key**", value=f"```{key_display}```", inline=False)
                embed.add_field(name="**Status**", value=f"{status}", inline=False)
                return await ctx.send(embed=embed)
        

        # create unique key and save
        key = generate_license_key(existing_keys=self._all_keys())
        create_license(guild_id, key)

        embed = self._embed(description=f"<a:sword_spin:1211611749426667560>  License key generated:\n\n```{key}\n```", include_author=False)
        embed.set_footer(text="TIP: Use activate <key> in your server.")
        await ctx.send(embed=embed)

    @commands.command()
    async def activate(self, ctx: commands.Context, key: str | None = None):
        """Activate the bot in your server using a license key."""
        prefix = ctx.prefix

        if key is None:
            embed = self._embed(title="command: activate", description=f"Activate **{self.bot.user.name}** in your server using a license key", ctx=ctx, include_author=True)
            embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}activate <license_key>\n\u001b[35mexample:\u001b[0m {prefix}activate NGHT-XXXX-XXXX```", inline=False)
            return await ctx.send(embed=embed)

        if ctx.guild is None:
            msg = await ctx.reply("Run this inside the server you want to activate.", mention_author=False)
            await asyncio.sleep(3)
            await msg.delete()
            return

        entry = get_license(ctx.guild.id)
        if not entry:
            embed = self._embed("", "<a:sword_spin:1211611749426667560>  This server does not have a license assigned.\n\nIf you believe this is a problem, contact support in the official server.", include_author=False)
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(3)
            await msg.delete()
            return

        if entry.get("activated"):
            embed = self._embed("", "<a:sword_spin:1211611749426667560>  This server is already activated.", include_author=False)
            return await ctx.send(embed=embed)
            

        if entry.get("key") != key:
            embed = self._embed("", "<a:sword_spin:1211611749426667560>  That key is invalid for this server.", include_author=False)
            return await ctx.send(embed=embed)

        set_activated(ctx.guild.id, True)
        embed = self._embed("LICENSE ACTIVATED", f"**{self.bot.user.name}** is now activated and fully-functional in this server.\n\nTo get started, see a list of commands by using `{prefix}commands`", include_author=True)
        embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_footer(text="Nox Aeternum")
        await ctx.send(embed=embed)
        

    @commands.command(aliases=["li"])
    async def licenseinfo(self, ctx: commands.Context, guild_id: int | None = None):
        """Show a server's license info or your own"""
        target_gid = str(guild_id if guild_id is not None else (ctx.guild.id if ctx.guild else None))
        if not target_gid:
            embed = self._embed(title="command: licenseinfo", description="Show a server's license info or your own", ctx=ctx, include_author=True)
            embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {ctx.prefix}licenseinfo <guild_id?>\n\u001b[35mexample:\u001b[0m {ctx.prefix}licenseinfo 18932678491324653```", inline=False)
            return await ctx.send(embed=embed)

        guild_obj = self.bot.get_guild(int(target_gid))
        entry = get_license(int(target_gid))
        if not entry:
            embed = self._embed(title="", description=f"<a:sword_spin:1211611749426667560>  No license assigned for guild `{guild_obj.name}`.", ctx=ctx, include_author=False)
            return await ctx.send(embed=embed)
            
        status = "Activated" if entry.get("activated") else "Not activated"
        key = entry.get("key", "—")
        embed = self._embed(color=discord.Color.from_str("#2f3136"))
        embed.set_author(name=f"{guild_obj.name}\n({guild_obj.id})")
        embed.set_thumbnail(url=guild_obj.icon.url)
        embed.add_field(name="**Key**", value=f"```{key}```", inline=False)
        embed.add_field(name="**Status**", value=f"{status}", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def revoke(self, ctx: commands.Context, guild_id: int | None = None):
        """Revoke and remove a license (official server staff only)"""
        if ctx.guild is None or ctx.guild.id != OFFICIAL_SERVER_ID:
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  This command only works in the official server.", include_author=False)
            return await ctx.send(embed=embed)

        author_role_ids = [r.id for r in ctx.author.roles]
        if not any(rid in author_role_ids for rid in AUTHORIZED_ROLE_IDS):
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  You do not have permission to revoke licenses.", include_author=False)
            return await ctx.send(embed=embed)

        if guild_id is None:
            embed = self._embed(title="command: revoke", description="Revoke and remove a license (official server staff only)", ctx=ctx, include_author=True)
            embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {ctx.prefix}revoke <guild_id>\n\u001b[35mexample:\u001b[0m {ctx.prefix}revoke 193827189325461822```", inline=False)
            return await ctx.send(embed=embed)

        guild_obj = self.bot.get_guild(int(guild_id))
        gid = str(guild_id)
        if not get_license(guild_id):
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  That guild does not have a license entry.", include_author=False)
            return await ctx.send(embed=embed)

        delete_license(guild_id)
        embed = self._embed(title="LICENSE REVOKED", description=f"License for server **{guild_obj.name}** has been revoked and removed.", include_author=True)
        embed.set_thumbnail(url=guild_obj.icon.url)
        embed.add_field(name="**Moderator**", value=f"{ctx.author.mention}")
        await ctx.send(embed=embed)

        embed2 = self._embed("LICENSE REVOKED", description=f"The license for this server has been revoked and **{self.bot.user.name}** is no longer functional.\n\nIf you believe this is a mistake, contact support in the official server.", include_author=True)
        embed2.set_footer(text="Bot license lost, A new one is needed.")
        embed2.set_thumbnail(url=guild_obj.icon.url)
        
        channel = guild_obj.system_channel

        if channel is None or not channel.permissions_for(guild_obj.me).send_messages:
            channel = discord.utils.get(guild_obj.text_channels, name="general")

        if channel is None or not channel.permissions_for(guild_obj.me).send_messages:
            for ch in guild_obj.text_channels:
                if ch.permissions_for(guild_obj.me).send_messages:
                    channel = ch
                    break

        if channel:
            try:
                await channel.send(embed=embed2)
            except:
                pass



    @commands.command(aliases=["dea"])
    async def deactivate(self, ctx: commands.Context, target_gid: int | None = None):
        """Deactivate a server's license for nightblade"""
        if ctx.guild is None or ctx.guild.id != OFFICIAL_SERVER_ID:
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  This command only works in the official server.", include_author=False)
            return await ctx.send(embed=embed)

        if not ctx.author.guild_permissions.manage_guild:
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  You need `Manage Server` permission to deactivate this guild's license.", include_author=False)
            return await ctx.send(embed=embed)

        if target_gid is None:
            embed = self._embed("command: deactivate", f"Deactivate a server's license for **{self.bot.user.name}**", include_author=True)
            embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {ctx.prefix}deactivate <serverID>\n\u001b[35mexample:\u001b[0m {ctx.prefix}deactivate 13871391345213453```")
            return await ctx.send(embed=embed)

        guild_obj = self.bot.get_guild(int(target_gid))
        entry = get_license(target_gid)
        if not entry:
            embed = self._embed(description=f"<a:sword_spin:1211611749426667560>  No license entry found for server ID `{target_gid}`.", include_author=False)
            return await ctx.send(embed=embed)
        if not entry.get("activated"):
            embed = self._embed(description="<a:sword_spin:1211611749426667560>  This guild is not currently activated.", include_author=False)
            return await ctx.send(embed=embed)

        set_activated(target_gid, False)

        embed = self._embed("LICENSE DEACTIVATED", description=f"The license for server **{guild_obj.name}** has been deactivated.", include_author=True)
        embed.add_field(name="**Moderator**", value=f"{ctx.author.mention}")
        embed.set_thumbnail(url=guild_obj.icon.url)
        await ctx.send(embed=embed)

        embed2 = self._embed("LICENSE DEACTIVATED", description=f"The license for this server has been deactivated and **{self.bot.user.name}** is no longer functional.\n\nIf you believe this is a mistake, contact support in the official server.", include_author=True)
        embed2.set_footer(text="Access to commands has been locked.")
        embed2.set_thumbnail(url=guild_obj.icon.url)
        
        channel = guild_obj.system_channel

        if channel is None or not channel.permissions_for(guild_obj.me).send_messages:
            channel = discord.utils.get(guild_obj.text_channels, name="general")

        if channel is None or not channel.permissions_for(guild_obj.me).send_messages:
            for ch in guild_obj.text_channels:
                if ch.permissions_for(guild_obj.me).send_messages:
                    channel = ch
                    break

        if channel:
            try:
                await channel.send(embed=embed2)
            except:
                pass

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(License(bot))
    print("License cog loaded.")