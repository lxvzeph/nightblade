import discord
from discord.ext import commands
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones
from data.timezones import get_timezone, set_timezone, get_all_timezones_in_guild # Built-in Python timezone database

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

    def __init__(self, bot):
        self.bot = bot
        self.tz_lookup = self.build_timezone_lookup()
        self.city_list = self.build_city_lookup()
        self.EMBED_COLOR = 0x2f3136

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
        except Exception:
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
        """See your own time or another member's
        example: timezone zeph"""
        author = ctx.author

        # If no argument → show author's time
        target = member or author
        tzname = get_timezone(target.id)

        if tzname is None:
            if target == author:
                return await ctx.send(
                    embed=self._embed(
                        "",
                        f"{author.mention}: You do not have a timezone set. Use `{ctx.prefix}timezone set <timezone>` to set it.",
                        ctx, include_author=False
                    )
                )

            # author calls for someone else
            return await ctx.send(
                embed=self._embed(
                    "",
                    f"{author.mention}: **{target.name}** does not have a timezone set.",
                    ctx, include_author=False
                )
            )

        try:
            now = datetime.now(ZoneInfo(tzname))
        except Exception:
            return await ctx.send(embed=self._embed(
                "",
                f"{author.mention}: Stored timezone `{tzname}` is invalid. Please set a new one.",
                ctx, include_author=False
            ))

        formatted = now.strftime("%B %d, %I:%M %p")

        if target == author:
            msg = f"{author.mention}: It is currently `{formatted}`."
        else:
            msg = f"{author.mention}: **{target.name}**'s current time is `{formatted}`."

        await ctx.send(embed=self._embed(
            "",
            msg,
            ctx, include_author=False
        ))

    # ----------------- timezone set -----------------

    @timezone.command(name="set")
    async def timezone_set(self, ctx, *, tz: str | None = None):
        """Sets your timezone
        example: timezone set jakarta"""
        author = ctx.author
        prefix = ctx.prefix

        # No timezone provided → help
        if tz is None:
            embed = self._embed(
                "command: timezone set",
                "Sets your timezone",
                ctx
            )
            embed.add_field(
                name="Utilization",
                value=f"```ansi\n\u001b[35msyntax:\u001b[0m {prefix}timezone set <timezone>\n"
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
        set_timezone(author.id, final_tz)

        await ctx.send(
            embed=self._embed(
                "",
                f"{author.mention}: Your timezone is set to `{final_tz.replace('_', ' ')}`",
                ctx,
                include_author=False
            )
        )

    @timezone.command(name="list")
    async def timezone_list(self, ctx):
        """See list of all available timezones"""

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
        view.message = await ctx.send(embed=view.get_embed(), view=view)

    @timezone.command(name="all")
    async def timezone_all(self, ctx):
        """See all members' timezones"""
        member_ids = [m.id for m in ctx.guild.members if not m.bot]
        tz_map = get_all_timezones_in_guild(member_ids)

        entries = []
        for member in ctx.guild.members:
            if member.bot or member.id not in tz_map:
                continue
            tzname = tz_map[member.id]
            try:
                now = datetime.now(ZoneInfo(tzname))
                formatted = now.strftime("%I:%M %p")
            except Exception:
                formatted = "invalid tz"
            entries.append((member, tzname, formatted))

        if not entries:
            return await ctx.send(embed=self._embed(
                "", f"{ctx.author.mention}: No members have set a timezone in this server.",
                ctx, include_author=False
            ))

        entries.sort(key=lambda e: e[2])  # sort by time string

        PER_PAGE = 10

        class TimezoneAllView(discord.ui.View):
            def __init__(self, ctx, entries, embed_fn):
                super().__init__(timeout=60)
                self.ctx = ctx
                self.entries = entries
                self.embed_fn = embed_fn
                self.page = 1
                self.message = None

            def make_embed(self):
                start = (self.page - 1) * PER_PAGE
                subset = self.entries[start:start + PER_PAGE]
                lines = []
                for i, (member, tzname, formatted) in enumerate(subset, start=start + 1):
                    lines.append(f"`{i}.` **{member.display_name}** — {formatted} (`{tzname.replace('_', ' ')}`)")
                embed = self.embed_fn(
                    "All Members' Timezones",
                    "\n".join(lines),
                    self.ctx
                )
                total = len(self.entries)
                pages = (total + PER_PAGE - 1) // PER_PAGE or 1
                embed.set_author(name=self.ctx.guild.name, icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)
                embed.set_footer(text=f"{self.page}/{pages}  ∙  {total} members")
                return embed

            async def update_message(self, interaction):
                await interaction.response.edit_message(embed=self.make_embed(), view=self)

            @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
            async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.ctx.author.id:
                    return await interaction.response.send_message("Not your embed.", ephemeral=True)
                if self.page > 1:
                    self.page -= 1
                    await self.update_message(interaction)
                else:
                    await interaction.response.defer()

            @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
            async def nxt(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.ctx.author.id:
                    return await interaction.response.send_message("Not your embed.", ephemeral=True)
                total = len(self.entries)
                pages = (total + PER_PAGE - 1) // PER_PAGE or 1
                if self.page < pages:
                    self.page += 1
                    await self.update_message(interaction)
                else:
                    await interaction.response.defer()

            @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
            async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.ctx.author.id:
                    return await interaction.response.send_message("Not your embed.", ephemeral=True)
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

        view = TimezoneAllView(ctx, entries, self._embed)
        view.message = await ctx.send(embed=view.make_embed(), view=view)

async def setup(bot):
    await bot.add_cog(Timezone(bot))
    print("Timezone cog loaded.")
