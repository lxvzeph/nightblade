import discord
import asyncio
from discord.ext import commands

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix=";", intents=intents)

ALLOWED = {
    1118719182062759967,
    1173690462654189600,
    231191072263372801,
    934124462146715738,
    852952632322031657,
    778242218888658954
}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        if message.author.id not in ALLOWED:
            msg = await message.channel.send("hell no 😂")
            await asyncio.sleep(3)
            await msg.delete()
            await message.delete()
            return
        
        content = message.content.lower().strip()

        if content == f"<@{bot.user.id}> get em" or content == f"<@!{bot.user.id}> get em":
            if not message.reference:
                msg = await message.channel.send("ping me while replying to a message")
                await asyncio.sleep(3)
                await msg.delete()
                await message.delete()
                return
            
            if isinstance(message.reference.resolved, discord.Message):
                replied_message = message.reference.resolved
            else:
                replied_message = await message.channel.fetch_message(message.reference.message_id)

            try:
                await replied_message.clear_reactions()
                msg = await message.channel.send("👍")
                await asyncio.sleep(1)
                await msg.delete()
                await message.delete()
                return
            except discord.Forbidden:
                msg = await message.channel.send("👎")
                await asyncio.sleep(1)
                await msg.delete()
                await message.delete()
                return
        
        else:
            msg = await message.channel.send("say the thing bro")
            await asyncio.sleep(3)
            await msg.delete()
            await message.delete()
    
    await bot.process_commands(message)

from dotenv import load_dotenv
import os

load_dotenv()

bot.run(os.getenv("SNATCHER_TOKEN"))
