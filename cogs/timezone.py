import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo   # Built-in Python timezone database
from zoneinfo import available_timezones

BASE_DIR = os.getcwd()
TIMEZONE_FILE = os.path.join(BASE_DIR, "timezones.json")

def load_timezones():
    if not os.path.exists(TIMEZONE_FILE):
        return {}
    with open(TIMEZONE_FILE, "r") as f:
        return json.load(f)

def save_timezones(data):
    with open(TIMEZONE_FILE, "w") as f:
        json.dump(data, f, indent=4)

class TimezoneListView(discord.ui.View):
    def __init__(self, ctx, cities: list[str]):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cities = cities
        self.per_page = 20
        self.index = 0
        self.message: discord.Message | None = None

    def format_city(self, tz: str):
        parts = tz.split("/")

        city = parts[-1].replace("_", " ")
        city = " ".join(word.capitalize() for word in city.split())

        if len(parts) > 2:
            region = parts[-2].replace("_", " ")
            region = " ".join(word.capitalize() for word in region.split())
            return f"{city} ({region})"
        
        return city

    def get_embed(self):
        start = self.index * self.per_page
        end = start + self.per_page
        page_items = self.cities[start:end]

        lines = "\n".join(f"`{self.format_city(c)}`" for c in page_items) if page_items else "*No cities.*"

        embed = discord.Embed(
            title="Available Timezones (Cities)",
            description=lines,
            color=0x2f3136
        )

        embed.set_author(
            name=self.ctx.author.name,
            icon_url=self.ctx.author.avatar.url if self.ctx.author.avatar else None
        )

        total_pages = max(1, (len(self.cities) - 1) // self.per_page + 1)
        embed.set_footer(text=f"{self.index + 1}/{total_pages}")

        return embed

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.get_embed(),
            view=self
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "This pagination is not for you.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.cities) - 1) // self.per_page + 1)
        self.index = (self.index - 1) % total_pages
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_pages = max(1, (len(self.cities) - 1) // self.per_page + 1)
        self.index = (self.index + 1) % total_pages
        await self.update(interaction)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
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


class Timezone(commands.Cog):

    def build_timezone_lookup(self):
        lookup = {}
        for tz in available_timezones():
            parts = tz.lower().replace("_", " ").split("/")
            tokens = set()
            for p in parts:
                tokens.update(p.split())

            key = " ".join(sorted(tokens))
            lookup.setdefault(key, []).append(tz)

        return lookup

    def __init__(self, bot):
        self.bot = bot
        self.timezones = load_timezones()
        self.tz_lookup = self.build_timezone_lookup()
        self.city_list = self.build_city_lookup()
        self.EMBED_COLOR = 0x2f3136
    
    def build_city_lookup(self):
        lookup = {}
        for tz in available_timezones():
            if "/" not in tz:
                continue

            _, city = tz.split("/", 1)

            key = city.lower().replace("_", " ").replace("-", " ")
            lookup.setdefault(key, []).append(tz)
        
        return lookup

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

    # ----------------- COMMAND: timezone set -----------------

    @commands.group(aliases=["tz"], invoke_without_command=True)
    async def timezone(self, ctx, member: discord.Member | None = None):
        """Get time for yourself or another member."""
        author = ctx.author

        # If no argument → show author's time
        target = member or author
        tid = str(target.id)

        if tid not in self.timezones:
            # author calls for themself
            if target == author:
                embed = self._embed(
                    "",
                    f"{author.mention}: You do not have a timezone set. To do so, use `timezone set <city>`",
                    ctx,
                    include_author=False
                )
                return await ctx.send(embed=embed)

            # author calls for someone else
            embed = self._embed(
                "",
                f"{author.mention}: **{target.name}** does not have a timezone set.",
                ctx,
                include_author=False
            )
            return await ctx.send(embed=embed)

        # timezone exists
        tzname = self.timezones[tid]

        try:
            now = datetime.now(ZoneInfo(tzname))
        except:
            now = None

        formatted = now.strftime("%B %d, %I:%M %p")

        if target == author:
            embed = self._embed(
                "",
                f"{author.mention}: It is currently `{formatted}`",
                ctx,
                include_author=False
            )
        else:
            embed = self._embed(
                "",
                f"{author.mention}: **{target.name}**'s current time is `{formatted}`.",
                ctx,
                include_author=False
            )

        await ctx.send(embed=embed)

    # ----------------- timezone set -----------------

    @timezone.command(name="set")
    async def timezone_set(self, ctx, *, tz: str | None = None):
        author = ctx.author
        prefix = ctx.prefix

        # No timezone provided → help
        if tz is None:
            embed = self._embed(
                "command: timezone set",
                "Set a timezone based on location",
                ctx
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}timezone set <city>\n"
                      f"\u001b[35mexample:\u001b[0m {prefix}timezone set jakarta```",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        tokens = tz.lower().replace("_", " ").replace("-", " ").strip()

        matches = self.city_list.get(tokens)

        if not matches:
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"{author.mention}: Unavailable timezone/location **{tz}**. Use `{prefix}timezone list` to see available timezones.",
                    ctx,
                    include_author=False
                )
            )
        
        if len(matches) > 1:
            formatted = ", ".join(matches[:5])
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"{author.mention}: Multiple timezones found for **{tz}**:\n`{formatted}`.\nPlease be more specific.",
                    ctx,
                    include_author=False
                )
            )
        
        final_tz = matches[0]
        self.timezones[str(author.id)] = final_tz
        save_timezones(self.timezones)

        await ctx.send(
            embed=self._embed(
                "",
                f"{author.mention}: Your timezone is set to `{final_tz.replace('_', ' ').replace('-', ' ')}`",
                ctx,
                include_author=False
            )
        )

    @timezone.command(name="list")
    async def timezone_list(self, ctx):

        if not self.city_list:
            return await ctx.send(
                embed=self._embed(
                    "",
                    "No timezones available.",
                    ctx,
                    include_author=False
                )
            )
        
        cities = sorted(
        (tz for tzs in self.city_list.values() for tz in tzs),
        key=lambda tz: TimezoneListView.format_city(self, tz)
        )
        view = TimezoneListView(ctx, cities)
        message = await ctx.send(embed=view.get_embed(), view=view)
        view.message = message

async def setup(bot):
    await bot.add_cog(Timezone(bot))
    print("Timezone cog loaded.")
