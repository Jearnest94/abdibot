"""
Quick debug script to see what servers and channels the bot can access
"""
import os
import asyncio
from dotenv import load_dotenv
import discord

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    intents = discord.Intents.default()
    intents.message_content = False
    intents.members = False
    intents.presences = False
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"Bot logged in as: {client.user.name}")
        print(f"Bot ID: {client.user.id}")
        print()
        
        print(f"Bot is in {len(client.guilds)} server(s):")
        for guild in client.guilds:
            print(f"\nServer: {guild.name} (ID: {guild.id})")
            print(f"  Text channels:")
            for channel in guild.text_channels:
                print(f"    - #{channel.name} (ID: {channel.id})")
        
        await client.close()
    
    await client.start(TOKEN)

asyncio.run(main())
