import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from data.snipes import (
    load_all_snipes,
    save_message_snipe,
    save_reaction_snipe,
    save_edit_snipe,
    delete_message_snipe,
    delete_reaction_snipe,
    delete_edit_snipe,
    delete_expired_snipes
)

class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ignore_deletes = set()
        self.snipes, self.reaction_snipes, self.edit_snipes = load_all_snipes()
        self.cleanup_snipes.start()

    @tasks.loop(minutes=10)
    async def cleanup_snipes(self):
        cutoff = datetime.utcnow() - timedelta(hours=2)

        for cid in list(self.snipes.keys()):
            self.snipes[cid] = [m for m in self.snipes[cid] if m["time"] > cutoff]

        for cid in list(self.reaction_snipes.keys()):
            self.reaction_snipes[cid] = [r for r in self.reaction_snipes[cid] if r["time"] > cutoff]

        for cid in list(self.edit_snipes.keys()):
            self.edit_snipes[cid] = [e for e in self.edit_snipes[cid] if e["time"] > cutoff]

        delete_expired_snipes(cutoff)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.id in self.ignore_deletes:
            self.ignore_deletes.discard(message.id)
            return

        if message.author.bot:
            return

        cid = message.channel.id
        snipe = {
            "author_id": message.author.id,
            "author_name": str(message.author),
            "author_avatar_url": message.author.avatar.url if message.author.avatar else None,
            "content": message.content,
            "attachments": [{"url": a.url} for a in message.attachments],
            "time": datetime.utcnow()
        }

        self.snipes.setdefault(cid, []).append(snipe)
        save_message_snipe(cid, snipe)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        cid = reaction.message.channel.id

        message = reaction.message

        snipe = {
            "user_id": user.id,
            "user_name": str(user),
            "user_avatar_url": user.avatar.url if user.avatar else None,
            "emoji": str(reaction.emoji),
            "message_id": message.id,
            "message_url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}",
            "time": datetime.utcnow()
        }

        self.reaction_snipes.setdefault(cid, []).append(snipe)
        save_reaction_snipe(cid, snipe)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return

        if before.content == after.content:
            return

        cid = before.channel.id

        snipe = {
            "author_id": before.author.id,
            "author_name": str(before.author),
            "author_avatar_url": before.author.avatar.url if before.author.avatar else None,
            "before": before.content,
            "after": after.content,
            "message_url": f"https://discord.com/channels/{before.guild.id}/{before.channel.id}/{before.id}",
            "time": datetime.utcnow()
        }

        self.edit_snipes.setdefault(cid, []).append(snipe)
        save_edit_snipe(cid, snipe)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["s"])
    async def snipe(self, ctx, number: int = 1):
        """Snipes a deleted message
        example: snipe 3"""
        cid = ctx.channel.id
        if cid not in self.snipes or not self.snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No deleted message(s) in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        messages = sorted(self.snipes[cid], key=lambda x: x["time"], reverse=True)
        if number < 1 or number > len(messages):
            return await ctx.send(embed=discord.Embed(
                description="No deleted messages in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        m = messages[number - 1]

        embed = discord.Embed(
            description=m["content"] or "*(no text, maybe only attachments)*",
            color=discord.Color.from_str("#2f3136")
        )
        embed.set_author(name=m["author_name"], icon_url=m["author_avatar_url"])
        embed.set_footer(text=f"Sniped by {ctx.author.display_name}")
        embed.timestamp = discord.utils.utcnow()

        if m["attachments"]:
            embed.set_image(url=m["attachments"][-1]["url"])

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["cs"])
    async def clearsnipe(self, ctx):
        """Clear snipes for deleted messages
        example: clearsnipe 3"""
        cid = ctx.channel.id
        if cid not in self.snipes or not self.snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No deleted messages in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        count = len(self.snipes[cid])
        self.snipes[cid] = []
        delete_message_snipe(cid)

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["rs"])
    async def reactionsnipe(self, ctx, number: int = 1):
        """Snipes a deleted reaction
        example: reactionsnipe 2"""
        cid = ctx.channel.id
        if cid not in self.reaction_snipes or not self.reaction_snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No removed reaction(s) in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        reactions = sorted(self.reaction_snipes[cid], key=lambda x: x["time"], reverse=True)
        if number < 1 or number > len(reactions):
            return await ctx.send(embed=discord.Embed(
                description="No removed reaction(s) in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        r = reactions[number - 1]
        elapsed = datetime.utcnow() - r["time"]

        embed = discord.Embed(
            title="Go to message",
            url=r["message_url"],
            description=f"Reacted with  {r['emoji']}  {self.format_elapsed(elapsed)} ago",
            color=discord.Color.from_str("#2f3136")
        )
        embed.set_author(name=r["user_name"], icon_url=r["user_avatar_url"])
        embed.set_footer(text=f"Sniped by {ctx.author.display_name}")

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["crs"])
    async def clearreactionsnipe(self, ctx, number: int = 1):
        """Clear snipes for deleted reactions
        example: clearreactionsnipe 2"""
        cid = ctx.channel.id
        if cid not in self.reaction_snipes or not self.reaction_snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No removed reactions in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        count = len(self.reaction_snipes[cid])
        self.reaction_snipes[cid] = []
        delete_reaction_snipe(cid)

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    @commands.command(aliases=["es"])
    @commands.has_permissions(manage_messages=True)
    async def editsnipe(self, ctx, number: int = 1):
        """Snipes an edited message
        example: editsnipe 3"""
        cid = ctx.channel.id
        if cid not in self.edit_snipes or not self.edit_snipes[cid]:
            return await ctx.send(
                embed=discord.Embed(
                    description="No edited message(s) in the last 2 hours.",
                    color=discord.Color.from_str("#2f3136")
                ))
        
        edits = sorted(self.edit_snipes[cid], key=lambda x: x["time"], reverse=True)
        if number < 1 or number > len(edits):
            return await ctx.send(
                embed=discord.Embed(
                    description="No edited message(s) in the last 2 hours.",
                    color=discord.Color.from_str("#2f3136")
                ))
        
        e = edits[number - 1]

        embed = discord.Embed(
            title="Go to message",
            url=e["message_url"],
            color=discord.Color.from_str("#2f3136")
        )
        embed.set_author(name=e["author_name"], icon_url=e["author_avatar_url"])
        embed.add_field(name="Before", value=e["before"] or "*empty*", inline=False)
        embed.add_field(name="After", value=e["after"] or "*empty*", inline=False)
        embed.set_footer(text=f"Sniped by {ctx.author.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    @commands.command(aliases=["ces"])
    @commands.has_permissions(manage_messages=True)
    async def cleareditsnipe(self, ctx, number: int = 1):
        """Clear snipes for edited messages
        example: cleareditsnipe 3"""
        cid = ctx.channel.id
        if cid not in self.edit_snipes or not self.edit_snipes[cid]:
            return await ctx.send(
                embed=discord.Embed(
                    description="No edited message(s) in the last 2 hours.",
                    color=discord.Color.from_str("#2f3136")
                ))
        
        count = len(self.edit_snipes[cid])
        self.edit_snipes[cid] = []
        delete_edit_snipe(cid)

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    def format_elapsed(self, delta):
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        return f"{hours}h"

async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))
    print("Snipe cog loaded.")