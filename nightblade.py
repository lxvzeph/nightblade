import discord
import json
import os
import random
import asyncio
import psutil
import pytz
import time
import aiohttp
from deep_translator import GoogleTranslator, single_detection
from deep_translator.exceptions import LanguageNotSupportedException
from discord import app_commands
from discord.ext import commands
from discord.utils import get
from data.db import init_db
from data.prefixes import (
    get_prefix_for_guild,
    set_prefix_for_guild,
    delete_prefix_for_guild
)
from data.imute import (
    get_imute_role_id,
    set_imute_role_id,
    delete_imute_role,
)
from data.rmute import (
    get_rmute_role_id,
    set_rmute_role_id,
    delete_rmute_role,
)
from data.cases import (
    create_case,
    get_case,
    get_cases_for_member,
    remove_case,
    clear_member_cases,
    get_all_cases
)
from data.warnings import (
    add_warning,
    get_warnings,
    remove_warning,
    clear_warnings
)
from data.autoroles import (
    get_autorole,
    set_autorole,
    delete_autorole
)
from data.jail import (
    get_jail_config,
    set_jail_config,
    delete_jail_config
)
from data.commands import (
    get_disabled_commands,
    disable_command,
    enable_command,
    is_command_disabled,
    is_command_disabled_serverwide,
    is_command_disabled_in_channel,
    get_restrictions,
    get_all_restrictions,
    add_restriction,
    remove_restriction,
    clear_command_restrictions
)
from data.forcename import get_forced_nickname, set_forced_nickname, remove_forced_nickname, get_all_forced_in_guild
from datetime import datetime, timezone, timedelta
from discord.ext.commands import BucketType, MemberConverter, BadArgument
from discord.ui import View, Button

init_db()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
		
def get_prefix(bot, message):
    if message.guild:
        return get_prefix_for_guild(message.guild.id)  # default prefix ";"
    return ";"  # default in DM

def p(ctx):
	return get_prefix(bot, ctx.message)

bot = commands.Bot(command_prefix=get_prefix, intents=intents)
bot.remove_command('help')
        
@bot.event
async def on_guild_remove(guild):
    delete_prefix_for_guild(guild.id)
    clear_command_restrictions(guild.id)

	

# Updated create_embed that works for both ctx and message, optional author

EMBED_COLOR = 0x2f3136 # default color

def create_embed(title, description, ctx_or_msg, include_author=True, color=None):
    try:
        bot_avatar = ctx_or_msg.bot.user.avatar.url
    except AttributeError:
        bot_avatar = ctx_or_msg.guild.me.avatar.url if ctx_or_msg.guild else None

    # Decide final color
    final_color = discord.Color(color) if isinstance(color, int) else color
    if final_color is None:
        final_color = discord.Color(EMBED_COLOR)

    embed = discord.Embed(
        title=title if title else "",
        description=description,
        color=final_color
    )

    if include_author and bot_avatar:
        if getattr(ctx_or_msg, "guild", None):
            bot_display_name = ctx_or_msg.guild.me.display_name
        else:
            bot_display_name = ctx_or_msg.bot.user.display_name

        embed.set_author(name=bot_display_name, icon_url=bot_avatar)

    return embed

# -----------------------------
# Events
# -----------------------------
async def load_extensions():
    await bot.load_extension("cogs.sticky")
    await bot.load_extension("cogs.snipe")
    await bot.load_extension("cogs.license")
    await bot.load_extension("cogs.autoresponder")
    await bot.load_extension("cogs.roles")
    await bot.load_extension("cogs.timezone")
    await bot.load_extension("cogs.serverinfo")
    await bot.load_extension("cogs.flag")
    await bot.load_extension("cogs.blacktea")
    await bot.load_extension("cogs.tictactoe")
    
loaded = False

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=";help"))
    global loaded
    if not loaded:
        await load_extensions()
        loaded = True
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash commands as {bot.user}")
    print(f"{bot.user} is online.")

# -----------------------------
# Moderation commands
# -----------------------------

def get_aliases_string(command):
    if not command.aliases:
        return "`n/a`"
    return ", ".join(f"`{a}`" for a in command.aliases)
    
def alss_ctx(ctx):
    return get_aliases_string(ctx.command)
    
def find_general_channel(guild):
    # 1. Exact match for a "general" channel
    for name in ["general", "chat", "lounge", "main", "welcome"]:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel and channel.permissions_for(guild.me).send_messages:
            return channel

    # 2. Fallback to system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        return guild.system_channel

    # 3. Fallback to any sendable channel
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            return channel

    return None  # No valid channel

def resolve_role(guild, value: str):
    # Mention
    if value.startswith("<@&") and value.endswith(">"):
        try:
            return guild.get_role(int(value[3:-1]))
        except:
            pass

    # ID
    try:
        rid = int(value)
        role = guild.get_role(rid)
        if role:
            return role
    except:
        pass

    # Exact name
    role = discord.utils.get(guild.roles, name=value)
    if role:
        return role

    # Partial name (case-insensitive)
    value_lower = value.lower()
    for r in guild.roles:
        if value_lower in r.name.lower():
            return r

    return None

def resolve_channel(guild, value: str):
    # Mention
    if value.startswith("<#") and value.endswith(">"):
        try:
            return guild.get_channel(int(value[2:-1]))
        except:
            pass

    # ID
    try:
        cid = int(value)
        channel = guild.get_channel(cid)
        if channel:
            return channel
    except:
        pass

    # Exact name
    channel = discord.utils.get(guild.channels, name=value)
    if channel:
        return channel

    # Partial name
    value_lower = value.lower()
    for c in guild.channels:
        if value_lower in c.name.lower():
            return c

    return None

async def resolve_user(ctx, value: str):
    # Mention
    if value.startswith("<@") and value.endswith(">"):
        try:
            uid = int(value.strip("<@!>"))
            return await ctx.bot.fetch_user(uid)
        except:
            pass

    # ID
    try:
        return await ctx.bot.fetch_user(int(value))
    except:
        pass

    # Try guild member by partial match
    value_lower = value.lower()
    for m in ctx.guild.members:
        if value_lower in m.name.lower() or value_lower in m.display_name.lower():
            return m

    return None


# ===================
# COMMAND MANAGEMENT
# ===================


@bot.check
async def command_restriction_check(ctx):
    if not ctx.guild:
        return True  # ignore DMs

    gid = ctx.guild.id
    cmd = ctx.command.name

    if is_command_disabled_serverwide(gid, cmd):
        embed = create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: The command `{cmd}` is disabled in this server.\n",
            ctx,
            include_author=False,
            color=0x2f3136
        )
        await ctx.send(embed=embed)
        return False
    
    if is_command_disabled_in_channel(gid, cmd, ctx.channel.id):
        await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: `{cmd}` is disabled in this channel.",
            ctx, include_author=False
        ))
        return False

    # 2. RESTRICTIONS
    restrict = get_restrictions(gid, cmd)

    # Role restriction
    if restrict["roles"]:
        if not any(r.id in restrict["roles"] for r in ctx.author.roles):
            e = create_embed("", f"{ctx.author.mention}: **You** do not have the required role to use `{cmd}`.", ctx, include_author=False, color=0x2f3136)
            await ctx.send(embed=e)
            return False

    # Channel restriction
    if restrict["channels"]:
        if ctx.channel.id not in restrict["channels"]:
            e = create_embed("", f"{ctx.author.mention}: `{cmd}` is not allowed in this channel.", ctx, include_author=False, color=0x2f3136)
            await ctx.send(embed=e)
            return False

    # User restriction
    if restrict["users"]:
        if ctx.author.id not in restrict["users"]:
            e = create_embed("", f"{ctx.author.mention}: You are not allowed to use `{cmd}`.", ctx, include_author=False, color=0x2f3136)
            await ctx.send(embed=e)
            return False

    return True

def has_higher_role(author: discord.Member, target: discord.Member | discord.Role):
    """Returns True if author has permission to restrict target, False otherwise."""

    # If author is owner, always allowed
    if isinstance(author, discord.Member) and author.guild.owner_id == author.id:
        return True

    # If target is a ROLE
    if isinstance(target, discord.Role):
        # Role has ADMIN?
        if target.permissions.administrator:
            return False

        # Target role is above author’s highest role?
        if target.position >= author.top_role.position:
            return False

        return True

    # If target is a USER
    if isinstance(target, discord.Member):
        # User has ADMIN?
        if target.guild_permissions.administrator:
            return False

        # Target member has equal or higher role
        if target.top_role.position >= author.top_role.position:
            return False

        return True

    return False


@bot.command(aliases=["ec"])
@commands.has_permissions(manage_guild=True)
async def enablecommand(ctx, command_name: str = None, channel_input: str = None):
    """Enables a command server-wide or in specific channels"""
    prefix = p(ctx)

    if not command_name:
        embed = create_embed(
            "command: enablecommand",
            "Enables a command server-wide or in specific channels",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="**Permissions Required**",
            value="`Manage Server`",
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}enablecommand <command> (channel)\n\u001b[35mexample:\u001b[0m {prefix}enablecommand avatar #chat```",
            inline=False
        )
        return await ctx.send(embed=embed)

    command = command_name.strip()
    cmd_obj = bot.get_command(command)
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Unknown command `{command}`. Use `{prefix}commands` for help.",
                ctx, include_author=False
            ))
    
    full_name = cmd_obj.name
    gid = ctx.guild.id

    if channel_input:
        channel = resolve_channel(ctx.guild, channel_input)
        if not channel:
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Channel not found.",
                ctx, include_author=False
            ))
        
        if not is_command_disabled_in_channel(gid, full_name, channel.id):
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: `{full_name}` is not disabled in {channel.mention}.",
                ctx, include_author=False
            ))
        
        enable_command(gid, full_name, channel.id)
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: `{full_name}` has been enabled in {channel.mention}.",
            ctx, include_author=False, color=0x71906e
        ))

    if not is_command_disabled_serverwide(gid, full_name):
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `{full_name}` is already enabled.",
        ctx,
        include_author=False))

    enable_command(gid, full_name)
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Command `{full_name}` has been enabled.",
    ctx,
    include_author=False,
    color=0x71906e))

@bot.command(aliases=["dc"])
@commands.has_permissions(manage_guild=True)
async def disablecommand(ctx, command_name: str = None, channel_input: str = None):
    """Disables a command server-wide or in specific channels"""
    prefix = p(ctx)

    if not command_name:
        embed = create_embed(
            "command: disablecommand",
            "Disables a command server-wide or in specific channels",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="**Permissions Required**",
            value="`Manage Server`",
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}disablecommand <command> (channel)\n\u001b[35mexample:\u001b[0m {prefix}disablecommand avatar #chat```",
            inline=False
        )
        return await ctx.send(embed=embed)

    command = command_name.strip()
    cmd_obj = bot.get_command(command)
    if not cmd_obj:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Unknown command: `{command}`. Use `{prefix}commands` for help.",
        ctx,
        include_author=False))

    full_name = cmd_obj.name
    gid = ctx.guild.id

    protected = {"enablecommand", "disablecommand", "restrict", "unrestrict"}
    if full_name in protected:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: `{full_name}` cannot be disabled.",
            ctx, include_author=False
        ))
    
    if channel_input:
        channel = resolve_channel(ctx.guild, channel_input)
        if not channel:
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Channel not found.",
                ctx, include_author=False
            ))
        
        if is_command_disabled_in_channel(gid, full_name, channel.id):
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: `{full_name}` is already disabled in {channel.mention}.",
                ctx, include_author=False
            ))
        
        disable_command(gid, full_name, channel.id)
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: `{full_name}` has been disabled in {channel.mention}.",
            ctx, include_author=False, color=0x963939
        ))

    if is_command_disabled_serverwide(gid, full_name):
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `{full_name}` is already disabled.",
        ctx,
        include_author=False))

    disable_command(gid, full_name)
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Command `{full_name}` has been disabled.",
    ctx,
    include_author=False,
    color=0x963939))

@bot.group(aliases=["rc"], invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def restrict(ctx):
    """Restricts a command to specific roles, channels, or users"""
    prefix = p(ctx)
    embed = create_embed("command: restrict", "Restricts a command to specific roles, channels, or users", ctx)
    embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
    embed.add_field(
        name="**Permissions Required**",
        value="`Manage Server`",
        inline=False
    )
    embed.add_field(
        name="**Subcommands**",
        value="`role`\n`channel`\n`user`\n`list`",
        inline=False
    )
    embed.add_field(
        name="**Utilization**",
        value=(
            f"```ansi\n\u001b[35msyntax:\u001b[0m\n"
            f"{prefix}restrict role <role> <command>\n"
            f"{prefix}restrict channel <channel> <command>\n"
            f"{prefix}restrict user <user> <command>\n"
            f"{prefix}restrict list <command>```"
        ),
        inline=False
    )
    return await ctx.send(embed=embed)

@restrict.command(name="role")
@commands.has_permissions(manage_guild=True)
async def restrict_role(ctx, role_input: str = None, *, command_name: str = None):
    """Restricts a command to specific roles"""
    prefix = p(ctx)

    if not role_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a role and a command.\nUsage: `{prefix}restrict role <role> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command `{command_name}`. Use `{prefix}commands` for help.",
            ctx, include_author=False
        ))
    
    full_name = cmd_obj.name
    role = resolve_role(ctx.guild, role_input)
    if not role:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Role not found.", ctx, include_author=False))
    
    if not has_higher_role(ctx.author, role):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Cannot restrict `{full_name}` to {role.mention} due to hierarchy.",
            ctx, include_author=False
        ))
    
    settings = get_restrictions(ctx.guild.id, full_name)
    if role.id in settings["roles"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: {role.mention} is already on the allowlist for `{full_name}`", ctx, include_author=False))
    
    add_restriction(ctx.guild.id, full_name, "role", role.id)
    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: `{full_name}` is now restricted to {role.mention}.",
        ctx, include_author=False, color=0xf9c414
    ))

@restrict.command(name="channel")
@commands.has_permissions(manage_guild=True)
async def restrict_channel(ctx, channel_input: str = None, *, command_name: str = None):
    """Restricts a command to specific channels"""
    prefix = p(ctx)

    if not channel_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a channel and a command.\nUsage: `{prefix}restrict channel <channel> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command `{command_name}`. Use `{prefix}commands` for help.",
            ctx, include_author=False
        ))
    
    full_name = cmd_obj.name
    channel = resolve_channel(ctx.guild, channel_input)
    if not channel:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Channel not found.", ctx, include_author=False))
    
    settings = get_restrictions(ctx.guild.id, full_name)
    if channel.id in settings["channels"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {channel.mention} is already on the allowlist for `{full_name}`.", ctx, include_author=False))
    
    add_restriction(ctx.guild.id, full_name, "channel", channel.id)
    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: `{full_name}` is now restricted to {channel.mention}.",
        ctx, include_author=False, color=0xf9c414
    ))

@restrict.command(name="user")
@commands.has_permissions(manage_guild=True)
async def restrict_user(ctx, user_input: str = None, *, command_name: str = None):
    """Restricts a command to specific users"""
    prefix = p(ctx)

    if not user_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a user and a command.\nUsage: `{prefix}restrict user <user> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command `{command_name}`. Use `{prefix}commands` for help.",
            ctx, include_author=False
        ))
    
    full_name = cmd_obj.name
    user = await resolve_user(ctx, user_input)
    if not user:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Invalid user.", ctx, include_author=False))
    
    member = ctx.guild.get_member(user.id)
    if member and not has_higher_role(ctx.author, member):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Cannot restrict **{member.name}** due to hierarchy.",
            ctx, include_author=False
        ))
    
    settings = get_restrictions(ctx.guild.id, full_name)
    if user.id in settings["users"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: **{user.name}** is already on the allowlist for `{full_name}`.", ctx, include_author=False))
    
    add_restriction(ctx.guild.id, full_name, "user", user.id)
    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: `{full_name}` is now restricted to {user.mention}.",
        ctx, include_author=False, color=0xf9c414
    ))

@restrict.command(name="list")
@commands.has_permissions(manage_guild=True)
async def restrict_list(ctx, *, command_name: str = None):
    """See a list of restrictions for a command"""
    prefix = p(ctx)
    
    if not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Provide a command to list its restrictions for.",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Unknown command `{command_name}`. Use `{prefix}commands` for help.",
            ctx, include_author=False
        ))
    
    full_name = cmd_obj.name
    data = get_restrictions(ctx.guild.id, full_name)
    
    embed = create_embed(f"Restrictions for `{full_name}`", "", ctx)
    embed.add_field(name="Allowed Roles", value=", ".join([f"<@&{r}>" for r in data["roles"]]) or "`n/a`", inline=False)
    embed.add_field(name="Allowed Channels", value=", ".join([f"<#{c}>" for c in data["channels"]]) or "`n/a`", inline=False)
    embed.add_field(name="Allowed Users", value=", ".join([f"<@{u}>" for u in data["users"]]) or "`n/a`", inline=False)
    await ctx.send(embed=embed)


@bot.group(aliases=["urc"], invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def unrestrict(ctx):
    """Removes a restriction from a command"""
    prefix = p(ctx)
    embed = create_embed("command: unrestrict", "Removes a restriction from a command", ctx)
    embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
    embed.add_field(name="**Permissions Required**", value="`Manage Server`", inline=False)
    embed.add_field(name="**Subcommands**", value="`role`\n`channel`\n`user`\n`all`", inline=False)
    embed.add_field(
        name="**Utilization**",
        value=(
            f"```ansi\n\u001b[35msyntax:\u001b[0m\n"
            f"{prefix}unrestrict role <role> <command>\n"
            f"{prefix}unrestrict channel <channel> <command>\n"
            f"{prefix}unrestrict user <user> <command>\n"
            f"{prefix}unrestrict all <command>```"
        ),
        inline=False
    )
    await ctx.send(embed=embed)

@unrestrict.command(name="role")
@commands.has_permissions(manage_guild=True)
async def unrestrict_role(ctx, role_input: str = None, *, command_name: str = None):
    """Removes a command restriction for roles"""
    prefix = p(ctx)
    
    if not role_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a role and a command.\nUsage: `{prefix}unrestrict role <role> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command: `{command_name}`. Use `{prefix}commands` for help.", ctx, include_author=False))
    
    full_name = cmd_obj.name
    role = resolve_role(ctx.guild, role_input)
    if not role:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Role not found.", ctx, include_author=False))
    
    if not has_higher_role(ctx.author, role):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Cannot remove `{full_name}` restriction for {role.mention} due to hierarchy.",
            ctx, include_author=False
        ))
    
    restrictions = get_restrictions(ctx.guild.id, full_name)
    if role.id not in restrictions["roles"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: {role.mention} is not on the allowlist for `{full_name}`.", ctx, include_author=False))
    
    remove_restriction(ctx.guild.id, full_name, "role", role.id)
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Removed `{full_name}` restriction for {role.mention}.", ctx, include_author=False, color=0x71906e))

@unrestrict.command(name="channel")
@commands.has_permissions(manage_guild=True)
async def unrestrict_channel(ctx, channel_input: str = None, *, command_name: str = None):
    """Removes a command restriction for channels"""
    prefix = p(ctx)
    
    if not channel_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a channel and a command.\nUsage: `{prefix}unrestrict channel <channel> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command: `{command_name}`. Use `{prefix}commands` for help.", ctx, include_author=False))
    
    full_name = cmd_obj.name
    channel = resolve_channel(ctx.guild, channel_input)
    if not channel:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Channel not found.", ctx, include_author=False))
    
    restrictions = get_restrictions(ctx.guild.id, full_name)
    if channel.id not in restrictions["channels"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: {channel.mention} is not on the allowlist for `{full_name}`.", ctx, include_author=False))
    
    remove_restriction(ctx.guild.id, full_name, "channel", channel.id)
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Removed restriction for `{full_name}` in {channel.mention}.", ctx, include_author=False, color=0x71906e))

@unrestrict.command(name="user")
@commands.has_permissions(manage_guild=True)
async def unrestrict_user(ctx, user_input: str = None, *, command_name: str = None):
    """Removes a command restriction from users"""
    prefix = p(ctx)
    
    if not user_input or not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide both a user and a command.\nUsage: `{prefix}unrestrict user <user> <command>`",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command: `{command_name}`. Use `{prefix}commands` for help.", ctx, include_author=False))
    
    full_name = cmd_obj.name
    user = await resolve_user(ctx, user_input)
    if not user:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: User not found.", ctx, include_author=False))
    
    member = ctx.guild.get_member(user.id)
    if member and not has_higher_role(ctx.author, member):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Cannot unrestrict `{member}` due to hierarchy.",
            ctx, include_author=False
        ))
    
    restrictions = get_restrictions(ctx.guild.id, full_name)
    if user.id not in restrictions["users"]:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: **{user.name}** is not on the allowlist for `{full_name}`.", ctx, include_author=False))
    
    remove_restriction(ctx.guild.id, full_name, "user", user.id)
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Removed `{full_name}` restriction for **{user.name}**.", ctx, include_author=False, color=0x71906e))

@unrestrict.command(name="all")
@commands.has_permissions(manage_guild=True)
async def unrestrict_all(ctx, *, command_name: str = None):
    """Removes all restrictions from a command"""
    prefix = p(ctx)
    
    if not command_name:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide a command to clear restrictions for.",
            ctx, include_author=False
        ))
    
    cmd_obj = bot.get_command(command_name.strip())
    if not cmd_obj:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Unknown command `{command_name}`. Use `{prefix}commands` for help.",
            ctx, include_author=False
        ))
    
    full_name = cmd_obj.name
    restrictions = get_restrictions(ctx.guild.id, full_name)
    if not any(restrictions.values()):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: `{full_name}` has no restrictions.",
            ctx, include_author=False
        ))
    
    clear_command_restrictions(ctx.guild.id, full_name)
    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: Cleared all restrictions for `{full_name}`.",
        ctx, include_author=False, color=0x71906e
    ))

# PREFIX SYSTEM

@bot.command(aliases=["pre"])
async def prefix(ctx, new_prefix: str = None):
    """Configure the bot's prefix in your server"""
    guild_id = ctx.guild.id
    current = get_prefix_for_guild(guild_id)

    # Show current prefix
    if not new_prefix:
        embed = discord.Embed(
            description=(
                f"{ctx.author.mention}: Current prefix is (`{current}`)\n\n"
                f"To change the prefix, use:\n```{current}prefix <new_prefix>```\n"
                f"-# (Administrator required)"
            ),
            color=0x2f3136
        )
        await ctx.send(embed=embed)
        return

    # Check permissions
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description=f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You need **Administrator** permissions to change the prefix.",
            color=0x2f3136
        )
        await ctx.send(embed=embed)
        return

    set_prefix_for_guild(guild_id, new_prefix)

    embed = discord.Embed(
        description=f"{ctx.author.mention}: Changed prefix from `{current}` to `{new_prefix}`",
        color=0x71906e
    )
    await ctx.send(embed=embed)

# =============
# CASE SYSTEM
# =============

# -------------------------
# Formatting helpers
# -------------------------
def _fmt_case_brief(case_id: int, case: dict):
    # Example line: "1. Warned for 'spam' (Case #4)"
    typ = case.get("type", "unknown")
    reason = case.get("reason")

    if typ == "ban":
        desc = f"Banned for `{reason or 'n/a'}`"
    elif typ == "kick":
        desc = f"Kicked for `{reason or 'n/a'}`"
    elif typ == "timeout":
        desc = f"Timed out for `{reason or 'n/a'}`"
    elif typ == "jail":
        desc = f"Sent to jail for `{reason or 'n/a'}`"
    elif typ == "imute":
        desc = f"Image muted for `{reason or 'n/a'}`"
    elif typ == "rmute":
        desc = f"Reaction muted for `{reason or 'n/a'}`"
    else:
        desc = f"{typ} ({reason or 'n/a'})"
    return f"{desc} (Case #{case_id})"

def _fmt_case_detailed(case_id:int, case:dict, guild: discord.Guild, bot: commands.Bot):
    user_id = case.get("user_id")
    mod_id = case.get("mod")
    ts = case.get("timestamp", int(time.time()))
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    time_str = discord.utils.format_dt(dt, style="d")  # localized long format

    type_display = case.get("type", "unknown").upper()
    reason = case.get("reason") or "n/a"

    mod_mention = f"<@{mod_id}>"
    user_mention = f"<@{user_id}>"

    embed = discord.Embed(
        title=f"Case #{case_id} — {type_display}",
        color=0x2f3136
    )
    embed.add_field(
        name="User",
        value=user_mention,
        inline=True
    )
    embed.add_field(
        name="Moderator",
        value=mod_mention,
        inline=True
    )
    embed.add_field(
        name="_ _",
        value="_ _",
        inline=False
    )
    embed.add_field(
        name="Time",
        value=time_str,
        inline=True
    )
    embed.add_field(
        name="Reason",
        value=reason,
        inline=True
    )
    # attempt to set author to the user (if present in guild)
    member = guild.get_member(user_id)
    if member:
        embed.set_author(name=f"{member} ({user_id})", icon_url=member.avatar.url if member.avatar else None)
    else:
        embed.set_author(name=f"User ({user_id})")
    return embed

# -------------------------
# history command group
# -------------------------
# Requires bot variable and create_embed function in your script.

PAGE_SIZE = 10

class HistoryView(discord.ui.View):
    def __init__(self, ctx: commands.Context, member: discord.Member, case_list: list[tuple], page:int=1):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.member = member
        self.timed_out = False
        self.case_list = case_list  # list of (case_id, case)
        self.page = page
        self.message = None

    def make_embed(self):
        start = (self.page - 1) * PAGE_SIZE
        subset = self.case_list[start:start+PAGE_SIZE]
        embed = create_embed(
            title=f"HISTORY — {self.member.display_name}",
            description="",
            ctx_or_msg=self.ctx,  # your create_embed expects ctx usually
            include_author=False
        )
        embed.set_author(name=self.member.name, icon_url=self.member.avatar.url)
        lines = []
        for idx, (case_id, case) in enumerate(subset, start=1):
            lines.append(f"**{idx}.** {_fmt_case_brief(case_id, case)}")
        if not lines:
            embed.description = f"{self.ctx.author.mention}: **{self.member.display_name}** is clean."
        else:
            embed.description = "\n".join(lines)
        total = len(self.case_list)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
        embed.set_footer(text=f"{self.page}/{pages}  ∙  {total} cases")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        total = len(self.case_list)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
        if self.page > 1:
            self.page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def nxt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        total = len(self.case_list)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
        if self.page < pages:
            self.page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only allow the command author to close
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=None)
        except discord.Forbidden:
            pass

        self.stop()

@bot.group(aliases=["hst"], invoke_without_command=True)
@commands.has_permissions(moderate_members=True)
async def history(ctx, member: discord.Member | None = None, page: int = 1):
    """View a member's case log"""
    if member is None:
        member = ctx.author

    case_list = get_cases_for_member(ctx.guild.id, member.id)  # list[(case_id, case)]
    if not case_list:
        if member == ctx.author:
            return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You are clean.", ctx, include_author=False))
        else:
            return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** is clean.", ctx, include_author=False))

    # page sanity
    total = len(case_list)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
    if page < 1:
        page = 1
    if page > pages:
        page = pages

    view = HistoryView(ctx, member, case_list, page=page)
    view.message = await ctx.send(embed=view.make_embed(), view=view)
# -------------------------
# history view subcommand
# -------------------------
@history.command(name="view")
@commands.has_permissions(moderate_members=True)
async def history_view(ctx, case_number: int = None):
    """View a case log by its number"""
    prefix = p(ctx)

    if case_number is None:
        try:
            embed = create_embed(
                "command: history view",
                "View a case log by its number",
                ctx
            )
            embed.add_field(
                name="Aliases",
                value=alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="Permissions Required",
                value="`Manage Messages`",
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}history view <case_number> \n\u001b[35mexample:\u001b[0m {prefix}history view 5```",
                inline=False
            )
            return await ctx.send(embed=embed)
        except Exception as e:
            print("Could not send embed:", e)


    case = get_case(ctx.guild.id, case_number)
    if not case:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: No case #{case_number} found.", ctx, include_author=False))
    try:
        embed = _fmt_case_detailed(case_number, case, ctx.guild, bot)
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"[history view] Error: {e}")
        await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Failed to display case.", ctx, include_author=False))

# -------------------------
# history remove subcommand
# -------------------------
@history.command(name="remove", aliases=["delete", "del"])
@commands.has_permissions(moderate_members=True)
async def history_remove(ctx, member: discord.Member | None = None, case_number: int = None):
    """
    Remove a member's specific case log
    """
    prefix = p(ctx)

    if member is None or case_number is None:
        try:
            embed = create_embed(
                "command: history remove",
                "Remove a member's specific case log",
                ctx
            )
            embed.add_field(
                name="Aliases",
                value=alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="Permissions Required",
                value="`Manage Messages`",
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}history remove <member> <case_number> \n\u001b[35mexample:\u001b[0m {prefix}history remove zeph 6```",
                inline=False
            )
            return await ctx.send(embed=embed)
        except Exception as e:
            print("Could not send embed:", e)
    
    case = get_case(ctx.guild.id, case_number)
    if not case:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Case #{case_number} does not exist.", ctx, include_author=False))
    if case.get("user_id") != member.id:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Case #{case_number} is not for that member.", ctx, include_author=False))
    removed = remove_case(ctx.guild.id, case_number)
    if removed:
        await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Removed Case #{case_number}.", ctx, include_author=False))
    else:
        await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Failed to remove Case #{case_number}.", ctx, include_author=False))

# -------------------------
# history clear subcommand
# -------------------------
@history.command(name="clear", aliases=["removeall", "delall"])
@commands.has_permissions(administrator=True)
async def history_clear(ctx, member: discord.Member | None = None):
    """Clear all cases for a member"""

    prefix = p(ctx)

    if member is None:
        try:
            embed = create_embed(
                "command: history clear",
                "Clear all cases for a member",
                ctx
            )
            embed.add_field(
                name="Aliases",
                value=alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="Permissions Required",
                value="`Administrator`",
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}history clear <member> \n\u001b[35mexample:\u001b[0m {prefix}history clear zeph```",
                inline=False
            )
            return await ctx.send(embed=embed)
        except Exception as e:
            print("Could not send embed:", e) 
    
    count = clear_member_cases(ctx.guild.id, member.id)
    clear_warnings(ctx.guild.id, member.id)
            
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Removed {count} case(s) for **{member.name}**.", ctx, include_author=False))

@history.command(name="all")
@commands.has_permissions(moderate_members=True)
async def history_all(ctx):
    """View all case logs in the server"""

    case_list = get_all_cases(ctx.guild.id)

    if not case_list:
        return await ctx.send(embed=create_embed(
            "", f"{ctx.author.mention}: This server has no case history.",
            ctx, include_author=False
        ))
    
    class HistoryAllView(discord.ui.View):
        def __init__(self, ctx, case_list):
            super().__init__(timeout=60)
            self.ctx = ctx
            self.case_list = case_list
            self.page = 1
            self.message = None

        def make_embed(self):
            start = (self.page - 1) * PAGE_SIZE
            subset = self.case_list[start:start + PAGE_SIZE]
            embed = create_embed(
                f"Punishment History",
                "",
                self.ctx
            )
            lines = []
            for case_id, case in subset:
                user_id = case.get("user_id")
                typ = case.get("type", "unknown")
                reason = case.get("reason") or "n/a"
                lines.append(f"`{case_id}.` <@{user_id}> — {typ} (`{reason}`)")
            embed.description = "\n".join(lines)
            embed.set_author(name=self.ctx.guild.name, icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)
            total = len(self.case_list)
            pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
            embed.set_footer(text=f"{self.page}/{pages}  ∙  {total} cases")
            return embed

        async def update_message(self, interaction):
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

        @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
        async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message(
                    embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                    ephemeral=True
                )
            if self.page > 1:
                self.page -= 1
                await self.update_message(interaction)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
        async def nxt(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message(
                    embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                    ephemeral=True
                )
            total = len(self.case_list)
            pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
            if self.page < pages:
                self.page += 1
                await self.update_message(interaction)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
        async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message(
                    embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                    ephemeral=True
                )
            await interaction.message.delete()
            self.stop()

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(view=None)
            except:
                pass
            self.stop()

    view = HistoryAllView(ctx, case_list)
    view.message = await ctx.send(embed=view.make_embed(), view=view)


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member = None, *, reason=None):
    """Bans a member"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed("command: ban", "Bans a member", ctx)
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Ban Members`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=("```ansi\n"
            "\u001b[35msyntax:\u001b[0m" + f" {prefix}ban <member> (reason)\n"
            "\u001b[35mexample:\u001b[0m" + f" {prefix}ban zeph being dumb\n```"),
            inline=False
            
        )
        await ctx.send(embed=embed)
        return

    try:
        if isinstance(member, discord.User) and not isinstance(member, discord.Member):
            member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        elif not isinstance(member, discord.Member):
            member = await MemberConverter().convert(ctx, str(member))

    except discord.NotFound:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: I can't find that user in the server.", ctx, include_author=False))
    except BadArgument:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Couldn't resolve the member. Use mention or ID.", ctx, include_author=False))
    except Exception as e:
        # If this triggers, you'll see the real error instead of it being swallowed.
        return await ctx.send(embed=create_embed("", f"Error resolving member: `{e}`", ctx, include_author=False))

    if member == ctx.author:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You cannot `ban` yourself.", ctx, include_author=False))

    if member.top_role.position >= ctx.author.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: You cannot ban **{member}** due to hierarchy.",
            ctx, include_author=False
        ))

    # === Bot hierarchy check ===
    if member.top_role.position >= ctx.guild.me.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member}** has a higher role than me.",
            ctx, include_author=False
        ))

    # Explicit admin check (Discord protects admins)
    if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: I cannot ban **{member}** because they have `Administrator` permission.",
            ctx, include_author=False
        ))

    # Send DM first before banning (otherwise they can’t receive it)
    try:
        dm_embed = discord.Embed(
            title="/ban",
            description=(
                f"You have been banished from **{ctx.guild.name}**.\n\n"
                f"**Moderator**\n{ctx.author.mention}\n\n"
                f"**Reason**\n{reason or 'n/a'}"
            ),
            color=0x963939
        )
        dm_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")
        await member.send(embed=dm_embed)
    except (discord.Forbidden, discord.HTTPException):
        pass  # user has DMs closed or blocked the bot

    # Ban the member
    try:
        await member.ban(reason=reason, delete_message_days=0)
        create_case(ctx.guild.id, member.id, "ban", reason, ctx.author.id)
    except discord.Forbidden:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Cannot ban **{member.name}**. They may have `Administrator` or a higher role than you.", ctx, include_author=False))

    # Send confirmation message in the channel
    await ctx.send("https://tenor.com/view/dr-manhattan-gif-18899941")
    await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member.name}** has been banished from **{ctx.guild.name}**. **Reason:** {reason or 'n/a'}",
            ctx, color=0x963939,
            include_author=False
        ))
    

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member: str = None):
    """Unbans a member"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed("command: unban", "Unbans a member", ctx)
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Ban Members`", inline=False)
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}unban userID\n\u001b[35mexample:\u001b[0m {prefix}unban 1438523192426627112```", inline=False)
        await ctx.send(embed=embed)
        return

    try:
        # Allow mention or ID input
        member = member.strip("<@!>")
        user_id = int(member)

        # Iterate through the async generator
        async for ban_entry in ctx.guild.bans(limit=None):
            if ban_entry.user.id == user_id:
                await ctx.guild.unban(ban_entry.user)
                await ctx.send("https://tenor.com/view/doctor-manhattan-watchmen-marvel-gif-21030500")
                await ctx.send(embed=create_embed(
                    "", f"{ctx.author.mention}: **{ban_entry.user.name}** has been unbanned from **{ctx.guild.name}**.", ctx, color=0x71906e, include_author=False
                ))
                return

        await ctx.send("User not found in ban list.")
    except Exception as e:
        await ctx.send(f"**ERROR:** {e}. (Must use **UserID**)")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member = None, *, reason=None):
    """Kicks a member"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed("command: kick", "Kicks a member", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx), inline=False)
        embed.add_field(
        name="**Permissions Required**",
        value="`Kick Members`", inline=False)
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}kick <member> (reason)\n\u001b[35mexample:\u001b[0m {prefix}kick zeph get out```", inline=False)
        await ctx.send(embed=embed)
        return

    try:
        if isinstance(member, discord.User) and not isinstance(member, discord.Member):
            member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        elif not isinstance(member, discord.Member):
            member = await MemberConverter().convert(ctx, str(member))

    except discord.NotFound:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: I can't find that user in the server.", ctx, include_author=False))
    except BadArgument:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Couldn't resolve the member. Use mention or ID.", ctx, include_author=False))
    except Exception as e:
        # If this triggers, you'll see the real error instead of it being swallowed.
        return await ctx.send(embed=create_embed("", f"Error resolving member: `{e}`", ctx, include_author=False))

    if member == ctx.author:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You cannot `kick` yourself.", ctx, include_author=False))

    if member.top_role.position >= ctx.author.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: You cannot kick **{member}** due to hierarchy.",
            ctx, include_author=False
        ))

    # === Bot hierarchy check ===
    if member.top_role.position >= ctx.guild.me.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member}** has a higher role than me.",
            ctx, include_author=False
        ))

    # Explicit admin check (Discord protects admins)
    if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: I cannot kick **{member}** because they have `Administrator` permission.",
            ctx, include_author=False
        ))

    dm_embed = discord.Embed(
        title="/kick",
        description=(
            f"You have been kicked from **{ctx.guild.name}**.\n\n"
            f"**Moderator**\n{ctx.author.mention}\n\n"
            f"**Reason**\n{reason or 'n/a'}"
        ),
        color=0x963939
    )
    dm_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")

    # Send DM (ignore failure to DM)
    try:
        await member.send(embed=dm_embed)
    except Exception:
        pass
    
    try:
        await member.kick(reason=reason)
        case_id = create_case(ctx.guild.id, member.id, "kick", reason, ctx.author.id)
    except discord.Forbidden:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Cannot kick **{member.name}**. They may have `Administrator` or a higher role than you.", ctx, include_author=False))
    await ctx.send(embed=create_embed("", f"{member.mention} has been kicked from **{ctx.guild.name}**. **Reason:** {reason or 'n/a'}", ctx, color=0x963939, include_author=False))

from datetime import datetime, timedelta, timezone  # <- top of your file

@bot.command(aliases=["time"])
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member = None, duration: str = None, *, reason=None):
    """Times out a member"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed("command: timeout", "Times out a member", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False)
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False)
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}timeout <member> (duration m/h/d) (reason)\n\u001b[35mexample:\u001b[0m {prefix}timeout zeph 1d being dumb again```", inline=False)
        await ctx.send(embed=embed)
        return

    try:
        if isinstance(member, discord.User) and not isinstance(member, discord.Member):
            member = ctx.guild.get_member(member.id) or await ctx.guild.fetch_member(member.id)
        elif not isinstance(member, discord.Member):
            member = await MemberConverter().convert(ctx, str(member))

    except discord.NotFound:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: I can't find that user in the server.", ctx, include_author=False))
    except BadArgument:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Couldn't resolve the member. Use mention or ID.", ctx, include_author=False))
    except Exception as e:
        # If this triggers, you'll see the real error instead of it being swallowed.
        return await ctx.send(embed=create_embed("", f"Error resolving member: `{e}`", ctx, include_author=False))

    if member == ctx.author:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You cannot `timeout` yourself.", ctx, include_author=False))

    if member.top_role.position >= ctx.author.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: You cannot timeout **{member}** due to hierarchy.",
            ctx, include_author=False
        ))

    # === Bot hierarchy check ===
    if member.top_role.position >= ctx.guild.me.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member}** has a higher role than me.",
            ctx, include_author=False
        ))

    # Explicit admin check (Discord protects admins)
    if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: I cannot timeout **{member}** because they have `Administrator` permission.",
            ctx, include_author=False
        ))

    if member.timed_out_until and member.timed_out_until > datetime.now(tz=timezone.utc):
        await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: **{member.name}** is already on timeout.", ctx, include_author=False))
        return

    if not duration:
        duration = "5m"

    try:
        amount = int(duration[:-1])
        unit = duration[-1].lower()
        if unit == "m":
            delta = timedelta(minutes=amount)
        elif unit == "h":
            delta = timedelta(hours=amount)
        elif unit == "d":
            delta = timedelta(days=amount)
        else:
            raise ValueError("Invalid time unit.")
            return
        MAX_TIMEOUT = timedelta(days=28)
        if delta > MAX_TIMEOUT:
            msg = await ctx.send("Maximum duration exceeded. (**limit:** `28d`)")
            await asyncio.sleep(3)
            await msg.delete()
            return
    except Exception:
        msg = await ctx.send("Invalid duration format. Example: `10m`, `2h`, `1d`")
        await asyncio.sleep(3)
        await msg.delete()
        return

    until_time = datetime.now(tz=timezone.utc) + delta
    try:
        await member.timeout(until_time)
        case_id = create_case(ctx.guild.id, member.id, "timeout", reason, ctx.author.id)
    except discord.Forbidden:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: Cannot `timeout` **{member.name}**, They may have Administrator permissions or a higher role than you.", ctx, include_author=False))  # positional-only argument
    await ctx.send("https://tenor.com/view/it%27s-time-to-stop-gif-9416155803997449261")
    await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** has been timed out for **{duration}**. **Reason:** {reason or 'n/a'}", ctx, color=0x963939, include_author=False))

@bot.command(aliases=["untime"])
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member = None):
    """Removes timeout from a member"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed("command: untimeout", "Removes timeout from a member", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False
        )
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}untimeout <member>\n\u001b[35mexample:\u001b[0m {prefix}untimeout zeph```", inline=False)
        await ctx.send(embed=embed)
        return
        
    if not member.timed_out_until or member.timed_out_until <= datetime.now(tz=timezone.utc):
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: **{member.name}** is not timed out.", ctx, include_author=False))
    # Remove timeout by passing None as the positional 'until' argument
    await member.timeout(None)
    
    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: **{member.name}** has been released from timeout.",
        ctx, color=0x71906e, include_author=False
    ))

# WARNING SYSTEM (PER-SERVER)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member = None, *, reason: str = None):
    """Warns a member"""
    prefix = p(ctx)

    if member is None:
        embed = create_embed(
            "command: warn",
            "Warns a member",
            ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Messages`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}warn <member> (reason)\n\u001b[35mexample:\u001b[0m {prefix}warn zeph being dumb```",
            inline=False
        )
        return await ctx.send(embed=embed)

    if member == ctx.author:
        embed = create_embed(
            "",
            f"{ctx.author.mention}: You cannot warn yourself.",
            ctx,
            include_author=False
        )
        return await ctx.send(embed=embed)
    
    if member.top_role.position >= ctx.author.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: You cannot warn **{member}** due to hierarchy.",
            ctx, include_author=False
        ))

    # === Bot hierarchy check ===
    if member.top_role.position >= ctx.guild.me.top_role.position:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member}** has a higher role than me.",
            ctx, include_author=False
        ))

    if reason is None:
        reason = "n/a"

    add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
    
    pub_embed = create_embed(
        "",
        f"You have been warned in **{ctx.guild.name}** for `{reason}`.",
        ctx,
        include_author=False
    )
    await ctx.send(member.mention, embed=pub_embed)

    dm_embed = create_embed(
        "/warn",
        f"You have received a warning in **{ctx.guild.name}**.\nFurther warnings may result in a timeout, kick, or ban.",
        ctx,
        include_author=False,
        color=0xf9c414
    )
    dm_embed.add_field(
        name="Moderator",
        value=ctx.author.mention,
        inline=False
    )
    dm_embed.add_field(
        name="Reason",
        value=reason,
        inline=False
    )
    dm_embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")
    try:
        await member.send(embed=dm_embed)
    except:
        pass

@bot.group(invoke_without_command=True)
@commands.has_permissions(manage_messages=True)
async def warnings(ctx, member:discord.Member = None):
    """View a member's warnings or your own"""

    if member is None:
        member = ctx.author

    warn_list = get_warnings(ctx.guild.id, member.id)

    if not warn_list:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member.name}** has no warnings.",
            ctx,
            include_author=False
        ))

    embed = create_embed(
        f"Warnings in {ctx.guild.name}",
        "",
        ctx,
        include_author=False
    )
    embed.set_author(name=str(member), icon_url=member.avatar.url if member.avatar else None)
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

    lines = []
    for i, w in enumerate(warn_list, start=1):
        mod = ctx.guild.get_member(w["mod"])
        mod_name = mod.mention if mod else "Unknown"
        timestamp = discord.utils.format_dt(discord.utils.datetime.datetime.utcfromtimestamp(w["timestamp"]), style="R")
        lines.append(f"**{i}.** `{w['reason']}`  —  {mod_name} ({timestamp})")
    
    embed.description = "\n".join(lines)

    await ctx.send(embed=embed)

@warnings.command(name="remove", aliases=["delete", "del"])
@commands.has_permissions(manage_messages=True)
async def warnings_remove(ctx, member: discord.Member = None, warning_number: int = None):
    """Remove a specific warning from a member"""
    prefix = p(ctx)

    if member is None or warning_number is None:
        embed = create_embed("command: warnings remove", "Remove a specific warning from a member", ctx)
        embed.add_field(name="Aliases",              value=alss_ctx(ctx),       inline=False)
        embed.add_field(name="Permissions Required", value="`Manage Messages`", inline=False)
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}warnings remove <member> <warning_number>\n\u001b[35mexample:\u001b[0m {prefix}warnings remove zeph 2```",
            inline=False
        )
        return await ctx.send(embed=embed)

    warn_list = get_warnings(ctx.guild.id, member.id)
    if not warn_list:
        return await ctx.send(embed=create_embed(
            "", f"{ctx.author.mention}: **{member.name}** has no warnings.", ctx, include_author=False
        ))

    if warning_number < 1 or warning_number > len(warn_list):
        return await ctx.send(embed=create_embed(
            "", f"{ctx.author.mention}: Warning #{warning_number} does not exist. **{member.name}** has {len(warn_list)} warning(s).",
            ctx, include_author=False
        ))

    remove_warning(ctx.guild.id, member.id, warning_number)
    await ctx.send(embed=create_embed(
        "", f"{ctx.author.mention}: Removed warning #{warning_number} from **{member.name}**.", ctx, include_author=False
    ))


@warnings.command(name="clear", aliases=["removeall", "delall"])
@commands.has_permissions(administrator=True)
async def warnings_clear(ctx, member: discord.Member = None):
    """Clear all warnings for a member"""
    prefix = p(ctx)

    if member is None:
        embed = create_embed("command: warnings clear", "Clear all warnings for a member", ctx)
        embed.add_field(name="Aliases",              value=alss_ctx(ctx),    inline=False)
        embed.add_field(name="Permissions Required", value="`Administrator`", inline=False)
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}warnings clear <member>\n\u001b[35mexample:\u001b[0m {prefix}warnings clear zeph```",
            inline=False
        )
        return await ctx.send(embed=embed)

    count = clear_warnings(ctx.guild.id, member.id)
    await ctx.send(embed=create_embed(
        "", f"{ctx.author.mention}: Cleared {count} warning(s) from **{member.name}**.", ctx, include_author=False
    ))


# JAIL SYSTEM (PER-SERVER VERSION)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_guild_jail(guild_id: int):
    """Returns {role_id, channel_id} for that guild or None"""
    return get_jail_config(guild_id)


def set_guild_jail(guild_id: int, role_id: int, channel_id: int):
    set_jail_config(guild_id, role_id, channel_id)


def remove_guild_jail(guild_id: int):
    delete_jail_config(guild_id)


def jail_system_not_set(guild: discord.Guild):
    config = get_guild_jail(guild.id)
    if not config:
        return True

    role = guild.get_role(config["role_id"])
    channel = guild.get_channel(config["channel_id"])

    if not role or not channel:
        remove_guild_jail(guild.id)
        return True

    return False


async def jail_instruction_embed(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(
        description=(
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `jail` system is **not set**.\n\n"
            f"To set it up, use:\n```{prefix}jailset <role> <channel>```"
        ),
        color=0x2f3136
    )
    embed.set_footer(text="TIP: You can use existing role and channel.")
    await ctx.send(embed=embed)



# ---------------------------------------------------------
# jailset — per server setup
# ---------------------------------------------------------

@bot.group(invoke_without_command=True)
@commands.has_permissions(moderate_members=True, manage_roles=True, manage_channels=True)
async def jailset(ctx, role_arg=None, channel_arg=None):
    """Configures a jail system in the server"""
    guild = ctx.guild
    prefix = p(ctx)

    # Already set?
    if not jail_system_not_set(guild):
        config = get_guild_jail(guild.id)
        role = guild.get_role(config["role_id"])
        channel = guild.get_channel(config["channel_id"])
        embed = create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `jail` system is already set.",
            ctx, include_author=False
        )
        embed.add_field(name="Role",    value=role.mention    if role    else "`deleted`", inline=True)
        embed.add_field(name="Channel", value=channel.mention if channel else "`deleted`", inline=True)
        embed.set_footer(text=f"To change: {prefix}jailset role <role>  |  {prefix}jailset channel <channel>")
        return await ctx.send(embed=embed)

    loading_embed = create_embed(
        "",
        "<a:sword_spin:1211611749426667560>  Setting up `jail` system, this might take a while.",
        ctx,
        include_author=False
    )
    status_msg = await ctx.send(embed=loading_embed)

    # 1) ROLE SETUP
    if role_arg is None:
        role = await guild.create_role(name="jailed", reason="auto-generated jail role")
    else:
        role = resolve_role(guild, role_arg)

        if role is None:
            role = await guild.create_role(name=role_arg, reason="jailset created role")

    # 2) CHANNEL SETUP
    channel = None
    if channel_arg is not None:
        channel = resolve_channel(guild, channel_arg)
    if channel:
        try:
            await channel.set_permissions(
                guild.default_role,
                view_channel=False
            )
            await channel.set_permissions(
                role,
                view_channel=True,
                send_messages=True
            )
        except:
            pass

    else:
        category = discord.utils.get(guild.categories, name="jail")
        if category is None:
            category = await guild.create_category(
                "jail",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
            )
        else:
            await category.set_permissions(guild.default_role, view_channel=False)
            await category.set_permissions(role, view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            channel_arg or "jail",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
        )



    # SAVE PER-SERVER CONFIG
    set_guild_jail(guild.id, role.id, channel.id)

    # Lock all other channels
    for ch in guild.text_channels:
        if ch.id != channel.id:
            try:
                await ch.set_permissions(role, send_messages=False)
            except:
                pass

    for vc in guild.voice_channels:
        try:
            await vc.set_permissions(role, connect=False, speak=False)
        except:
            pass

    final_embed = discord.Embed(
        description=f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `jail` system has been set.",
        color=0x2f3136
    )
    final_embed.add_field(name="Role", value=role.mention, inline=False)
    final_embed.add_field(name="Channel", value=channel.mention, inline=False)
    await status_msg.edit(embed=final_embed)

@jailset.command(name="role")
@commands.has_permissions(manage_roles=True)
async def jailset_role(ctx, *, role_input: str = None):
    """Configures jailed role"""
    guild = ctx.guild
    prefix = p(ctx)

    if jail_system_not_set(guild):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `jail` system is not set up yet. Run `{prefix}jailset` first.",
            ctx, include_author=False
        ))
    
    if role_input is None:
        embed = create_embed(
            "command: jailset role",
            "Edit jailed role",
            ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Roles`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}jailset role @newrole\n\u001b[35mexample: \u001b[0m{prefix}jailset role @convict```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    new_role = resolve_role(guild, role_input)
    if new_role is None:
        return await ctx.send(embed=create_embed(
            "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Role `{role_input}` not found.",
            ctx, include_author=False
        ))
    
    config = get_guild_jail(guild.id)
    channel = guild.get_channel(config["channel_id"])
    old_role = guild.get_role(config["role_id"])

    if old_role:
        if channel:
            try:
                await channel.set_permissions(old_role, overwrite=None)
            except discord.Forbidden:
                pass
        for ch in guild.text_channels:
            try:
                await ch.set_permissions(old_role, overwrite=None)
            except discord.Forbidden:
                pass
        for vc in guild.voice_channels:
            try:
                await vc.set_permissions(old_role, overwrite=None)
            except discord.Forbidden:
                pass

    if channel:
        try:
            await channel.set_permissions(new_role, view_channel=True, send_messages=True)
        except discord.Forbidden:
            pass

    for ch in guild.text_channels:
        if ch.id != (channel.id if channel else None):
            try:
                await ch.set_permissions(new_role, send_messages=False)
            except discord.Forbidden:
                pass
    
    for vc in guild.voice_channels:
        try:
            await vc.set_permissions(new_role, connect=False, speak=False)
        except discord.Forbidden:
            pass

    set_guild_jail(guild.id, new_role.id, config["channel_id"])
    await ctx.send(embed=create_embed(
        "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Jail role updated to {new_role.mention}.",
        ctx, include_author=False
    ))

@jailset.command(name="channel")
@commands.has_permissions(manage_messages=True)
async def jailset_channel(ctx, *, channel_input: str = None):
    """Configures jail channel"""
    guild = ctx.guild
    prefix = p(ctx)

    if jail_system_not_set(guild):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `jail` system is not set up yet. Run `{prefix}jailset` first.",
            ctx, include_author=False
        ))
    
    if channel_input is None:
        embed = create_embed(
            "command: jailset channel",
            "Edit jail channel", ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Channels`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}jailset channel #newchannel\n\u001b[35mexample: \u001b[0m{prefix}jailset channel #prison```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    new_channel = resolve_channel(guild, channel_input)
    if new_channel is None:
        return await ctx.send(embed=create_embed(
            "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Channel `{channel_input}` not found.",
            ctx, include_author=False
        ))
    
    config = get_guild_jail(guild.id)
    jail_role = guild.get_role(config["role_id"])
    old_channel = guild.get_channel(config["channel_id"])

    if old_channel and jail_role:
        try:
            await old_channel.set_permissions(guild.default_role, overwrite=None)
            await old_channel.set_permissions(jail_role, overwrite=None)
        except discord.Forbidden:
            pass

    if jail_role:
        try:
            await new_channel.set_permissions(guild.default_role, view_channel=False)
            await new_channel.set_permissions(jail_role, view_channel=True, send_messages=True)
        except discord.Forbidden:
            pass

    set_guild_jail(guild.id, config["role_id"], new_channel.id)
    await ctx.send(embed=create_embed(
        "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Jail channel updated to {new_channel.mention}.",
        ctx, include_author=False
    ))

# ---------------------------------------------------------
# jail — apply punishment
# ---------------------------------------------------------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def jail(ctx, member: discord.Member = None, *, reason=None):
    """Sends a member to jail"""
    
    prefix = p(ctx)
    guild = ctx.guild

    if jail_system_not_set(guild):
        return await jail_instruction_embed(ctx)

    if not member:
        embed = create_embed("command: jail", "Sends a member to `jail`", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False
        )
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}jail <member> (reason)\n\u001b[35mexample:\u001b[0m {prefix}jail zeph just because```", inline=False)
        return await ctx.send(embed=embed)

    if member == ctx.author:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You cannot `jail` yourself.", ctx, include_author=False))

    if member.top_role >= guild.me.top_role:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** has a higher role than me.", ctx, include_author=False))

    config = get_guild_jail(guild.id)
    role = guild.get_role(config["role_id"])
    channel = guild.get_channel(config["channel_id"])

    if role in member.roles:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** is already in `jail`.", ctx, include_author=False))

    await member.add_roles(role)
    create_case(ctx.guild.id, member.id, "jail", reason, ctx.author.id)

    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: **{member.name}** has been sent to `jail`. **Reason:** {reason or 'n/a'}",
        ctx, color=0x963939, include_author=False
    ))

    try:
        dm_embed = discord.Embed(
            title="/jail",
            description=f"You have been sent to `jail` in **{guild.name}**.\n\n**Moderator**\n{ctx.author.mention}\n\n**Reason**\n{reason or 'n/a'}",
            color=0x963939
        )
        await member.send(embed=dm_embed)
    except:
        pass



# ---------------------------------------------------------
# unjail — release
# ---------------------------------------------------------

@bot.command(aliases=["release", "unj"])
@commands.has_permissions(moderate_members=True)
async def unjail(ctx, member: discord.Member = None):
    """Releases a member from jail"""
    
    prefix = p(ctx)
    guild = ctx.guild

    if jail_system_not_set(guild):
        return await jail_instruction_embed(ctx)

    if not member:
        embed = create_embed("command: unjail", "Releases a member from `jail`", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False
        )
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}unjail <member>\n\u001b[35mexample:\u001b[0m {prefix}unjail zeph```", inline=False)
        return await ctx.send(embed=embed)

    config = get_guild_jail(guild.id)
    role = guild.get_role(config["role_id"])

    if role not in member.roles:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** is not in `jail`.", ctx, include_author=False))

    if member == ctx.author:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: You cannot `unjail` yourself.", ctx, include_author=False))

    if member.top_role >= guild.me.top_role:
        return await ctx.send(embed=create_embed("", f"{ctx.author.mention}: **{member.name}** has a higher role than me.", ctx, include_author=False))

    await member.remove_roles(role)

    await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: **{member.name}** has been released.",
        ctx, color=0x71906e, include_author=False
    ))

    try:
        dm_embed = discord.Embed(
            title="/unjail",
            description=f"You have been released from `jail` in **{guild.name}**.\n\n**Moderator**\n{ctx.author.mention}",
            color=0x71906e
        )
        await member.send(embed=dm_embed)
    except:
        pass
        
@bot.event
async def on_guild_role_delete(role):
    data = get_jail_config(role.guild.id)
    if data and data["role_id"] == role.id:
        delete_jail_config(role.guild.id)
    istored = get_imute_role_id(role.guild.id)
    if istored == role.id:
        delete_imute_role(role.guild.id)
    rstored = get_rmute_role_id(role.guild.id)
    if rstored == role.id:
        delete_rmute_role(role.guild.id)
    
        
@bot.event
async def on_guild_channel_delete(channel):
    data = get_jail_config(channel.guild.id)
    if data and data["channel_id"] == channel.id:
        delete_jail_config(channel.guild.id)

# ===========================
#      PER-SERVER IMUTE
# ===========================

def imute_not_set(guild):
    role_id = get_imute_role_id(guild.id)
    if role_id is None:
        return True

    role = guild.get_role(role_id)
    if not role:
        # cleanup invalid role
        delete_imute_role(guild.id)
        return True

    return False


async def imute_instruction_embed(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(
        title="",
        description=(
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `imute` system is **not set**.\n\n"
            f"To set it up, use:\n```{prefix}imuteset <role>```"
        ),
        color=0x2f3136
    )
    embed.set_footer(text="TIP:  You can provide an existing role or let the bot create one.")
    await ctx.send(embed=embed)


# ===========================
#         imuteset
# ===========================

@bot.group(invoke_without_command=True)
@commands.has_permissions(moderate_members=True, manage_roles=True)
async def imuteset(ctx, *, role_arg=None):
    """Configures image mute system in the server"""
    guild = ctx.guild
    prefix = p(ctx)

    if not imute_not_set(guild):
        config = get_imute_role_id(guild.id)
        role = guild.get_role(config)
        embed = create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `imute` system is already set.",
            ctx,
            include_author=False
        )
        embed.add_field(name="Role", value=role.mention if role else "`deleted`", inline=True)
        embed.set_footer(text=f"To change: {prefix}imuteset role <role>")
        return await ctx.send(embed=embed)

    loading_embed = create_embed(
        "",
        "<a:sword_spin:1211611749426667560>  Setting up `imute` system, this might take a while.",
        ctx,
        include_author=False
    )
    status_msg = await ctx.send(embed=loading_embed)

    # No argument → auto-create role
    if role_arg is None:
        role = await guild.create_role(
            name="imuted",
            reason="auto-created imute role"
        )
    else:
        # Mentioned role
        role = None
        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]

        # Exact name
        if role is None:
            role = resolve_role(guild, role_arg)

        # Create if not found
        if role is None:
            role = await guild.create_role(
                name=role_arg,
                reason="created with imuteset command"
            )

    # Apply NO ATTACHMENTS permissions
    for ch in guild.channels:
        try:
            perms = ch.overwrites_for(role)
            perms.attach_files = False
            perms.embed_links = False
            await ch.set_permissions(role, overwrite=perms)
        except:
            pass

    # Save role per server
    set_imute_role_id(guild.id, role.id)

    final_embed = discord.Embed(
        title="",
        description=(
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: "
            f"`imute` role has been set."
        ),
        color=0x2f3136
    )
    final_embed.add_field(name="Role", value=role.mention, inline=False)
    await status_msg.edit(embed=final_embed)

@imuteset.command(name="role")
@commands.has_permissions(manage_roles=True)
async def imuteset_role(ctx, *, role_input: str = None):
    """Configures image mute role"""
    guild = ctx.guild
    prefix = p(ctx)

    if imute_not_set(guild):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `imute` system not set up yet. Run `{prefix}imuteset` first.",
            ctx, include_author=False
        ))

    if role_input is None:
        embed = create_embed(
            "command: imuteset role",
            "Edits imute role", ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Roles`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}imuteset role @role\n\u001b[35mexample: \u001b[0m{prefix}imuteset role @no image```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    new_role = resolve_role(guild, role_input)

    if new_role is None:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Role `{role_input}` not found.",
            ctx, include_author=False
        ))
    
    config = get_imute_role_id(guild.id)
    old_role = guild.get_role(config) if config else None
    if old_role:
        for ch in guild.channels:
            try:
                await ch.set_permissions(old_role, overwrite=None)
            except discord.Forbidden:
                pass
    
    for ch in guild.channels:
        try:
            perms = ch.overwrites_for(new_role)
            perms.attach_files = False
            perms.embed_links = False
            await ch.set_permissions(new_role, overwrite=perms)
        except discord.Forbidden:
            pass
    
    set_imute_role_id(guild.id, new_role.id)
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `imute` role updated to {new_role.mention}.",
        ctx, include_author=False
    ))

# ===========================
#          imute
# ===========================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def imute(ctx, member: discord.Member = None, *, reason=None):
    """Toggles a member's image permissions """
    if imute_not_set(ctx.guild):
        return await imute_instruction_embed(ctx)

    prefix = get_prefix(bot, ctx.message)

    if not member:
        embed = create_embed("command: imute", "Toggles a member's image permissions", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}imute <member> (reason)\n\u001b[35mexample:\u001b[0m {prefix}imute zeph trash memes```",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    if member == ctx.author:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: You cannot `imute` yourself.",
            ctx,
            include_author=False
        ))

    role_id = get_imute_role_id(ctx.guild.id)
    imute_role = ctx.guild.get_role(role_id)

    if not imute_role:
        return await imute_instruction_embed(ctx)

    if imute_role in member.roles:
        await member.remove_roles(imute_role)
        await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: **{member.name}** can now send images again.",
        ctx, color=0x71906e,
        include_author=False
    ))
    else:
        await member.add_roles(imute_role)
        create_case(ctx.guild.id, member.id, "imute", reason, ctx.author.id)
        await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: **{member.name}** has been revoked of their image perms. **Reason**: {reason or 'n/a'}",
            ctx, color=0x963939,
            include_author=False
        ))

# ===========================
#      PER-SERVER RMUTE
# ===========================

def rmute_not_set(guild):
    role_id = get_rmute_role_id(guild.id)
    if role_id is None:
        return True

    role = guild.get_role(role_id)
    if not role:
        # clean invalid entry
        delete_rmute_role(guild.id)
        return True

    return False


async def rmute_instruction_embed(ctx):
    prefix = get_prefix(bot, ctx.message)

    embed = discord.Embed(
        description=(
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: "
            "`rmute` system is **not set**.\n\n"
            f"To set it up, use:\n```{prefix}rmuteset <role>```"
        ),
        color=0x2f3136
    )
    embed.set_footer(text="TIP: You can provide an existing role, or let the bot create one.")
    await ctx.send(embed=embed)


# ===========================
#         rmuteset
# ===========================

@bot.group(invoke_without_command=True)
@commands.has_permissions(moderate_members=True, manage_roles=True)
async def rmuteset(ctx, *, role_arg=None):
    """Configures reaction mute system in the server"""
    guild = ctx.guild
    prefix = get_prefix(bot, ctx.message)

    if not rmute_not_set(guild):
        config = get_rmute_role_id(guild.id)
        role = guild.get_role(config)
        embed = create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `rmute` system is already set.",
            ctx,
            include_author=False
        )
        embed.add_field(name="Role", value=role.mention if role else "`deleted`", inline=True)
        embed.set_footer(text=f"To change: {prefix}rmuteset role <role>")
        return await ctx.send(embed=embed)

    loading_embed = create_embed(
        "",
        "<a:sword_spin:1211611749426667560>  Setting up `rmute` system, this might take a while.",
        ctx,
        include_author=False
    )
    status_msg = await ctx.send(embed=loading_embed)

    # Auto-create role
    if role_arg is None:
        role = await guild.create_role(
            name="rmuted",
            reason="auto-created rmute role"
        )
    else:
        role = None

        # Mentioned role
        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]

        # Exact name
        if role is None:
            role = resolve_role(guild, role_arg)

        # Create new if not found
        if role is None:
            role = await guild.create_role(
                name=role_arg,
                reason="created via rmuteset command"
            )

    # Apply NO REACTIONS to all channels
    for ch in guild.channels:
        try:
            perms = ch.overwrites_for(role)
            perms.add_reactions = False
            await ch.set_permissions(role, overwrite=perms)
        except:
            pass

    # Save per-server role
    set_rmute_role_id(guild.id, role.id)

    final_embed = discord.Embed(
        description=(
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: "
            "`rmute` role has been set."
        ),
        color=0x2f3136
    )
    final_embed.add_field(name="Role", value=role.mention, inline=False)
    await status_msg.edit(embed=final_embed)

@rmuteset.command(name="role")
@commands.has_permissions(manage_roles=True)
async def rmuteset_role(ctx, *, role_input: str = None):
    """Configures reaction mute role"""
    guild = ctx.guild
    prefix = p(ctx)

    if rmute_not_set(guild):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `rmute` system not set up yet. Run `{prefix}rmuteset` first.",
            ctx, include_author=False
        ))

    if role_input is None:
        embed = create_embed(
            "command: rmuteset role",
            "Edits rmute role", ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Roles`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}rmuteset role @role\n\u001b[35mexample: \u001b[0m{prefix}rmuteset role @no react```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    new_role = resolve_role(guild, role_input)
    
    if new_role is None:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Role `{role_input}` not found.",
            ctx, include_author=False
        ))
    
    config = get_rmute_role_id(guild.id)
    old_role = guild.get_role(config) if config else None
    if old_role:
        for ch in guild.channels:
            try:
                await ch.set_permissions(old_role, overwrite=None)
            except discord.Forbidden:
                pass
    
    for ch in guild.channels:
        try:
            perms = ch.overwrites_for(new_role)
            perms.add_reactions = False
            await ch.set_permissions(new_role, overwrite=perms)
        except discord.Forbidden:
            pass
    
    set_rmute_role_id(guild.id, new_role.id)
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: `rmute` role updated to {new_role.mention}.",
        ctx, include_author=False
    ))


# ===========================
#           rmute
# ===========================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def rmute(ctx, member: discord.Member = None, *, reason=None):
    """Toggles a member's reaction permissions"""
    if rmute_not_set(ctx.guild):
        return await rmute_instruction_embed(ctx)

    prefix = get_prefix(bot, ctx.message)

    # Instruction
    if not member:
        embed = create_embed("command: rmute", "Toggles a member's reaction permissions", ctx)
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Moderate Members`",
        inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}rmute <member> (reason)\n\u001b[35mexample:\u001b[0m {prefix}rmute zeph stop sobbing yourself```",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Prevent self rmute
    if member == ctx.author:
        return await ctx.send(embed=create_embed(
            "",
            f"{ctx.author.mention}: You cannot `rmute` yourself.",
            ctx,
            include_author=False
        ))

    role_id = get_rmute_role_id(ctx.guild.id)
    rmute_role = ctx.guild.get_role(role_id)

    if not rmute_role:
        return await rmute_instruction_embed(ctx)

    # Already muted
    if rmute_role in member.roles:
        await member.remove_roles(rmute_role)
        await ctx.send(embed=create_embed(
        "",
        f"{ctx.author.mention}: **{member.name}** can now add reactions again.",
        ctx,
        color=0x71906e,
        include_author=False
    ))
    else:
        await member.add_roles(rmute_role)
        create_case(ctx.guild.id, member.id, "rmute", reason, ctx.author.id)
        await ctx.send(
            embed=create_embed(
                "",
                f"{ctx.author.mention}: **{member.name}** has been revoked of their reaction perms. **Reason:** {reason or 'n/a'}",
                ctx,
                color=0x963939,
                include_author=False
            )
        )
    
@bot.command(aliases=["sm"])
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, duration: str = None):
    """Set slowmode for a channel"""
    prefix = p(ctx)

    if duration is None:
        embed = create_embed(
            "command: slowmode",
            "Set slowmode for a channel", ctx
        )
        embed.add_field(
            name="Aliases",
            value=alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Channels`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}slowmode <duration>\n\u001b[35mexample: \u001b[0m{prefix}slowmode 5m```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    if duration.lower() in ("off", "0", "disable"):
        if ctx.channel.slowmode_delay == 0:
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Slowmode is already turned off.",
                ctx, include_author=False
            ))
        await ctx.channel.edit(slowmode_delay=0)
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Slowmode has been turned off in {ctx.channel.mention}.",
            ctx, include_author=False
        ))
    
    try:
        amount = int(duration[:-1])
        unit = duration[-1].lower()

        if unit == "s":
            seconds = amount
        elif unit == "m":
            seconds = amount * 60
        elif unit == "h":
            seconds = amount * 3600
        else:
            raise ValueError("Invalid unit")
    except (ValueError, IndexError):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Invalid duration. Use `s`, `m`, or `h`. Example: `10s`, `1m`, `1h`.",
            ctx, include_author=False
        ))
    
    if seconds < 1:
        return await ctx.send("what is 0s slowmode gonna do bro...")
    if seconds > 21600:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Maximum duration is `6h` (21600 seconds).",
            ctx, include_author=False
        ))
    
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Slowmode set to `{duration}` in {ctx.channel.mention}.",
        ctx, include_author=False
    ))

@bot.command(aliases=["r"])
@commands.has_permissions(manage_roles=True)
async def role(ctx, user: str = None, *, role: str = None):
    """Assign/remove role from a user"""

    prefix = p(ctx)

    # ===========================
    #   Missing Arguments
    # ===========================
    if user is None or role is None:
        embed = create_embed(
            "command: role",
            "Assign/remove a role from a user",
            ctx,
            include_author=True
        )
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}role <member> <role>\n\u001b[35mexample:\u001b[0m {prefix}role john member```",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # ===========================
    #   Find Member
    # ===========================
    member = None

    # If user mentioned
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
    else:
        search = user.lower()
        member = discord.utils.find(
            lambda m: search in m.name.lower()
            or search in m.display_name.lower()
            or search in str(m).lower(),
            ctx.guild.members
        )

    if member is None:
        await ctx.send(
            embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Could not find user `{user}`.",
                ctx,
                include_author=False
            )
        )
        return

    # ===========================
    #   Find Role
    # ===========================
    role_obj = None

    if ctx.message.role_mentions:
        role_obj = ctx.message.role_mentions[0]
    else:
        search_role = role.lower()
        role_obj = discord.utils.find(
            lambda r: search_role in r.name.lower(),
            ctx.guild.roles
        )

    if role_obj is None:
        await ctx.send(
            embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Could not find role `{role}`.",
                ctx,
                include_author=False
            )
        )
        return

    # ===========================
    #   Assign / Remove Role
    # ===========================
    try:
        if role_obj in member.roles:
            await member.remove_roles(role_obj)
            await ctx.send(
                embed=create_embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Removed {role_obj.mention} from **{member.display_name}**.",
                    ctx,
                    include_author=False
                )
            )
        else:
            await member.add_roles(role_obj)
            await ctx.send(
                embed=create_embed(
                    "",
                    f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Assigned {role_obj.mention} to **{member.display_name}**.",
                    ctx,
                    include_author=False
                )
            )

    except discord.Forbidden:
        await ctx.send(
            embed=create_embed(
                "",
                "<a:sword_spin:1211611749426667560>  I don't have permission to manage that role.",
                ctx,
                include_author=False
            )
        )

@bot.command()
async def roleinfo(ctx, *, role_input: str = None):
    """View a specific role info or your own top role"""

    # If no role specified → use author's highest role
    if role_input is None:
        role = ctx.author.top_role
    else:
        role = resolve_role(ctx.guild, role_input)
        if role is None:
            return await ctx.send(
                embed=create_embed(
                    "",
                    f"Could not find a role matching **{role_input}**.",
                    ctx,
                    include_author=False
                )
            )

    # Collect member list
    members = [m.name for m in role.members]

    if len(members) > 7:
        displayed = members[:7]
        displayed.append("...")
        members_text = "\n".join(displayed)
    else:
        members_text = "\n".join(members) if members else "*No members*"

    hex_code = f"#{role.color.value:06X}"

    # Build embed
    embed = discord.Embed(
        title=role.name,
        color=role.color if role.color.value != 0 else 0x2f3136
    )

    embed.set_author(
        name=ctx.author.name,
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    if role.icon:
        embed.set_thumbnail(url=role.icon.url)

    embed.add_field(name="ID", value=f"`{role.id}`", inline=False)

    embed.add_field(
        name="Created",
        value=f"<t:{int(role.created_at.timestamp())}:F>",
        inline=False
    )

    embed.add_field(
        name="Hex",
        value=f"`{hex_code}`",
        inline=False
    )

    embed.add_field(
        name=f"Members ({len(role.members)})",
        value=members_text,
        inline=False
    )

    await ctx.send(embed=embed)

# -----------------------------
# Role management: autorole
# -----------------------------

@bot.group(aliases=["ar"], invoke_without_command=True)
@commands.has_permissions(manage_roles=True)
async def autorole(ctx):
    """Adds or removes auto-assign role(s)"""
    prefix = p(ctx)
    embed = create_embed(
        "command: autorole",
        "Adds or removes auto-assign role(s)",
        ctx
    )
    embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
    embed.add_field(name="**Subcommands**", value="`add`\n`remove`", inline=False)
    embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
    embed.add_field(
        name="**Utilization**",
        value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}autorole <add/remove> <role>\n\u001b[35mexample:\u001b[0m {prefix}autorole add @members```",
        inline=False
    )
    await ctx.send(embed=embed)

@autorole.command(name="add")
@commands.has_permissions(manage_roles=True)
async def autorole_add(ctx, *, role_input: str = None):
    """Sets a role to auto-assign to members upon joining"""
    prefix = p(ctx)
    
    if not role_input:
        embed = create_embed(
            "command: autorole add",
            "Sets a role to auto-assign to members upon joining",
            ctx
        )
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}autorole add <role>\n\u001b[35mexample: \u001b[0m{prefix}autorole add @members```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    role = resolve_role(ctx.guild, role_input.strip())
    if not role:
        msg = await ctx.send("Role not found. Use `@role` or `role ID`")
        await asyncio.sleep(3)
        return await msg.delete()
    
    if get_autorole(ctx.guild.id) == role.id:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: That role is already set as an auto-assign role.",
            ctx,
            include_author=False
        ))
    
    set_autorole(ctx.guild.id, role.id)
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: {role.mention} will be auto-assigned to new members upon joining.",
        ctx,
        include_author=False
    ))

@autorole.command(name="remove")
@commands.has_permissions(manage_roles=True)
async def autorole_remove(ctx, *, role_input: str = None):
    """Removes an existing autorole"""
    prefix = p(ctx)
    
    if not role_input:
        embed = create_embed(
            "command: autorole remove",
            "Removes an existing autorole",
            ctx
        )
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}autorole remove <role>\n\u001b[35mexample: \u001b[0m{prefix}autorole remove @members```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    role = resolve_role(ctx.guild, role_input.strip())
    if not role:
        msg = await ctx.send("Role not found. Use `@role` or `role ID`")
        await asyncio.sleep(3)
        return await msg.delete()
    
    if get_autorole(ctx.guild.id) != role.id:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: That role is not set as an auto-assign role.",
            ctx,
            include_author=False
        ))
    
    delete_autorole(ctx.guild.id)
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Auto-assign role {role.mention} has been removed.",
        ctx,
        include_author=False
    ))

@bot.event
async def on_member_join(member):
    if member.bot:
        return
    role_id = get_autorole(member.guild.id)
    if not role_id:
        return
    role = member.guild.get_role(int(role_id))
    if not role:
        print(f"Role ID {role_id} not found in {member.guild.name}")
        return
    try:
        await member.add_roles(role)
        print(f"Assigned {role.name} to {member}")
    except Exception as e:
        print(f"Failed to assign role to {member}: {e}")


# -----------------------------
# Role management: roleedit
# -----------------------------
@bot.group(aliases=["re"], invoke_without_command=True)
@commands.has_permissions(manage_roles=True)
async def roleedit(ctx):
    """Edits a role"""
    prefix = p(ctx)
    embed = create_embed("command: roleedit", "Edits a role", ctx)
    embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
    embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
    embed.add_field(
        name="**Subcommands**",
        value="`name`\n`color`",
        inline=False
    )
    embed.add_field(
        name="**Utilization**",
        value=(
            f"```ansi\n\u001b[35msyntax:\u001b[0m\n"
            f"{prefix}roleedit name <role> <newName>\n"
            f"{prefix}roleedit color <role> <color>```"
        ),
        inline=False
    )
    await ctx.send(embed=embed)

@roleedit.command(name="name")
@commands.has_permissions(manage_roles=True)
async def roleedit_name(ctx, role_input: str = None, *, new_name: str = None):
    """Edits a role's name"""
    prefix = p(ctx)
    
    if not role_input or not new_name:
        embed = create_embed(
            "command: roleedit name",
            "Edits a role's name",
            ctx
        )
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}roleedit name <role> <newName>\n\u001b[35mexample: \u001b[0m{prefix}roleedit name @members citizens```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    role = resolve_role(ctx.guild, role_input)
    if not role:
        return await ctx.send(embed=create_embed("", "<a:sword_spin:1211611749426667560>  Role not found.", ctx, include_author=False))
    
    try:
        await role.edit(name=new_name.strip())
    except Exception as e:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  Failed to update role name: `{e}`", ctx, include_author=False))
    
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Updated name for {role.mention}.",
        ctx,
        include_author=False
    ))

@roleedit.command(name="color")
@commands.has_permissions(manage_roles=True)
async def roleedit_color(ctx, role_input: str = None, hex_code: str = None):
    """Edits a role's color"""
    prefix = p(ctx)
    
    if not role_input or not hex_code:
        embed = create_embed(
            "command: roleedit color",
            "Edits a role's color",
            ctx
        )
        embed.add_field(name="**Aliases**", value=alss_ctx(ctx), inline=False)
        embed.add_field(name="**Permissions Required**", value="`Manage Roles`", inline=False)
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}roleedit color <role> <color>\n\u001b[35mexample: \u001b[0m{prefix}roleedit color @members #ff8800```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    role = resolve_role(ctx.guild, role_input)
    if not role:
        return await ctx.send(embed=create_embed("", "<a:sword_spin:1211611749426667560>  Role not found.", ctx, include_author=False))
    
    hex_code = hex_code.strip()
    if not (hex_code.startswith("#") and len(hex_code) == 7):
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Invalid hex code. Format: `#RRGGBB` (e.g., `#ff8800`)",
            ctx,
            include_author=False
        ))
    
    try:
        color = discord.Color(int(hex_code.replace("#", "0x"), 16))
        await role.edit(color=color)
    except Exception as e:
        return await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  Failed to update color: `{e}`", ctx, include_author=False))
    
    await ctx.send(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Updated color for {role.mention}.",
        ctx,
        include_author=False
    ))

    
# -----------------------------
# Prefix version: just an instruction embed
# -----------------------------
@bot.command()
async def embed(ctx):
    """Creates a custom embed"""
    embed = create_embed(
        "command: embed",
        "Creates a custom embed",
        ctx)
    embed.add_field(
    name="**Aliases**",
    value=alss_ctx(ctx),
    inline=False
    )
    embed.add_field(
    name="**Permissions Required**",
    value="`n/a`",
    inline=False
    )
    embed.add_field(name="**Utilization**", value="```ansi\n\u001b[35msyntax:\u001b[0m /embed```", inline=False)
    await ctx.send(embed=embed)

# ---------- Interactive Embed Builder (standalone, slash command) ----------

# builder state stored per user (memory only)
# structure: {user_id: {"state": {...}, "channel_id": int}}
builder_states = {}

EMBED_PREVIEW_FOOTER = "Edit your embed below."
EMBED_PREVIEW_DESCRIPTION = "This is a preview."

def make_preview_embed(data: dict):

    # --- safe color parsing (only part that changes) ---
    raw_color = data.get("color", "2f3136") or "2f3136"
    try:
        color_value = int(raw_color.lstrip("#"), 16)
    except:
        color_value = int("2f3136", 16)
    # -----------------------------------------------------

    embed = discord.Embed(
        title=data.get("title") or None,
        description=data.get("description") or "This is a preview.",
        color=color_value
    )

    # Author
    if data.get("author"):
        embed.set_author(
            name=data["author"],
            icon_url=data.get("author_icon") or None
        )

    # Thumbnail
    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"])

    # ➜ FIELD PREVIEW LOOP GOES HERE
    for field in data.get("fields", []):
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field.get("inline", False)
        )

    # Footer
    footer = data.get("footer")
    if footer:
        embed.set_footer(text=data["footer"])

    return embed

# ---------- Modals ----------
class TitleModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Set Title")

        # IMPORTANT:
        # TextInputs must be created inside __init__
        # or Discord will treat them as static and modal breaks after 1 submit.
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Enter embed title",
            required=False,
            max_length=256
        )

        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id

        data = builder_states.setdefault(
            uid, {"state": {}, "channel_id": interaction.channel_id}
        )["state"]

        data["title"] = (
            self.title_input.value.strip() if self.title_input.value else ""
        )

        preview = make_preview_embed(data)

        await interaction.response.edit_message(
            embed=preview,
            view=EmbedBuilderView(uid)
        )

class DescriptionModal(discord.ui.Modal, title="Set Description"):
    desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="Enter description", required=False, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        data = builder_states.setdefault(uid, {"state": {}, "channel_id": interaction.channel_id})["state"]
        data["description"] = self.desc.value.strip() if self.desc.value else ""
        preview = make_preview_embed(data)
        await interaction.response.edit_message(embed=preview, view=EmbedBuilderView(uid))

class ColorModal(discord.ui.Modal, title="Set Embed Color"):
    color = discord.ui.TextInput(
        label="Hex color (#RRGGBB)",
        required=False,
        placeholder="#2f3136 (default)"
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        data = builder_states.setdefault(
            uid,
            {"state": {}, "channel_id": interaction.channel_id}
        )["state"]

        value = self.color.value.strip()

        if value:
            # store raw value, parsing happens in preview builder
            data["color"] = value
        else:
            # blank = delete custom color
            data["color"] = "2f3136"

        preview = make_preview_embed(data)

        await interaction.response.edit_message(
            embed=preview,
            view=EmbedBuilderView(uid)
        )

class AuthorModal(discord.ui.Modal, title="Set Author"):
    name = discord.ui.TextInput(label="Author name", required=False, max_length=256)
    icon = discord.ui.TextInput(
        label="Author icon URL (optional)",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id

        record = builder_states.setdefault(uid, {"state": {}, "channel_id": interaction.channel_id})
        data = record["state"]

        data["author"] = self.name.value.strip() or ""
        data["author_icon"] = self.icon.value.strip() or ""

        preview = make_preview_embed(data)
        await interaction.response.edit_message(embed=preview, view=EmbedBuilderView(uid))

class ThumbnailModal(discord.ui.Modal, title="Set Thumbnail"):
    url = discord.ui.TextInput(label="Thumbnail URL", required=False, placeholder="https://...")

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        data = builder_states.setdefault(uid, {"state": {}, "channel_id": interaction.channel_id})["state"]
        data["thumbnail"] = self.url.value.strip() if self.url.value else ""
        preview = make_preview_embed(data)
        await interaction.response.edit_message(embed=preview, view=EmbedBuilderView(uid))

class FooterModal(discord.ui.Modal, title="Set Footer"):
    footer = discord.ui.TextInput(
        label="Footer text",
        required=False,
        placeholder="Leave blank for no footer",
        max_length=2048
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        data = builder_states.setdefault(
            uid,
            {"state": {}, "channel_id": interaction.channel_id}
        )["state"]

        text = self.footer.value.strip()

        if text:
            data["footer"] = text           # keep footer
        else:
            data.pop("footer", None)        # remove footer entirely

        preview = make_preview_embed(data)

        await interaction.response.edit_message(
            embed=preview,
            view=EmbedBuilderView(uid)
        )

class AddFieldModal(discord.ui.Modal, title="Add Field"):
    name = discord.ui.TextInput(
        label="Field name",
        required=True,
        max_length=256
    )

    value = discord.ui.TextInput(
        label="Field value",
        style=discord.TextStyle.long,
        required=True,
        max_length=1024
    )

    inline = discord.ui.TextInput(
        label="Inline? (yes/no)",
        required=False,
        max_length=5,
        default="no"
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id

        # Create field entry
        entry = {
            "name": self.name.value.strip(),
            "value": self.value.value.strip(),
            "inline": (self.inline.value.lower() == "yes")
        }

        # Get or create the builder state
        record = builder_states.setdefault(uid, {"state": {}, "channel_id": interaction.channel_id})
        data = record["state"]

        # Append field slot
        data.setdefault("fields", []).append(entry)

        # Rebuild preview embed
        preview = make_preview_embed(data)

        # Update the builder UI
        await interaction.response.edit_message(
            embed=preview,
            view=EmbedBuilderView(uid)
        )

# ---------- View w/ Dropdown ----------
class EmbedBuilderView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        # add the select to the view
        self.add_item(EmbedComponentSelect(user_id))

class EmbedComponentSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(label="Title", description="Set or clear the embed title"),
            discord.SelectOption(label="Description", description="Set or clear the description"),
            discord.SelectOption(label="Color", description="Set your embed's color"),
            discord.SelectOption(label="Add Field", description="Add a field (name + value)"),
            discord.SelectOption(label="Author", description="Set author name + icon URL"),
            discord.SelectOption(label="Thumbnail", description="Set thumbnail URL"),
            discord.SelectOption(label="Footer", description="Set footer text"),
            discord.SelectOption(label="Finish & Send", description="Post the final embed in this channel"),
            discord.SelectOption(label="Cancel", description="Abort and clear builder")
        ]
        super().__init__(placeholder="Edit component...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        # ensure only the command author can interact
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("You are not the author of this builder.", ephemeral=True)

        choice = self.values[0]
        uid = interaction.user.id
        # ensure state exists
        record = builder_states.setdefault(uid, {"state": {}, "channel_id": interaction.channel_id})
        data = record["state"]

        # Route the choices
        if choice == "Title":
            await interaction.response.send_modal(TitleModal())
            return
        if choice == "Description":
            await interaction.response.send_modal(DescriptionModal())
            return
        if choice == "Color":
            await interaction.response.send_modal(ColorModal())
            return
        if choice == "Add Field":
            await interaction.response.send_modal(AddFieldModal())
            return
        if choice == "Author":
            await interaction.response.send_modal(AuthorModal())
            return
        if choice == "Thumbnail":
            await interaction.response.send_modal(ThumbnailModal())
            return
        if choice == "Footer":
            await interaction.response.send_modal(FooterModal())
            return
        if choice == "Cancel":
            # clear and inform
            builder_states.pop(uid, None)
            await interaction.response.edit_message(content="<a:sword_spin:1211611749426667560>  Embed builder cancelled.", embed=None, view=None)
            return
        if choice == "Finish & Send":
            # Build final embed and send it publicly to the channel where the command was used.
            target_channel_id = record.get("channel_id") or interaction.channel_id
            channel = interaction.client.get_channel(target_channel_id) or interaction.channel
            final_embed = make_preview_embed(data)
            try:
                await channel.send(embed=final_embed)
            except Exception as e:
                # if send fails, notify user
                await interaction.response.send_message(f"Failed to send embed: {e}", ephemeral=True)
                return

            builder_states.pop(uid, None)
            await interaction.response.edit_message(content="<a:sword_spin:1211611749426667560>  Embed sent!", embed=None, view=None)
            return

# ---------- Slash command ----------
@bot.tree.command(name="embed", description="Open the interactive embed builder (ephemeral preview)")
async def embed(interaction: discord.Interaction):
    uid = interaction.user.id
    # initialize state if not exists
    builder_states[uid] = {
        "state": {
            # initial empty state; description prefilled by make_preview_embed
            "title": "",
            "description": "",
            "author_name": "",
            "author_icon": "",
            "thumbnail": "",
            "fields": [],
            "footer": ""
        },
        "channel_id": interaction.channel_id  # where the final embed will be posted
    }
    preview = make_preview_embed(builder_states[uid]["state"])

    # send ephemeral initial builder message with the preview
    await interaction.response.send_message(embed=preview, view=EmbedBuilderView(uid), ephemeral=True)
    
# COMMANDS HELP

# =================== CUSTOM HELP COMMAND ===================

class HelpView(discord.ui.View):
    def __init__(self, ctx, pages):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.pages = pages
        self.index = 0
        self.message = None

    def get_embed(self):
        return self.pages[self.index]

    async def update(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index - 1) % len(self.pages)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index + 1) % len(self.pages)
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=None)
        except:
            pass
        self.stop()


def get_command_help_embed(ctx, command, parent_name=None):
    """Generate help embed for a single command."""
    prefix = p(ctx)
    
    # Full command name (including parent if it's a subcommand)
    if parent_name:
        full_name = f"{parent_name} {command.name}"
    else:
        full_name = command.name
    
    # Build usage string
    if isinstance(command, commands.Group):
        usage = f"{prefix}{full_name} <subcommand>"
    else:
        signature = command.signature or ""
        signature = signature.replace('[', '<').replace(']', '>')
        usage = f"{prefix}{full_name} {signature}".strip()
    
    embed = create_embed(
        f"command: {full_name}",
        command.help or "No description available.",
        ctx
    )
    
    # Aliases
    aliases = get_aliases_string(command)
    embed.add_field(name="**Aliases**", value=aliases, inline=False)
    
    # Permissions
    perms = []
    for check in command.checks:
        if hasattr(check, '__closure__') and check.__closure__:
            for cell in check.__closure__:
                obj = cell.cell_contents
                if isinstance(obj, dict) and 'permissions' in str(obj):
                    perm_names = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in obj.get('permissions', []))
                    if perm_names:
                        perms.append(perm_names)
    
    perm_str = ", ".join(perms) if perms else "`n/a`"
    embed.add_field(name="**Permissions Required**", value=perm_str, inline=False)
    
    # Subcommands for groups
    if isinstance(command, commands.Group):
        subcommands = "\n".join(f"`{cmd.name}`" for cmd in command.commands)
        embed.add_field(name="**Subcommands**", value=subcommands or "`n/a`", inline=False)
    
    # Usage
    embed.add_field(
        name="**Utilization**",
        value=f"```ansi\n\u001b[35msyntax:\u001b[0m {usage}```",
        inline=False
    )
    
    return embed

async def wait_for_confirmation(bot, author, channel, embed_message, command_message):
    def check(m):
        return (
            m.author.id == author.id
            and m.channel.id == channel.id
            and m.content.lower() == "close"
        )

    try:
        confirmation = await bot.wait_for("message", timeout=60, check=check)

        await embed_message.delete()
        await confirmation.delete()

    except asyncio.TimeoutError:
        pass
    
class Dropdown(discord.ui.Select):
    def __init__(self, ctx):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="/moderation", description="Bans, kicks, timeouts, jails, etc"),
            discord.SelectOption(label="/history", description="View, remove, and manage member case logs"),
            discord.SelectOption(label="/config", description="Set up and configure server systems"),
            discord.SelectOption(label="/rolemanagement", description="Assign, edit, and manage roles"),
            discord.SelectOption(label="/information", description="Look up users, servers, roles, and channels"),
            discord.SelectOption(label="/utilities", description="Translation, message snipes, AFK, embeds, and more"),
            discord.SelectOption(label="/games", description="Games like Guess the Country, Blacktea, Tic-Tac-Toe, and more (to come)"),
            discord.SelectOption(label="/misc", description="Everything else")
        ]

        super().__init__(placeholder="Select a category", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this menu.", self.ctx, include_author=False),
                ephemeral=True
            )

        prefix = get_prefix(self.ctx.bot, self.ctx.message)
        category = self.values[0]

        if category == "/moderation":
            desc = (
                f"`{prefix}ban` — Bans a member\n"
                f"`{prefix}unban` — Unbans a member\n"
                f"`{prefix}kick` — Kicks a member\n"
                f"`{prefix}timeout` — Times out a member\n"
                f"`{prefix}untimeout` — Removes timeout from a member\n"
                f"`{prefix}jail` — Sends a member to jail\n"
                f"`{prefix}unjail` — Releases a member from jail\n"
                f"`{prefix}warn` — Warns a member\n"
                f"`{prefix}warnings` — See all warnings for a member\n"
                f"`{prefix}forcename` — Forcibly changes a user's name\n"
                f"`{prefix}imute` — Toggles image permissions\n"
                f"`{prefix}rmute` — Toggles reaction permissions\n"
                f"`{prefix}purge` — Purges message(s)\n"
                f"`{prefix}slowmode` — Set a slowmode in a channel\n"
                f"`{prefix}lockdown` — Locks a channel\n"
                f"`{prefix}unlock` — Unlocks a channel\n"
            )

        elif category == "/history":
            desc = (
                f"`{prefix}history` — See a member's case log\n"
                f"`{prefix}history view` — View a case log by its number\n"
                f"`{prefix}history remove` — Remove a member's case log\n"
                f"`{prefix}history clear` — Clear all member's case logs\n"
            )
        	
        elif category == "/config":
            desc = (
                f"`{prefix}enablecommand` — Enables a command\n"
                f"`{prefix}disablecommand` — Disables a command\n"
                f"`{prefix}restrict` — Make a restriction for a command\n"
                f"`{prefix}unrestrict` — Removes a restriction from a command\n"
                f"`{prefix}autorole` — Adds or removes auto-assign role(s)\n"
                f"`{prefix}jailset` — Sets up a jail system\n"
                f"`{prefix}imuteset` — Sets up an imute system\n"
                f"`{prefix}rmuteset` — Sets up an rmute system\n"
                f"`{prefix}prefix` — Configure the bot's prefix\n"
            )
        
        elif category == "/rolemanagement":
            desc = (
                f"`{prefix}strip` — Strip a member off their role(s)\n"
                f"`{prefix}restore` — Restore/clear a member's role backup\n"
                f"`{prefix}role` — Assign/remove a role from a member\n"
                f"`{prefix}members` — See all members in a role\n"
                f"`{prefix}roleedit` — Edits a role\n"
                f"`{prefix}roleinfo` — See a role's information\n"
                f"`{prefix}roles` — See all roles in the server\n"
            )

        elif category == "/information":
            desc = (
                f"`{prefix}avatar` — Fetch a user's avatar\n"
                f"`{prefix}serveravatar` — Fetch a member's server avatar\n"
                f"`{prefix}guildicon` — Fetch the server icon\n"
                f"`{prefix}banner` — Fetch a user's banner\n"
                f"`{prefix}serverinfo` — See server's information\n"
                f"`{prefix}userinfo` — See a user's information\n"
                f"`{prefix}channelinfo` — See a channel's information\n"
                f"`{prefix}bots` — See all bots in the server\n"
                f"`{prefix}timezone` — See a user's timezone\n"
                f"`{prefix}timezone set` — Set a timezone based on location\n"
            )

        elif category == "/utilities":
            desc = (
                "`/sticky` — Sets a sticky message\n"
                "`/embed` — Sends a custom embed\n"
                f"`{prefix}autoresponder` — Configures an autoresponder system\n"
                f"`{prefix}snipe` — Snipes a deleted message\n"
                f"`{prefix}clearsnipe` — Clear sniped message\n"
                f"`{prefix}reactionsnipe` — Snipes a deleted reaction\n"
                f"`{prefix}clearreactionsnipe` — Clear reaction snipe\n"
                f"`{prefix}editsnipe` — Snipes an edited message\n"
                f"`{prefix}cleareditsnipe` — Clear edited snipe\n"
                f"`{prefix}define` — Get a definition of the specified word\n"
                f"`{prefix}ping` — See bot's latency\n"
                f"`{prefix}steal` — Steal emojis from other servers\n"
                f"`{prefix}urbandictionary` — Get the definition of a slang/word from Urban Dictionary\n"
                f"`{prefix}translate` — Translate text using Google Translate\n"
                f"`{prefix}afk` — Set AFK status\n"
            )

        elif category == "/games":
            desc = (
                f"`{prefix}flag` — Displays a random flag\n"
                f"`{prefix}flags` — Start a Guess the Flag game\n"
                f"`{prefix}blacktea` — Start a Blacktea game\n"
                f"`{prefix}tictactoe` — Challenge a member to a tic-tac-toe game\n"
            )
            
        elif category == "/misc":
            desc = (
                f"`{prefix}nightblade` — See bot's info\n"
                f"`{prefix}8ball` — Ask 8ball a yes-or-no question\n"
                f"`{prefix}nox` — **NOX AETERNUM**\n"
                f"`{prefix}out` — Leave the chat\n"
                f"`{prefix}zephfolk` — folk\n"
            )

        embed = discord.Embed(title=f"{category} commands", description=desc, color=EMBED_COLOR)
        embed.set_author(name=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")
        embed.set_footer(text="TIP:  type 'close' to close this embed.")

        await interaction.response.edit_message(embed=embed)


class View(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.timed_out = False
        self.add_item(Dropdown(ctx))

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            msg = await self.message.channel.fetch_message(self.message.id)
            embed = msg.embeds[0]
            embed.set_footer(text=None)
            await self.message.edit(embed=embed, view=None)
        except:
            pass

        self.stop()


@bot.command(aliases=["h"])
async def help(ctx, *, command_name: str = None):
    """Show command instructions"""
    prefix = p(ctx)
    
    # No command specified → show category menu (like ;commands)
    if command_name is None:
        embed = create_embed(
            "list of commands",
            "To show a list of commands, select a category below",
            ctx
        )
        embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")
        embed.set_footer(text="TIP:  type 'close' to close this embed.")
        
        view = View(ctx)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        await wait_for_confirmation(bot, ctx.author, ctx.channel, msg, ctx.message)
        return
    
    # Command specified
    cmd = bot.get_command(command_name)
    
    if cmd is None:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Command `{command_name}` not found. Use `{prefix}help` to see all commands.",
            ctx,
            include_author=False
        ))
    
    # Single command (not a group)
    if not isinstance(cmd, commands.Group):
        embed = get_command_help_embed(ctx, cmd)
        return await ctx.send(embed=embed)
    
    # Group command → paginate through subcommands
    pages = []
    
    # Main group page
    pages.append(get_command_help_embed(ctx, cmd))
    
    # Subcommand pages
    for subcmd in cmd.commands:
        pages.append(get_command_help_embed(ctx, subcmd, parent_name=cmd.name))
    
    # Send with pagination if more than 1 page
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        view = HelpView(ctx, pages)
        view.message = await ctx.send(embed=view.get_embed(), view=view)


# -----------------------------
# Utility: AFK
# -----------------------------
afk_users = {}  # user_id: (status, start_time)

@bot.command()
async def afk(ctx, *, status: str = "AFK"):
    """Sets an AFK status"""
    afk_users[ctx.author.id] = (status, discord.utils.utcnow())
    await ctx.reply(embed=create_embed(
        "",
        f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: you're now AFK with a status: {status}",
        ctx, include_author=False
    ), mention_author=False)

def strip_bot_mention(message, bot):
    content = message.content
    for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
        content = content.replace(mention, "")
    return content.strip().lower()

OWNER_ID = 1118719182062759967

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        content = strip_bot_mention(message, bot)
        if content == "":
            prefix = get_prefix(bot, message)
            embed = discord.Embed(
                description=(
                    f"{message.author.mention}: Current prefix is (`{prefix}`)\n\n"
                    f"To change the prefix, use:\n```{prefix}prefix <new_prefix>```\n"
                    f"-# (Administrator required)"
                ),
                color=0x2f3136
            )
            return await message.channel.send(embed=embed)
            
        elif "you up" in content.lower():
            if message.author.id == OWNER_ID:
                await message.reply("for you, sir, always", mention_author=False)

            else:
                await message.reply("yes", mention_author=False)

    # Remove AFK status if the AFK user sends a message
    if message.author.id in afk_users:
        status, start_time = afk_users.pop(message.author.id)
        duration = discord.utils.utcnow() - start_time
        minutes, seconds = divmod(int(duration.total_seconds()), 60)
        hours, minutes = divmod(minutes, 60)
        time_str = f"**{hours} hours**, **{minutes} minutes** and **{seconds} seconds**" if hours else f"**{minutes} minutes** and **{seconds} seconds**" if minutes else f"**{seconds} seconds**"
        await message.reply(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>  Welcome back {message.author.mention}, you were AFK for {time_str}.",
            message, include_author=False
        ), mention_author=False)

    # Notify if a mentioned user is AFK
    for user in message.mentions:
        if user.id in afk_users:
            status, _ = afk_users[user.id]
            await message.reply(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560>  {message.author.mention}: **{user.name}** is currently AFK. **Status:** {status}",
                message, include_author=False
            ), mention_author=False)

    if "y/n" in message.content.lower():
        await message.add_reaction("✅")
        await message.add_reaction("❌")

    if "sob/" in message.content.lower():
        await message.add_reaction("😭")

    await bot.process_commands(message)

from discord.ext import commands
@bot.command(aliases=["fn"])
@commands.has_permissions(manage_nicknames=True)
async def forcename(ctx, member: discord.Member = None, *, forced_name: str = None):
    """Forcibly changes and locks a user's name"""
    
    prefix = p(ctx)
    
    if not member:
        embed = create_embed(
            "command: forcename",
            "Forcibly changes and locks a user's name",
            ctx
        )
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Manage Nicknames`",
        inline=False
        )
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}forcename <member> <new_name>\n\u001b[35mexample:\u001b[0m {prefix}forcename zeph dumdum```", inline=False)
        await ctx.send(embed=embed)
        return

    # Check if bot has higher role than target
    if member.top_role >= ctx.author.top_role:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: You can't forcename someone with a role equal to or higher than yours.",
            ctx, include_author=False
        ))
    
    if member.id == ctx.author.id:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: You cannot forcename yourself.",
            ctx, include_author=False
        ))
    
    
    if member.top_role >= ctx.guild.me.top_role:
        return await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: I can't `forcename` someone with a higher role.",
            ctx, include_author=False
        ))

    entry = get_forced_nickname(ctx.guild.id, member.id)
    if entry:
        # Undo forcename
        original = entry["original"]
        try:
            if original is None or original == member.name:
                await member.edit(nick=None)
            else:
                await member.edit(nick=original)
        except:
            pass

        remove_forced_nickname(ctx.guild.id, member.id)
        return await ctx.send(embed=create_embed(
            "", f"{ctx.author.mention}: `forcename` on {member.mention} is undone.",
            ctx, color=0x71906e, include_author=False
        ))

    # Now we require a forced_name to apply a new nickname
    if not forced_name:
        embed = create_embed(
            "command: forcename",
            "Forcibly changes and locks a user's name",
            ctx
        )
        embed.add_field(
        name="**Aliases**",
        value=alss_ctx(ctx),
        inline=False
        )
        embed.add_field(
        name="**Permissions Required**",
        value="`Manage Nicknames`",
        inline=False
        )
        embed.add_field(name="**Utilization**", value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}forcename <member> <new_name>\n\u001b[35mexample: \u001b[0m{prefix}forcename zeph dumdum```", inline=False)
        await ctx.send(embed=embed)
        return

    # Apply new forced nickname and store original
    try:
        original = member.nick if member.nick else member.name
        set_forced_nickname(ctx.guild.id, member.id, original, forced_name)
        await member.edit(nick=forced_name)
    except:
        return await ctx.send("Failed to change nickname.")

    await ctx.send(embed=create_embed(
        "", f"{ctx.author.mention}: Forced {member.mention}'s name to **{forced_name}**",
        ctx, color=0x71906e, include_author=False
    ))

# Event: re-apply forced nicknames when a member changes their nickname
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # Only run for nickname changes (before.nick vs after.nick)
    if before.nick == after.nick:
        return

    entry = get_forced_nickname(after.guild.id, after.id)
    if not entry:
        return

    forced_name = entry["forced"]
    # If the current nickname is already the forced name, nothing to do
    if after.nick == forced_name:
        return

    try:
        # attempt to reapply forced nickname
        await after.edit(nick=forced_name)
    except Exception:
        # ignore failures (lack of permissions, hierarchy issues, etc.)
        pass
        
@bot.command(aliases=["ci"])
async def channelinfo(ctx, channel_input: str = None):
    """See channel info"""
    
    if channel_input is None:
        channel = ctx.channel
    else:
        channel = resolve_channel(ctx.guild, channel_input)
        if channel is None:
            return await ctx.send(
                embed=create_embed(
                    "",
                    f"Could not find a channel matching **{channel_input}**.",
                    ctx,
                    include_author=False
                )
            )  # default to the channel the command was used in

    embed = discord.Embed(
        title=channel.name,
        color=0x2f3136
    )

    # Author: user's display name & avatar
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url)

    # Thumbnail: guild icon
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    # Field: ID
    embed.add_field(name="ID", value=f"`{channel.id}`", inline=True)

    # Field: Created At
    embed.add_field(
        name="Created",
        value=f"<t:{int(channel.created_at.timestamp())}:F>",
        inline=True
    )

    slowmode = f"`{channel.slowmode_delay}s`" if channel.slowmode_delay else "`off`"
    embed.add_field(
        name="Slowmode",
        value=slowmode,
        inline=True
    )

    embed.add_field(
        name="Category",
        value=channel.category.name if channel.category else "*n/a*",
        inline=True
    )

    # Field: Type
    ctype = "Text Channel" if isinstance(channel, discord.TextChannel) else \
            "Voice Channel" if isinstance(channel, discord.VoiceChannel) else \
            "Category" if isinstance(channel, discord.CategoryChannel) else \
            "Channel"

    embed.add_field(name="Type", value=f"`{ctype}`", inline=True)

    embed.add_field(
        name="NSFW",
        value="`yes`" if channel.is_nsfw() else "`no`",
        inline=True
    )

    await ctx.send(embed=embed)


class MembersView(discord.ui.View):
    def __init__(self, ctx, role, members):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.role = role
        self.timed_out = False
        self.members = members
        self.per_page = 10
        self.index = 0
        self.message = None

    def get_embed(self):
        start = self.index * self.per_page
        end = start + self.per_page
        current_members = self.members[start:end]

        # Members formatted list
        if current_members:
            lines = "\n".join(
                [f"{i+1}. **{member.name}**" for i, member in enumerate(current_members, start=start)]
            )
        else:
            lines = "*No members found.*"

        embed = discord.Embed(
            title=f"{self.role.name}'s members",
            description=lines,
            color=self.role.color if self.role.color.value != 0 else 0x2f3136
        )

        # author
        embed.set_author(
            name=self.ctx.author.name,
            icon_url=self.ctx.author.avatar.url
        )

        if self.role.icon:
            embed.set_thumbnail(url=self.role.icon.url)

        # pagination footer
        total_pages = max(1, (len(self.members) - 1) // self.per_page + 1)
        embed.set_footer(text=f"{self.index + 1}/{total_pages}")

        return embed

    async def update(self, interaction):
        await interaction.response.edit_message(
            embed=self.get_embed(),
            view=self
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % max(1, (len(self.members) - 1) // self.per_page + 1)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % max(1, (len(self.members) - 1) // self.per_page + 1)
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=None)
        except:
            pass

        self.stop()

@bot.command(aliases=["inrole"])
async def members(ctx, *, role_input: str = None):
    """See all members that has a specific role or your own top role"""

    # if role not provided → use author's top role
    if role_input is None:
        role = ctx.author.top_role
    else:
        role = resolve_role(ctx.guild, role_input)
        if role is None:
            return await ctx.send(
                embed=create_embed(
                    "",
                    f"Could not find a role matching **{role_input}**.",
                    ctx,
                    include_author=False
                )
            )

    # fetch all members with that role
    members_list = [m for m in ctx.guild.members if role in m.roles]

    # ensure not empty
    if not members_list:
        return await ctx.send(
            embed=discord.Embed(
                description=f"No members found with the role **{role.name}**.",
                color=0x2f3136
            )
        )

    # make the pagination view
    view = MembersView(ctx, role, members_list)
    view.message = await ctx.send(embed=view.get_embed(), view=view)


        
# USER INFO UTILITY
def to_unix(dt: datetime):
    return int(dt.timestamp())


def time_ago(dt):
    now = datetime.now(timezone.utc)
    diff = now - dt

    seconds = int(diff.total_seconds())

    intervals = (
        ('year', 60 * 60 * 24 * 365),
        ('month', 60 * 60 * 24 * 30),
        ('day', 60 * 60 * 24),
        ('hour', 60 * 60),
        ('minute', 60),
        ('second', 1)
    )
    
    for name, count in intervals:
        value = seconds // count
        if value > 0:
            if value == 1:
                return f"{value} {name} ago"
            else:
                return f"{value} {name}s ago"

    return "just now"


@bot.command(aliases=["ui"])
async def userinfo(ctx, *, user: str = None):
    """See user's info"""

    # Default target = author
    if user is None:
        target = ctx.author
        is_member = True

    else:
        # Try mention or ID
        try:
            target = await bot.fetch_user(int(user.strip("<@!>")))
            is_member = ctx.guild.get_member(target.id) is not None

            if is_member:
                target = ctx.guild.get_member(target.id)

        except:
            # Try to find by partial name inside guild
            member_found = discord.utils.find(
                lambda m: user.lower() in m.name.lower() or user.lower() in m.display_name.lower(),
                ctx.guild.members
            )

            if member_found:
                target = member_found
                is_member = True
            else:
                # Fetch global user
                try:
                    target = await bot.fetch_user(user)
                    is_member = False
                except:
                    msg = await ctx.reply("User not found.", mention_author=False)
                    await asyncio.sleep(3)
                    await msg.delete()
                    await ctx.message.delete()
                    return

    # Dates
    created = target.created_at
    created_unix = int(created.timestamp())
    created_ago = time_ago(created)

    embed = discord.Embed(color=discord.Color.from_str("#2f3136"))

    embed.set_author(name=f"{target} ({target.id})")

    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)

    embed.add_field(
        name="**Created**",
        value=f"<t:{created_unix}:F>\n(`{created_ago}`)",
        inline=False
    )

    # ============================
    #      MEMBER FIELDS
    # ============================
    if is_member:
        target_member: discord.Member = target

        # Joined
        if target_member.joined_at:
            joined = target_member.joined_at
            joined_unix = int(joined.timestamp())
            joined_ago = time_ago(joined)

            embed.add_field(
                name="**Joined**",
                value=f"<t:{joined_unix}:F>\n(`{joined_ago}`)",
                inline=False
            )

        # Roles
        roles = [r for r in target_member.roles if r.name != "@everyone"][::-1]

        if len(roles) == 0:
            role_mentions = "None"
        else:
            trimmed = roles[:7]
            role_mentions = "\n".join([r.mention for r in trimmed])
            if len(roles) > 7:
                role_mentions += "**...**"

        embed.add_field(
            name=f"**Roles ({len(roles)})**",
            value=role_mentions,
            inline=False
        )

        # Member index
        sorted_members = sorted(
            ctx.guild.members,
            key=lambda m: m.joined_at or datetime.now(timezone.utc)
        )
        member_index = sorted_members.index(target_member) + 1

        embed.set_footer(text=f"Member #{member_index}  •  Requested by {ctx.author.display_name}")

    # ============================
    #      NON-MEMBER MODE
    # ============================
    else:
        # Count mutual guilds (between target user and ctx.author)
        mutuals = 0
        for g in bot.guilds:
            try:
                await g.fetch_member(target.id)
                if g.get_member(ctx.author.id):
                	mutuals += 1
                	
            except discord.NotFound:
            	pass
            except discord.Forbidden:
            	pass

        embed.set_footer(
            text=f"Mutual servers: {mutuals}  •  Requested by {ctx.author.display_name}"
        )

    await ctx.send(embed=embed)


@userinfo.error
async def userinfo_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        msg = await ctx.reply("User not found.", mention_author=False)
        await asyncio.sleep(3)
        await msg.delete()

# -----------------------------
# Test command
# -----------------------------
@bot.command()
async def ping(ctx):
    """See bot's latency"""

    ping_targets = [
        "Orion, the Iron Warrior",
        "Selene, Lady of the Abyss",
        "Kaelith, the Hollow Sentinel",
        "The Solar Paladin",
        "Zerath, the Crimson Fang",
        "Heolstor, the Nightlord",
        "Limveld",
        "Caelid",
        "Stormreach Citadel",
        "Typhon",
        "Limgrave",
        "idk what to put here",
        "who?",
        "the city of atlantis",
        "Jason Cintron",
        "uhhhhhh",
        "no one",
        "ChatGPT",
        "give me ideas what to put here",
        "hello",
        "a hooligan",
        "a nincompoop",
        "zeph's trash ass internet",
        "a random npc",
        "a discord mod",
        "why so many boss names",
        "what are all these pings 😭",
        "👀",
        "🫩",
        "hmmm",
        "a tuxedo cat named timmy",
        "a bat",
        "a lost child",
        "Lunaris, the Nightblade",
        "nobody to ping here.",
        "Zephyrax Bloodveil",
        "the Emperor",
        "the Queen of the Full Moon",
        "your fatass (jk)",
        "yours truly",
        "uhh wait",
        "your Highness",
        "/nightblade coming soon i hope",
        "Kadaku",
        "Jason Voorhees",
        "nightblade (formerly known as lunaris)",
    ]
    
    ultra_rare = f"secret command {get_prefix(bot, ctx.message)}batcave"
    
    choices = ping_targets + [ultra_rare]
    weights = [1] * len(ping_targets) + [0.001]
    
    target = random.choices(choices, weights=weights, k=1)[0]

    placeholder = await ctx.send("ping...")
    ws_latency = round(bot.latency * 1000)  # ms

    # Build embed with only description
    embed = discord.Embed(
        description=f"<a:sword_spin:1211611749426667560>  It took `{ws_latency}ms` to ping **{target}**",
        color=discord.Color.from_str("#2f3136")
    )

    # Edit placeholder
    await placeholder.edit(content=None, embed=embed)
    
@bot.command(aliases=["av"])
async def avatar(ctx, user: discord.User = None):
    """See user's avatar or your own"""
    # Default to command author
    target = user or ctx.author

    # Fetch full user to ensure avatar/banner is available
    try:
        fetched = await bot.fetch_user(target.id)
    except:
        msg = await ctx.send("Couldn't fetch that user.")
        await asyncio.sleep(3)
        await msg.delete()
        return

    avatar_url = fetched.avatar.url if fetched.avatar else fetched.default_avatar.url

    # Embed color (member = top role color, non-member = neutral)
    if isinstance(target, discord.Member):
        color = target.color if target.color.value != 0 else 0x2f3136
    else:
        color = 0x2f3136

    # Create embed
    embed = discord.Embed(
        title=f"{fetched.display_name}'s avatar",
        url=avatar_url,
        color=color
    )
    embed.set_image(url=avatar_url)

    # Include command author if viewing someone else
    if target != ctx.author:
        embed.set_author(
            name=str(ctx.author),
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

    await ctx.send(embed=embed)

@bot.command(aliases=["sav", "gav"])
async def serveravatar(ctx, user: discord.User = None):
    """See user's server avatar or your own"""
    # Default to command author
    target = user or ctx.author

    member = ctx.guild.get_member(target.id)

    if member is None:
        return await ctx.send(embed=create_embed("", f"**{target.name}** is not a member of this server.",
        ctx,
        include_author=False))

    if member.id == ctx.author.id and member.guild_avatar is None:
        return await ctx.send(embed=create_embed(
            "",
            "You do **not** have a server avatar set.",
            ctx,
            include_author=False
        ))

    if not member.guild_avatar:
        return await ctx.send(embed=create_embed(
            "",
            f"**{member.display_name}** does not have a server avatar set.",
            ctx,
            include_author=False
        ))

    avatar_url = member.guild_avatar.url

    color = member.color if member.color.value != 0 else 0x2f3136

    embed = discord.Embed(
        title=f"{member.display_name}'s server avatar",
        url=avatar_url,
        color=color
    )
    embed.set_image(url=avatar_url)

    if member.id != ctx.author.id:
        embed.set_author(
            name=str(ctx.author),
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

    await ctx.send(embed=embed)
    
@bot.command(aliases=["gicon"])
async def guildicon(ctx):
    """See the server's icon"""
    guild = ctx.guild

    # Get server icon URL (supports GIF)
    icon_url = guild.icon.url if guild.icon else None

    if not icon_url:
        await ctx.send(embed=create_embed("", "This server has no icon.",
        ctx,
        include_author=False))
        return

    embed = discord.Embed(
        title=f"{guild.name}'s icon",
        url=icon_url,
        color=0x2f3136
    )

    embed.set_image(url=icon_url)

    await ctx.send(embed=embed)
    
@bot.command()
async def banner(ctx, user: discord.User = None):
    """See user's banner or your own"""
    # Use command author if no user specified
    target = user or ctx.author

    # Always fetch the full user to ensure banner is available
    try:
        fetched = await bot.fetch_user(target.id)
    except:
        msg = await ctx.send("Couldn't fetch that user.")
        await asyncio.sleep(3)
        await msg.delete()
        return

    banner = fetched.banner

    if banner is None:
        msg = await ctx.send("That user has no banner set.")
        await asyncio.sleep(3)
        await msg.delete()
        return

    banner_url = banner.url

    # Embed color matches top role color IF they're a member
    if isinstance(target, discord.Member):
        color = target.color if target.color.value != 0 else 0x2f3136
    else:
        # Non-member → neutral color
        color = 0x2f3136

    # Create embed
    embed = discord.Embed(
        title=f"{fetched.display_name}'s banner",
        url=banner_url,
        color=color
    )
    embed.set_image(url=banner_url)

    # Add author info if viewing someone else
    if target != ctx.author:
        embed.set_author(
            name=str(ctx.author),
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

    await ctx.send(embed=embed)
    
@bot.command(aliases=["lock"])
@commands.has_permissions(manage_channels=True)
async def lockdown(ctx):
    """Locks down a channel"""
    channel = ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)

    # Check if already locked
    if overwrite.send_messages is False:
        return await ctx.send(embed=create_embed("", "🔒  Channel is already locked.", ctx, include_author=False))

    # Lock it
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    msg = await ctx.send("🔒")
    await asyncio.sleep(3)
    await msg.delete()
    
@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    """Unlocks a channel"""
    channel = ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)

    if overwrite.send_messages is True or overwrite.send_messages is None:
        return await ctx.send(embed=create_embed("", "🔓  Channel is not locked.", ctx, include_author=False))

    overwrite.send_messages = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    msg = await ctx.send("🔓")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount=5):
    """Purge messages in a channel"""
    await ctx.channel.purge(limit=amount)

@bot.command()
@commands.has_permissions(manage_emojis=True)
async def steal(ctx, emoji: discord.PartialEmoji | None = None, *, name: str | None = None):
    """Steal emojis from other servers"""

    prefix = p(ctx)

    if not emoji:
        embed = create_embed(
            "command: steal",
            "Steal emojis from other servers",
            ctx
        )
        embed.add_field(
            name="Permissions Required",
            value="`Manage Emojis`",
            inline=False
        )
        embed.add_field(
            name="Utilization",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}steal <emoji> (name)\n\u001b[35mexample:\u001b[0m {prefix}steal <:nightblade:1446122411341910026> sword```",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    emoji_name = name or emoji.name
    emoji_ext = "gif" if emoji.animated else "png"
    emoji_url = f"https://cdn.discordapp.com/emojis/{emoji.id}.{emoji_ext}"

    async with aiohttp.ClientSession() as session:
        async with session.get(emoji_url) as resp:
            if resp.status != 200:
                await ctx.send(
                    embed=create_embed(
                        "",
                        "Failed to get emoji.",
                        ctx,
                        include_author=False
                    )
                )
                return
            image_bytes = await resp.read()

    try:
        new_emoji = await ctx.guild.create_custom_emoji(
            name=emoji_name,
            image=image_bytes,
            reason=f"Stolen by {ctx.author}"
        )
    except discord.Forbidden:
        await ctx.send(
            embed=create_embed(
                "",
                "I don't have permission to steal emojis.",
                ctx,
                include_author=False
            )
        )
        return
    except discord.HTTPException:
        await ctx.send(
            embed=create_embed(
                "",
                "Emoji limit reached or invalid emoji.",
                ctx,
                include_author=False
            )
        )
        return
    
    if new_emoji.animated:
        await ctx.send(
            embed=create_embed(
                "",
                f"{ctx.author.mention}: Added <a:{new_emoji.name}:{new_emoji.id}> with the name `{new_emoji.name}`",
                ctx,
                include_author=False
            )
        )
    else:
        await ctx.send(
            embed=create_embed(
                "",
                f"Added <:{new_emoji.name}:{new_emoji.id}> with the name `{new_emoji.name}`",
                ctx,
                include_author=False
            )
        )

class InvBtn(discord.ui.View):
    def __init__(self, inv: str):
        super().__init__()
        self.inv = inv
        self.add_item(discord.ui.Button(label="Invite", url=self.inv))

@bot.command(aliases=["nb"])
async def nightblade(ctx):
    """See bot's info"""

    inv = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&integration_type=0&scope=bot+applications.commands"

    total_commands = 0
    for command in bot.commands:
        total_commands += 1
        if isinstance(command, commands.Group):
            total_commands += len(command.commands)

    total_servers = len(bot.guilds)
    total_users = sum(g.member_count for g in bot.guilds)

    process = psutil.Process()
    cpu = process.cpu_percent(interval=0.1)
    mem = process.memory_info().rss / (1024**2)

    created = bot.user.created_at
    created_unix = int(created.timestamp())
    created_ago = time_ago(created)

    embed = create_embed(
        "",
        f"**{bot.user.name}** is designed to be a fully functional all-in-one bot, developed by **zeph**\nUtilizing `{total_commands}` commands and more to come as development continues.",
        ctx
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1069850380114067490/1437817233907912817/lv_0_20240227091826-ezgif.com-gif-maker.gif")
    embed.add_field(
        name="**Created**",
        value=f"<t:{created_unix}:f>\n(`{created_ago}`)",
        inline=False
    )
    embed.add_field(
        name="**Stats**",
        value=f"Users: `{total_users}`\nServers: `{total_servers}`",
        inline=True
    )
    embed.add_field(
        name="**System**",
        value=f"CPU: `{cpu:.1f}%`\nMemory: `{mem:.1f} MB`",
        inline=True
    )
    embed.set_footer(text="v1.0.0 (early development)")

    await ctx.send(embed=embed, view=InvBtn(str(inv)))

# TRANSLATE COMMAND

LANGUAGE_NAMES = {
    "af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic",
    "hy": "Armenian", "as": "Assamese", "ay": "Aymara", "az": "Azerbaijani",
    "bm": "Bambara", "eu": "Basque", "be": "Belarusian", "bn": "Bengali",
    "bho": "Bhojpuri", "bs": "Bosnian", "bg": "Bulgarian", "ca": "Catalan",
    "ceb": "Cebuano", "zh-CN": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)",
    "co": "Corsican", "hr": "Croatian", "cs": "Czech", "da": "Danish",
    "dv": "Dhivehi", "doi": "Dogri", "nl": "Dutch", "en": "English",
    "eo": "Esperanto", "et": "Estonian", "ee": "Ewe", "fil": "Filipino",
    "fi": "Finnish", "fr": "French", "fy": "Frisian", "gl": "Galician",
    "ka": "Georgian", "de": "German", "el": "Greek", "gn": "Guarani",
    "gu": "Gujarati", "ht": "Haitian Creole", "ha": "Hausa", "haw": "Hawaiian",
    "he": "Hebrew", "hi": "Hindi", "hmn": "Hmong", "hu": "Hungarian",
    "is": "Icelandic", "ig": "Igbo", "ilo": "Ilocano", "id": "Indonesian",
    "ga": "Irish", "it": "Italian", "ja": "Japanese", "jv": "Javanese",
    "kn": "Kannada", "kk": "Kazakh", "km": "Khmer", "rw": "Kinyarwanda",
    "gom": "Konkani", "ko": "Korean", "kri": "Krio", "ku": "Kurdish (Kurmanji)",
    "ckb": "Kurdish (Sorani)", "ky": "Kyrgyz", "lo": "Lao", "la": "Latin",
    "lv": "Latvian", "ln": "Lingala", "lt": "Lithuanian", "lg": "Luganda",
    "lb": "Luxembourgish", "mk": "Macedonian", "mai": "Maithili", "mg": "Malagasy",
    "ms": "Malay", "ml": "Malayalam", "mt": "Maltese", "mi": "Maori",
    "mr": "Marathi", "mni-Mtei": "Meitei", "lus": "Mizo", "mn": "Mongolian",
    "my": "Myanmar (Burmese)", "ne": "Nepali", "no": "Norwegian", "ny": "Nyanja",
    "or": "Odia", "om": "Oromo", "ps": "Pashto", "fa": "Persian",
    "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi", "qu": "Quechua",
    "ro": "Romanian", "ru": "Russian", "sm": "Samoan", "sa": "Sanskrit",
    "gd": "Scots Gaelic", "nso": "Sepedi", "sr": "Serbian", "st": "Sesotho",
    "sn": "Shona", "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "es": "Spanish", "su": "Sundanese",
    "sw": "Swahili", "sv": "Swedish", "tg": "Tajik", "ta": "Tamil",
    "tt": "Tatar", "te": "Telugu", "th": "Thai", "ti": "Tigrinya",
    "ts": "Tsonga", "tr": "Turkish", "tk": "Turkmen", "ak": "Twi",
    "uk": "Ukrainian", "ur": "Urdu", "ug": "Uyghur", "uz": "Uzbek",
    "vi": "Vietnamese", "cy": "Welsh", "xh": "Xhosa", "yi": "Yiddish",
    "yo": "Yoruba", "zu": "Zulu"
}
LANGUAGE_CODES = {v.lower(): k for k, v in LANGUAGE_NAMES.items()}

async def detect_language(text: str) -> str:
    import urllib.parse
    encoded = urllib.parse.quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={encoded}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if r.status == 200:
                data = await r.json()
                return data[2]
    return None

@bot.command(aliases=["tr"])
async def translate(ctx, language: str = None, *, text: str = None):
    """Translate text using Google Translate"""
    prefix = p(ctx)

    if language is None and text is None:
        ref = ctx.message.reference
        if ref is None:
            embed = create_embed(
                "command: translate",
                "Translate text using Google Translate", ctx
            )
            embed.add_field(
                name="Aliases",
                value=alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}translate (language) (text)\n\u001b[35mexample: \u001b[0m{prefix}translate en hola```",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        replied = await ctx.channel.fetch_message(ref.message_id)
        if not replied.content:
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: That message has no text to translate.",
                ctx, include_author=False
            ))
        target_lang = "en"
        source_text = replied.content

    else:
        if language is None:
            embed = create_embed(
                "command: translate",
                "Translate text using Google Translate", ctx
            )
            embed.add_field(
                name="Aliases",
                value=alss_ctx(ctx),
                inline=False
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax: \u001b[0m{prefix}translate (language) (text)\n\u001b[35mexample: \u001b[0m{prefix}translate en hola```",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        if language and text is None:
            return await ctx.send(embed=create_embed(
                "",
                f"<a:sword_spin:1211611749426667560> {ctx.author.mention}: Provide a text to translate.",
                ctx, include_author=False
            ))
        
        original_input = language.lower()

        if original_input in LANGUAGE_NAMES:
            target_lang = original_input
        else:
            target_lang = LANGUAGE_CODES.get(original_input)
            if target_lang is None:
                return await ctx.send(embed=create_embed(
                    "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Unknown language code `{original_input}`. Use codes like `en`, `fr`, `de`, `ja`, etc.",
                    ctx, include_author=False
                ))
        
        source_text = text

    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(source_text)
    except LanguageNotSupportedException:
        return await ctx.send(embed=create_embed(
            "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Language `{target_lang}` is not supported.",
            ctx, include_author=False
        ))
    except Exception as e:
        return await ctx.send(embed=create_embed(
            "", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: Translation failed: `{e}`",
            ctx, include_author=False
        ))
    try:
        detected_code = await detect_language(source_text)
        from_name = LANGUAGE_NAMES.get(detected_code, detected_code.upper()) if detected_code else "Unknown"
    except:
        from_name = "Unknown"
    
    to_name = LANGUAGE_NAMES.get(target_lang, target_lang.capitalize())

    embed = create_embed(text, f"```{translated}```", ctx)
    embed.set_author(name="Google Translate", icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Google_Translate_logo.svg/960px-Google_Translate_logo.svg.png")
    embed.set_footer(text=f"Translated from {from_name} to {to_name}")
    await ctx.send(embed=embed)


@commands.cooldown(1, 5, BucketType.channel)
@bot.command()
async def nox(ctx, amount: int = 1):
    # Limit
    amount = max(1, min(amount, 7))

    # Build the repeated text
    result = "\n".join(["# NOX AETERNUM"] * amount)

    await ctx.send(result)
    
@nox.error
async def nox_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
    	await ctx.send(embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {ctx.author.mention}: This command is on `{error.retry_after:.1f}`s cooldown.", ctx, include_author=False))
    	
@bot.command(aliases=["leave", "fuckoff"])
async def out(ctx):
    await ctx.reply("take care", mention_author=False)

@bot.command()
async def oc(ctx):
    await ctx.send("https://cdn.discordapp.com/attachments/1069850380114067490/1445654781724201050/lv_0_20251130213805-ezgif.com-optimize.gif")

@bot.command(name="8ball")
async def ball(ctx, *, question: str = None):
    """Asks the magic 8-ball a yes-or-no question"""

    prefix = p(ctx)

    responses = [
        "Yes.",
        "mhmm",
        "i think so",
        "No.",
        "Maybe.",
        "Definitely.",
        "never ask me again",
        "hell no",
        "folk 😭😭😭😭😭😭😭",
        "ehhhhh i meannn",
        "yessir",
        "nah",
        "hell yeah",
        "i guess",
        "i'll lyk when i have the answer",
        "yea no",
        "naw",
        "nuh uh",
        "uh huh",
        "mmmaaaybe",
        "who knows",
        "ask zeph",
        "you tell me",
        f"{prefix}afk",
        f"{prefix}leave",
        "ofc bro 😂",
        "come again?",
        "beep boop",
        "indeed",
        "yup",
        "HELL YEAAAA",
        "FUK NAW 😭😭😭",
        "brb",
        "that goes without saying",
        "indubitably",
        "aaaabsolutely",
        "Absolutely not.",
        "Ask again later.",
        "It is certain.",
        "Very doubtful.",
        "Without a doubt.",
        "Duh.",
        "You may rely on it.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "Outlook not so good.",
        "Signs point to yes."
    ]

    if question is None:
        embed = create_embed(
            "command: 8ball",
            "Ask the magic 8-ball a yes-or-no question",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {p(ctx)}8ball <question>\n\u001b[35mexample:\u001b[0m {p(ctx)}8ball will nightblade ever be completed```",
            inline=False
        )
        return await ctx.send(embed=embed)


    answer = random.choice(responses)

    placeholder = await ctx.reply(embed=create_embed(
        "",
        f"🎱  hmmm",
        ctx,
        include_author=False
    ), mention_author=False)
    await asyncio.sleep(1.5)
    await placeholder.edit(embed=create_embed(
        "",
        f"🎱  {answer}",
        ctx,
        include_author=False
    ))

# -------------------------
# DEFINE COMMAND
# -------------------------

def clean_def(text: str) -> str:
    return text.replace("[", "").replace("]", "").strip()

class DefinitionView(discord.ui.View):
    def __init__(self, definitions, word, pronunciation, ctx):
        super().__init__(timeout=60)
        self.definitions = definitions
        self.word = word
        self.pronunciation = pronunciation
        self.timed_out = False
        self.index = 0
        self.ctx = ctx
        self.message = None

    # Build the embed for the current definition
    def get_embed(self):
        definition = self.definitions[self.index]

        embed = discord.Embed(
            description=f"# [{self.word} {self.pronunciation}](https://en.wiktionary.org/wiki/{self.word})\n{definition}",
            color=0x2f3136
        )
        embed.set_author(name="Wiktionary", icon_url="https://upload.wikimedia.org/wikipedia/commons/f/fc/Wiktionary_logo2_noW.png")
        embed.set_footer(text=f"{self.index + 1}/{len(self.definitions)}")

        return embed

    # Update the message when a button is clicked
    async def update(self, interaction):
        await interaction.response.edit_message(
            embed=self.get_embed(),
            view=self
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index - 1) % len(self.definitions)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index + 1) % len(self.definitions)
        await self.update(interaction)


    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=None)
        except:
            pass

        self.stop()

@bot.command(aliases=["def"])
async def define(ctx, *, word: str = None):
    """Get a definition of the specified word"""

    prefix = p(ctx)

    # ---------------------------------
    # CASE 1 — no word specified
    # ---------------------------------
    if word is None:
        embed = create_embed(
            "command: define",
            "Get a definition of the specified word",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value=alss_ctx(ctx),
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}define <word>\n\u001b[35mexample:\u001b[0m {prefix}define blade```",
            inline=False
        )
        return await ctx.send(embed=embed)

    # ---------------------------------
    # CASE 2 — word provided
    # ---------------------------------

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    async with ctx.typing():
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return await ctx.send(
                        embed=create_embed(
                            "",
                            f"Could not find a definition for **{word}**.",
                            ctx,
                            include_author=False))

                data = await r.json()

    # Extract definition
    try:
        definition = data[0]["meanings"][0]["definitions"][0]["definition"]
    except Exception:
        return await ctx.send(
            embed=create_embed(
                "",
                f"No definitions available for **{word}**.",
                ctx,
                include_author=False
            )
        )

    pronunciation = "n/a"
    try:
        pronunciation = data[0]["phonetics"][0].get("text")
    except Exception:
        pronunciation = "n/a"

    definitions = []

    try:
        for meaning in data[0]["meanings"]:
            for d in meaning["definitions"]:
                if "definition" in d:
                    definitions.append(clean_def(d["definition"]))
    except Exception as e:
        print("error extracting definitions:", e)

    if not definitions:
        return await ctx.send(
            embed=create_embed(
                "",
                f"No definitions found for **{word}**.",
                ctx,
                include_author=False
            )
        )


    # Send result
    view = DefinitionView(definitions, word, pronunciation, ctx)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

# URBAN DICTIONARY

class UrbanDictionaryView(discord.ui.View):
    def __init__(self, definitions, word, ctx):
        super().__init__(timeout=60)
        self.definitions = definitions
        self.word = word
        self.ctx = ctx
        self.index = 0
        self.message = None

    def get_embed(self):
        entry = self.definitions[self.index]
        
        embed = discord.Embed(
            title="",
            description=f"# [{entry["word"]}]({entry["permalink"]})\n{entry["definition"]}",
            color=0x2f3136
        )
        
        embed.set_author(
            name="Urban Dictionary",
            icon_url="https://cdn.discordapp.com/attachments/1069850380114067490/1473561929434796032/urbandictionary_logo.png"
        )
        
        embed.add_field(
            name="**Example**",
            value=entry["example"] or "*No example provided*",
            inline=False
        )
        
        embed.add_field(
            name="_ _",
            value=f"-# By **{entry['author']}**",
            inline=False
        )
        
        embed.set_footer(text=f"{self.index + 1}/{len(self.definitions)}")
        
        return embed

    async def update(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index - 1) % len(self.definitions)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index + 1) % len(self.definitions)
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=None)
        except:
            pass
        self.stop()


@bot.command(aliases=["ud", "urban"])
async def urbandictionary(ctx, *, word: str = None):
    """Get the definition of slang/word from Urban Dictionary"""
    prefix = p(ctx)
    
    if not word:
        embed = create_embed(
            "command: urbandictionary",
            "Get the definition of slang/word from Urban Dictionary",
            ctx
        )
        embed.add_field(
            name="**Aliases**",
            value="`ud`, `urban`",
            inline=False
        )
        embed.add_field(
            name="**Utilization**",
            value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}urbandictionary <word>\n\u001b[35mexample:\u001b[0m {prefix}urbandictionary folk```",
            inline=False
        )
        return await ctx.send(embed=embed)
    
    url = f"https://api.urbandictionary.com/v0/define?term={word}"
    
    async with ctx.typing():
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return await ctx.send(embed=create_embed(
                        "",
                        f"Could not find a definition for **{word}**.",
                        ctx,
                        include_author=False
                    ))
                
                data = await r.json()
    
    definitions = data.get("list", [])
    
    if not definitions:
        return await ctx.send(embed=create_embed(
            "",
            f"No definitions found for **{word}**.",
            ctx,
            include_author=False
        ))
    
    # Format definitions
    formatted_defs = []
    for entry in definitions:
        formatted_defs.append({
            "word": entry["word"],
            "definition": entry["definition"].replace("[", "").replace("]", ""),
            "example": entry["example"].replace("[", "").replace("]", "") if entry.get("example") else None,
            "author": entry.get("author", "Unknown"),
            "permalink": entry.get("permalink", f"https://www.urbandictionary.com/define.php?term={word}")
        })
    
    view = UrbanDictionaryView(formatted_defs, word, ctx)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

# ROLES COMMAND

class RolesView(discord.ui.View):
    def __init__(self, ctx, roles):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.roles = roles
        self.timed_out = False
        self.index = 0
        self.per_page = 10
        self.message = None

    # Build embed for current page
    def get_embed(self):
        start = self.index * self.per_page
        end = start + self.per_page
        current_roles = self.roles[start:end]

        # Format role list
        role_lines = "\n".join([f"{i+1}. {role.mention}" for i, role in enumerate(current_roles, start=start)])

        embed = discord.Embed(
            title=f"Roles in {self.ctx.guild.name}",
            description=role_lines if role_lines else "*No roles found.*",
            color=0x2f3136
        )
        embed.set_author(name=self.ctx.author.name, icon_url=self.ctx.author.avatar.url)
        embed.set_thumbnail(url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)

        # Footer (pagination)
        total_pages = max(1, (len(self.roles) - 1) // self.per_page + 1)
        embed.set_footer(text=f"{self.index + 1}/{total_pages}")

        return embed

    async def update(self, interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        total_pages = max(1, (len(self.roles) - 1) // self.per_page + 1)
        self.index = (self.index - 1) % total_pages
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        total_pages = max(1, (len(self.roles) - 1) // self.per_page + 1)
        self.index = (self.index + 1) % total_pages
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=None)
        except:
            pass

        self.stop()

@bot.command()
async def roles(ctx):
    """See all server roles"""

    # Get all roles EXCEPT @everyone
    roles = [role for role in ctx.guild.roles if role != ctx.guild.default_role]

    # If for some reason nothing is found
    if not roles:
        return await ctx.send(embed=create_embed(
            "",
            "This server has no assignable roles.",
            ctx,
            include_author=False
        ))

    # Sort roles by position (descending)
    roles = sorted(roles, key=lambda r: r.position, reverse=True)

    view = RolesView(ctx, roles)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

class BotsView(discord.ui.View):
    def __init__(self, bots, ctx):
        super().__init__(timeout=60)
        self.bots = bots
        self.ctx = ctx
        self.timed_out = False
        self.index = 0
        self.per_page = 10
        self.message = None

    def get_embed(self):
        start = self.index * self.per_page
        end = start + self.per_page
        current_bots = self.bots[start:end]

        # Format bot list
        bot_lines = "\n".join([f"{i+1}. **{bot.name}**" for i, bot in enumerate(current_bots, start=start)])

        embed = discord.Embed(
            title=f"Bots in {self.ctx.guild.name}",
            description=bot_lines if bot_lines else "*No bots found.*",
            color=0x2f3136
        )

        embed.set_author(name=self.ctx.author.name, icon_url=self.ctx.author.avatar.url)

        if self.ctx.guild.icon:
            embed.set_thumbnail(url=self.ctx.guild.icon.url)

        total_pages = max(1, (len(self.bots) - 1) // self.per_page + 1)
        embed.set_footer(text=f"{self.index + 1}/{total_pages}")

        return embed

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index - 1) % max(1, (len(self.bots) - 1) // self.per_page + 1)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        self.index = (self.index + 1) % max(1, (len(self.bots) - 1) // self.per_page + 1)
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=create_embed("", f"<a:sword_spin:1211611749426667560>  {interaction.user.mention}: You are not the author of this embed.", self.ctx, include_author=False),
                ephemeral=True
            )
        await interaction.message.delete()

    async def on_timeout(self):
        self.timed_out = True

        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=None)
        except:
            pass

        self.stop()

@bot.command()
async def bots(ctx):
    """See all server bots"""
    bots = [member for member in ctx.guild.members if member.bot]

    # If no bots found
    if not bots:
        return await ctx.send(
            embed=discord.Embed(
                description="No bots found in this server.",
                color=0x2f3136
            )
        )

    view = BotsView(bots, ctx)
    view.message = await ctx.send(embed=view.get_embed(), view=view)

@bot.command(aliases=["folk"])
async def zephfolk(ctx):
    gif = [
        "https://giphy.com/gifs/son-folk-druski-di3fwtPhjXOpL9KcUJ",
        "https://giphy.com/gifs/pose-folk-rgull1t-iUZVf1Q6PSnnZEJrkZ",
        "https://giphy.com/gifs/ai-baby-mongolian-folk-Z1iDnkZoCJ1krUt1nY",
        "https://giphy.com/gifs/folk-druski-mbappe-19IfsgThQuUQnZIjf9",
        "https://giphy.com/gifs/folk-polish-coach-nvY2DqdQwDx6zUnBKn",
        "https://cdn.discordapp.com/attachments/1069850380114067490/1472166276443930624/image.png",
        "https://cdn.discordapp.com/attachments/1069850380114067490/1472166977777696883/fd9be3c8e401e94d9beb31f69ed80e63.jpg",
        "https://cdn.discordapp.com/attachments/1388217572503060490/1472470330806108375/image.png"

    ]

    folk = random.choice(gif)
    await ctx.send(folk)
    

# -----------------------------
# Global error handler
# -----------------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        missing = error.missing_permissions

        # Format → `Ban Members`
        pretty = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in missing)

        await ctx.send(embed=create_embed(
            "",
            f"<a:sword_spin:1211611749426667560>   {ctx.author.mention}: "
            f"You don't have the **required permission(s)** to run this command:\n{pretty}",
            ctx,
            include_author=False
        ))
        return                    

# -----------------------------
# Run the bot
# -----------------------------
from dotenv import load_dotenv

load_dotenv()
bot.run(os.getenv("BOT_TOKEN"))