import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os

BASE_DIR = os.getcwd()
SNIPE_FILE = os.path.join(BASE_DIR, "snipes.json")

class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.snipes_file = SNIPE_FILE
        self.snipes = {}  # message snipes
        self.reaction_snipes = {}  # NEW: reaction snipes
        self.edit_snipes = {}
        self.ignore_deletes = set()
        self.load_snipes()
        self.cleanup_snipes.start()

    # -------------------------
    # SAVE + LOAD SYSTEM
    # -------------------------
    def save_snipes(self):
        serializable = {
            "messages": {},
            "reactions": {}
        }

        # Save message snipes
        for cid, messages in self.snipes.items():
            serializable["messages"][cid] = []
            for m in messages:
                serializable["messages"][cid].append({
                    "author_id": m["author_id"],
                    "author_name": m["author_name"],
                    "author_avatar_url": m["author_avatar_url"],
                    "content": m["content"],
                    "attachments": [a["url"] for a in m["attachments"]],
                    "time": m["time"].isoformat()
                })

        # Save reaction snipes
        for cid, reactions in self.reaction_snipes.items():
            serializable["reactions"][cid] = []
            for r in reactions:
                serializable["reactions"][cid].append({
                    "user_id": r["user_id"],
                    "user_name": r["user_name"],
                    "user_avatar_url": r["user_avatar_url"],
                    "emoji": r["emoji"],
                    "message_id": r["message_id"],
                    "message_url": r["message_url"],
                    "time": r["time"].isoformat()
                })

        for cid, edits in self.edit_snipes.items():
            serializable.setdefault("edits", {})[cid] = []
            for e in edits:
                serializable["edits"][cid].append({
                    "author_id": e["author_id"],
                    "author_name": e["author_name"],
                    "author_avatar_url": e["author_avatar_url"],
                    "before": e["before"],
                    "after": e["after"],
                    "message_url": e["message_url"],
                    "time": e["time"].isoformat()
                })

        with open(self.snipes_file, "w") as f:
            json.dump(serializable, f, indent=4)

    def load_snipes(self):
        if not os.path.exists(self.snipes_file):
            return

        with open(self.snipes_file, "r") as f:
            try:
                data = json.load(f)

                # Load message snipes
                for cid, messages in data.get("messages", {}).items():
                    cid = int(cid)
                    self.snipes[cid] = []
                    for m in messages:
                        self.snipes[cid].append({
                            "author_id": m["author_id"],
                            "author_name": m["author_name"],
                            "author_avatar_url": m.get("author_avatar_url"),
                            "content": m.get("content"),
                            "attachments": [{"url": url} for url in m.get("attachments", [])],
                            "time": datetime.fromisoformat(m["time"])
                        })

                # Load reaction snipes
                for cid, reactions in data.get("reactions", {}).items():
                    cid = int(cid)
                    self.reaction_snipes[cid] = []
                    for r in reactions:
                        self.reaction_snipes[cid].append({
                            "user_id": r["user_id"],
                            "user_name": r["user_name"],
                            "user_avatar_url": r.get("user_avatar_url"),
                            "emoji": r["emoji"],
                            "message_id": r["message_id"],
                            "message_url": r["message_url"],
                            "time": datetime.fromisoformat(r["time"])
                        })

                for cid, edits in data.get("edits", {}).items():
                    cid = int(cid)
                    self.edit_snipes[cid] = []
                    for e in edits:
                        self.edit_snipes[cid].append({
                            "author_id": e["author_id"],
                            "author_name": e["author_name"],
                            "author_avatar_url": e.get("author_avatar_url"),
                            "before": e["before"],
                            "after": e["after"],
                            "message_url": e["message_url"],
                            "time": datetime.fromisoformat(e["time"])
                        })

            except:
                self.snipes = {}
                self.reaction_snipes = {}

    # -------------------------
    # PERIODIC CLEANUP
    # -------------------------
    @tasks.loop(minutes=10)
    async def cleanup_snipes(self):
        cutoff = datetime.utcnow() - timedelta(hours=2)
        changed = False

        # Clean messages
        for cid in list(self.snipes.keys()):
            old_len = len(self.snipes[cid])
            self.snipes[cid] = [m for m in self.snipes[cid] if m["time"] > cutoff]
            if len(self.snipes[cid]) != old_len:
                changed = True

        # Clean reactions
        for cid in list(self.reaction_snipes.keys()):
            old_len = len(self.reaction_snipes[cid])
            self.reaction_snipes[cid] = [r for r in self.reaction_snipes[cid] if r["time"] > cutoff]
            if len(self.reaction_snipes[cid]) != old_len:
                changed = True

        for cid in list(self.edit_snipes.keys()):
            old_len = len(self.edit_snipes[cid])
            self.edit_snipes[cid] = [e for e in self.edit_snipes[cid] if e["time"] > cutoff]
            if len(self.edit_snipes[cid]) != old_len:
                changed = True 

        if changed:
            self.save_snipes()

    # -------------------------
    # LISTENERS
    # -------------------------
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.id in self.ignore_deletes:
            self.ignore_deletes.discard(message.id)
            return

        if message.author.bot:
            return

        cid = message.channel.id
        if cid not in self.snipes:
            self.snipes[cid] = []

        self.snipes[cid].append({
            "author_id": message.author.id,
            "author_name": str(message.author),
            "author_avatar_url": message.author.avatar.url if message.author.avatar else None,
            "content": message.content,
            "attachments": [{"url": a.url} for a in message.attachments],
            "time": datetime.utcnow()
        })

        self.save_snipes()

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return

        cid = reaction.message.channel.id
        if cid not in self.reaction_snipes:
            self.reaction_snipes[cid] = []

        message = reaction.message

        self.reaction_snipes[cid].append({
            "user_id": user.id,
            "user_name": str(user),
            "user_avatar_url": user.avatar.url if user.avatar else None,
            "emoji": str(reaction.emoji),
            "message_id": message.id,
            "message_url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}",
            "time": datetime.utcnow()
        })

        self.save_snipes()

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot:
            return

        if before.content == after.content:
            return  # ignore embed-only edits

        cid = before.channel.id
        if cid not in self.edit_snipes:
            self.edit_snipes[cid] = []

        self.edit_snipes[cid].append({
            "author_id": before.author.id,
            "author_name": str(before.author),
            "author_avatar_url": before.author.avatar.url if before.author.avatar else None,
            "before": before.content,
            "after": after.content,
            "message_url": f"https://discord.com/channels/{before.guild.id}/{before.channel.id}/{before.id}",
            "time": datetime.utcnow()
        })

        self.save_snipes()


    # -------------------------
    # MESSAGE SNIPE COMMANDS
    # -------------------------
    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["s"])
    async def snipe(self, ctx, number: int = 1):
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
        time_str = m["time"].strftime("%I:%M%p")

        embed = discord.Embed(
            description=m["content"] or "*(no text, maybe only attachments)*",
            color=discord.Color.from_str("#2f3136")
        )
        embed.set_author(name=m["author_name"], icon_url=m["author_avatar_url"])
        embed.set_footer(text=f"Sniped by {ctx.author}")
        embed.timestamp = discord.utils.utcnow()

        if m["attachments"]:
            embed.set_image(url=m["attachments"][-1]["url"])

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["cs"])
    async def clearsnipe(self, ctx, number: int = 1):
        cid = ctx.channel.id
        if cid not in self.snipes or not self.snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No deleted messages in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        msgs = sorted(self.snipes[cid], key=lambda x: x["time"], reverse=True)
        if number < 1 or number > len(msgs):
            return await ctx.send(embed=discord.Embed(
                description="No deleted messages in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        msgs.pop(number - 1)
        self.snipes[cid] = sorted(msgs, key=lambda x: x["time"])
        self.save_snipes()

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    # -------------------------
    # REACTION SNIPE COMMANDS
    # -------------------------
    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["rs"])
    async def reactionsnipe(self, ctx, number: int = 1):
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
        elapsed_str = self.format_elapsed(elapsed)

        embed = discord.Embed(
            title="Go to message",
            url=r["message_url"],
            description=f"Reacted with  {r['emoji']}  {elapsed_str} ago",
            color=discord.Color.from_str("#2f3136")
        )
        embed.set_author(name=r["user_name"], icon_url=r["user_avatar_url"])

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.command(aliases=["crs"])
    async def clearreactionsnipe(self, ctx, number: int = 1):
        cid = ctx.channel.id
        if cid not in self.reaction_snipes or not self.reaction_snipes[cid]:
            return await ctx.send(embed=discord.Embed(
                description="No removed reactions in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        reactions = sorted(self.reaction_snipes[cid], key=lambda x: x["time"], reverse=True)
        if number < 1 or number > len(reactions):
            return await ctx.send(embed=discord.Embed(
                description="No removed reactions in the last 2 hours.",
                color=discord.Color.from_str("#2f3136")
            ))

        reactions.pop(number - 1)
        self.reaction_snipes[cid] = sorted(reactions, key=lambda x: x["time"])
        self.save_snipes()

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    @commands.command(aliases=["es"])
    @commands.has_permissions(manage_messages=True)
    async def editsnipe(self, ctx, number: int = 1):
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
        embed.set_footer(text=f"Sniped by {ctx.author}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.send(embed=embed)

    @commands.command(aliases=["ces"])
    @commands.has_permissions(manage_messages=True)
    async def cleareditsnipe(self, ctx, number: int = 1):
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
        
        edits.pop(number - 1)
        self.edit_snipes[cid] = sorted(edits, key=lambda x: x["time"])
        self.save_snipes()

        msg = await ctx.send("👍")
        await msg.delete(delay=2)

        self.ignore_deletes.add(ctx.message.id)
        await ctx.message.delete(delay=2)

    # Helper
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