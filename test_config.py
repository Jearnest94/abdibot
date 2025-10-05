"""
Configuration Test Script
==========================
Test your Discord bot and RCON configuration before running the main bot.

This script validates:
1. .env file exists and is properly formatted
2. All required environment variables are set
3. RCON connection works
4. Discord bot token is valid
5. Discord channel is accessible

Run this before starting the bot to catch configuration issues early!
"""

import os
import sys
from dotenv import load_dotenv

print("=" * 70)
print("Minecraft Discord Bot - Configuration Test")
print("=" * 70)
print()

# Load environment variables
print("[1/4] Loading .env file...")
if not os.path.exists(".env"):
    print("[ERROR] .env file not found!")
    print("   Please copy .env.example to .env and fill in your values.")
    sys.exit(1)

load_dotenv()
print("[OK] .env file loaded")
print()

# Check environment variables
print("[2/4] Validating environment variables...")

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = os.getenv("RCON_PORT", "25575")
RCON_PASSWORD = os.getenv("RCON_PASSWORD")
POLL_SECONDS = os.getenv("POLL_SECONDS", "5")

errors = []

if not TOKEN:
    errors.append("DISCORD_TOKEN is not set")
else:
    print(f"[OK] DISCORD_TOKEN is set ({len(TOKEN)} characters)")

if not CHANNEL_ID:
    errors.append("DISCORD_CHANNEL_ID is not set")
else:
    try:
        int(CHANNEL_ID)
        print(f"[OK] DISCORD_CHANNEL_ID is set ({CHANNEL_ID})")
    except ValueError:
        errors.append("DISCORD_CHANNEL_ID must be a valid integer")
        print(f"[ERROR] DISCORD_CHANNEL_ID is invalid: {CHANNEL_ID}")

if not RCON_HOST:
    errors.append("RCON_HOST is not set")
else:
    print(f"[OK] RCON_HOST is set ({RCON_HOST})")

if not RCON_PASSWORD:
    errors.append("RCON_PASSWORD is not set")
else:
    print(f"[OK] RCON_PASSWORD is set ({len(RCON_PASSWORD)} characters)")

try:
    port = int(RCON_PORT)
    if port < 1 or port > 65535:
        errors.append("RCON_PORT must be between 1 and 65535")
        print(f"[ERROR] RCON_PORT is invalid: {port}")
    else:
        print(f"[OK] RCON_PORT is valid ({port})")
except ValueError:
    errors.append("RCON_PORT must be a valid integer")
    print(f"[ERROR] RCON_PORT is invalid: {RCON_PORT}")

try:
    poll = int(POLL_SECONDS)
    if poll < 1:
        errors.append("POLL_SECONDS must be at least 1")
        print(f"[ERROR] POLL_SECONDS is too low: {poll}")
    else:
        print(f"[OK] POLL_SECONDS is valid ({poll})")
        if poll < 3:
            print("[WARNING] POLL_SECONDS < 3 may cause high server load")
except ValueError:
    errors.append("POLL_SECONDS must be a valid integer")
    print(f"[ERROR] POLL_SECONDS is invalid: {POLL_SECONDS}")

if errors:
    print()
    print("[ERROR] Configuration validation failed with errors:")
    for error in errors:
        print(f"   - {error}")
    print()
    print("Please fix these errors in your .env file and try again.")
    sys.exit(1)

print()
print("[OK] All environment variables are valid!")
print()

# Test RCON connection
print("[3/4] Testing RCON connection...")
print(f"   Connecting to {RCON_HOST}:{RCON_PORT}...")

try:
    from mcrcon import MCRcon
    
    with MCRcon(RCON_HOST, RCON_PASSWORD, port=int(RCON_PORT)) as mcr:
        resp = mcr.command("list")
    
    print("[OK] RCON connection successful!")
    print(f"   Server response: {resp}")
    
    # Parse player list
    if "online:" in resp:
        parts = resp.split("online:", 1)
        if len(parts) > 1:
            names_part = parts[1].strip()
            if names_part:
                players = [n.strip() for n in names_part.split(",") if n.strip()]
                print(f"   Players online: {', '.join(players)}")
            else:
                print("   No players currently online")
    
except ImportError:
    print("[ERROR] mcrcon package not installed!")
    print("   Run: python -m pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] RCON connection failed: {e}")
    print()
    print("Troubleshooting tips:")
    print("   • Verify your Minecraft server is running")
    print("   • Check that enable-rcon=true in server.properties")
    print("   • Confirm RCON_PASSWORD matches rcon.password in server.properties")
    print("   • Ensure RCON port is open in your firewall/hosting panel")
    print("   • Try restarting your Minecraft server")
    sys.exit(1)

print()

# Test Discord connection
print("[4/4] Testing Discord bot token...")
print("   Connecting to Discord API...")

try:
    import discord
    import asyncio
    
    channel_found = False
    
    async def test_discord():
        global channel_found
        intents = discord.Intents.default()
        intents.message_content = False
        intents.members = False
        intents.presences = False
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            global channel_found
            print(f"[OK] Discord connection successful!")
            print(f"   Bot username: {client.user.name}")
            print(f"   Bot ID: {client.user.id}")
            
            # Try to get the channel
            channel = client.get_channel(int(CHANNEL_ID))
            if channel:
                print(f"[OK] Discord channel found: #{channel.name}")
                print(f"   Channel ID: {channel.id}")
                
                # Check permissions
                permissions = channel.permissions_for(channel.guild.me)
                if permissions.send_messages:
                    print("[OK] Bot has 'Send Messages' permission")
                else:
                    print("[ERROR] Bot lacks 'Send Messages' permission!")
                    print("   Grant the bot permission to send messages in this channel.")
                
                if permissions.view_channel:
                    print("[OK] Bot has 'View Channel' permission")
                else:
                    print("[ERROR] Bot lacks 'View Channel' permission!")
                    print("   Grant the bot permission to view this channel.")
                
                channel_found = True
            else:
                print(f"[ERROR] Could not find channel with ID: {CHANNEL_ID}")
                print()
                print("Troubleshooting:")
                print("   1. Check if bot is in your server (look for 'abdibot' in member list)")
                print("   2. Verify channel ID is correct (right-click channel -> Copy Channel ID)")
                print("   3. Make sure bot has 'View Channels' permission")
                print("   4. Try inviting bot again using OAuth2 URL Generator")
                channel_found = False
            
            await client.close()
        
        try:
            await client.start(TOKEN)
        except discord.LoginFailure:
            print("[ERROR] Discord authentication failed!")
            print("   Your DISCORD_TOKEN is invalid.")
            print("   Get a new token from: https://discord.com/developers/applications")
        except Exception as e:
            print(f"[ERROR] Discord connection failed: {e}")
    
    asyncio.run(test_discord())
    
    if not channel_found:
        print()
        sys.exit(1)
    
except ImportError:
    print("[ERROR] discord.py package not installed!")
    print("   Run: python -m pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    sys.exit(1)

print()
print("=" * 70)
print("[OK] All tests passed! Your configuration is ready.")
print("=" * 70)
print()
print("You can now run the bot with:")
print("   python bot.py")
print()
