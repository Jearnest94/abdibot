"""
Minecraft Discord Notification Bot
====================================
Monitors a Minecraft server via RCON and posts login notifications to Discord.

This bot polls the Minecraft server's player list at regular intervals and 
notifies a Discord channel when players join (and optionally when they leave).
"""

import os
import sys
import asyncio
import logging
import re
from datetime import datetime
from typing import Set, Optional
from dotenv import load_dotenv
from discord import Intents, Client
from mcrcon import MCRcon
import paramiko

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = os.getenv("RCON_PORT", "25575")
RCON_PASSWORD = os.getenv("RCON_PASSWORD")
POLL_SECONDS = os.getenv("POLL_SECONDS", "5")
NOTIFY_LOGOUT = os.getenv("NOTIFY_LOGOUT", "false").lower() == "true"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "")

# SFTP Configuration
SFTP_HOST = os.getenv("SFTP_HOST", "")
SFTP_PORT = os.getenv("SFTP_PORT", "22")
SFTP_USERNAME = os.getenv("SFTP_USERNAME", "")
# Workaround for # character in password - read from file or use alternative
SFTP_PASSWORD_RAW = os.getenv("SFTP_PASSWORD", "")
# If password seems truncated (no # character), try reading from separate file
if SFTP_PASSWORD_RAW and '#' not in SFTP_PASSWORD_RAW and os.path.exists('.sftp_password'):
    with open('.sftp_password', 'r') as f:
        SFTP_PASSWORD = f.read().strip()
else:
    SFTP_PASSWORD = SFTP_PASSWORD_RAW
SFTP_LOG_PATH = os.getenv("SFTP_LOG_PATH", "")

# State
last_online: Set[str] = set()
client: Optional[Client] = None
log_file_position: int = 0
sftp_client: Optional[paramiko.SFTPClient] = None
ssh_client: Optional[paramiko.SSHClient] = None
LOG_POSITION_FILE = ".log_position"


def load_log_position():
    """
    Load the last log file position from disk to prevent duplicate messages.
    
    Returns:
        int: Last read position, or 0 if file doesn't exist
    """
    try:
        if os.path.exists(LOG_POSITION_FILE):
            with open(LOG_POSITION_FILE, 'r') as f:
                return int(f.read().strip())
    except Exception as e:
        logger.warning(f"[WARNING] Could not load log position: {e}")
    return 0


def save_log_position(position: int):
    """
    Save the current log file position to disk.
    
    Args:
        position: Current byte position in log file
    """
    try:
        with open(LOG_POSITION_FILE, 'w') as f:
            f.write(str(position))
    except Exception as e:
        logger.error(f"[ERROR] Could not save log position: {e}")
    

def get_sftp_connection():
    """
    Get or create persistent SFTP connection.
    
    Returns:
        paramiko.SFTPClient: Active SFTP client or None if not configured
    """
    global sftp_client, ssh_client
    
    # Check if SFTP is configured
    if not SFTP_HOST or not SFTP_USERNAME or not SFTP_PASSWORD:
        return None
    
    # Reuse existing connection if alive
    if sftp_client is not None:
        try:
            sftp_client.stat('.')  # Test connection
            return sftp_client
        except Exception:
            # Connection died, close and reconnect
            try:
                if sftp_client:
                    sftp_client.close()
                if ssh_client:
                    ssh_client.close()
            except Exception:
                pass
            sftp_client = None
            ssh_client = None
    
    # Create new connection
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=SFTP_HOST,
            port=int(SFTP_PORT),
            username=SFTP_USERNAME,
            password=SFTP_PASSWORD,
            timeout=10
        )
        sftp_client = ssh_client.open_sftp()
        logger.info(f"[OK] Connected to SFTP server: {SFTP_HOST}:{SFTP_PORT}")
        return sftp_client
    except Exception as e:
        logger.error(f"[ERROR] SFTP connection failed: {e}")
        sftp_client = None
        ssh_client = None
        return None


def validate_configuration() -> bool:
    """
    Validate that all required configuration is present and valid.
    
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    errors = []
    
    if not TOKEN:
        errors.append("DISCORD_TOKEN is not set")
    
    if not CHANNEL_ID:
        errors.append("DISCORD_CHANNEL_ID is not set")
    else:
        try:
            int(CHANNEL_ID)
        except ValueError:
            errors.append("DISCORD_CHANNEL_ID must be a valid integer")
    
    if not RCON_HOST:
        errors.append("RCON_HOST is not set")
    
    if not RCON_PASSWORD:
        errors.append("RCON_PASSWORD is not set")
    
    try:
        port = int(RCON_PORT)
        if port < 1 or port > 65535:
            errors.append("RCON_PORT must be between 1 and 65535")
    except ValueError:
        errors.append("RCON_PORT must be a valid integer")
    
    try:
        poll = int(POLL_SECONDS)
        if poll < 1:
            errors.append("POLL_SECONDS must be at least 1")
        elif poll < 3:
            logger.warning("POLL_SECONDS is very low (< 3). Consider increasing to reduce server load.")
    except ValueError:
        errors.append("POLL_SECONDS must be a valid integer")
    
    if errors:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  [ERROR] {error}")
        logger.error("\nPlease check your .env file and ensure all required variables are set.")
        return False
    
    logger.info("[OK] Configuration validation passed")
    return True


def rcon_list_players() -> Set[str]:
    """
    Query the Minecraft server via RCON and return the set of online players.
    
    Returns:
        Set[str]: Set of player names currently online
    
    Raises:
        Exception: If RCON connection or command fails
    """
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=int(RCON_PORT)) as mcr:
            resp = mcr.command("list")
            
        # Parse response: "There are X of a max of Y players online: Player1, Player2"
        # or "There are X of a max of Y players online:" (when empty)
        if "online:" not in resp:
            logger.warning(f"Unexpected RCON response format: {resp}")
            return set()
        
        parts = resp.split("online:", 1)
        if len(parts) < 2:
            return set()
        
        names_part = parts[1].strip()
        if not names_part:
            return set()
        
        # Split by comma and clean up whitespace
        names = [n.strip() for n in names_part.split(",") if n.strip()]
        return set(names)
        
    except Exception as e:
        logger.error(f"RCON error: {e}")
        raise


def check_log_for_deaths():
    """
    Check Minecraft log file for death messages.
    Supports both local files and remote SFTP access.
    Saves position to prevent duplicate messages on restart.
    
    Returns:
        list: List of death message strings found since last check
    """
    global log_file_position
    
    death_messages = []
    
    # Load saved position on first run
    if log_file_position == 0:
        log_file_position = load_log_position()
        if log_file_position > 0:
            logger.info(f"[INFO] Resumed from saved log position: {log_file_position}")
    
    # Determine if using local file or SFTP
    use_sftp = SFTP_HOST and SFTP_USERNAME and SFTP_LOG_PATH
    
    if not use_sftp and not LOG_FILE_PATH:
        return []  # No log file configured
    
    try:
        if use_sftp:
            # Read from remote SFTP server
            sftp = get_sftp_connection()
            if not sftp:
                return []
            
            try:
                file_stat = sftp.stat(SFTP_LOG_PATH)
                file_size = file_stat.st_size
                
                # Handle log rotation (file became smaller)
                if log_file_position > file_size:
                    logger.info("[INFO] Log file rotated, resetting position")
                    log_file_position = 0
                
                # Only read new content
                if log_file_position < file_size:
                    with sftp.open(SFTP_LOG_PATH, 'r') as f:
                        f.seek(log_file_position)
                        new_content = f.read(file_size - log_file_position)
                        log_file_position = file_size
                        save_log_position(log_file_position)  # Save after reading
                        
                        # Decode and split into lines
                        new_lines = new_content.decode('utf-8', errors='ignore').split('\n')
                        death_messages = parse_death_messages(new_lines)
                        
            except FileNotFoundError:
                logger.warning(f"[WARNING] SFTP log file not found: {SFTP_LOG_PATH}")
                return []
                
        else:
            # Read from local file
            if not os.path.exists(LOG_FILE_PATH):
                return []
            
            file_size = os.path.getsize(LOG_FILE_PATH)
            
            # Handle log rotation (file became smaller)
            if log_file_position > file_size:
                logger.info("[INFO] Log file rotated, resetting position")
                log_file_position = 0
            
            with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(log_file_position)
                new_lines = f.readlines()
                log_file_position = f.tell()
                save_log_position(log_file_position)  # Save after reading
                death_messages = parse_death_messages(new_lines)
        
    except Exception as e:
        logger.error(f"[ERROR] Error reading log file: {e}")
    
    return death_messages


def parse_death_messages(lines):
    """
    Parse death messages from Minecraft log lines.
    Comprehensive patterns from Minecraft Wiki covering all vanilla death messages.
    
    Args:
        lines: List of log file lines to parse
        
    Returns:
        list: List of death message strings found
    """
    death_messages = []
    
    # Comprehensive death message patterns covering all Minecraft Java Edition death messages
    death_keywords = [
        # Direct death verbs
        'was pricked to death',  # Cactus
        'walked into a cactus',
        'drowned',
        'died from dehydration',  # Dolphin/Axolotl
        'experienced kinetic energy',  # Elytra into wall
        'blew up',
        'was blown up',
        'was killed by \[Intentional Game Design\]',  # Bed/Respawn anchor explosion
        'hit the ground too hard',
        'fell from a high place',
        'fell off a ladder',
        'fell off some vines',
        'fell off some weeping vines',
        'fell off some twisting vines',
        'fell off scaffolding',
        'fell while climbing',
        'was doomed to fall',
        'was impaled on a stalagmite',
        'was squashed by a falling anvil',
        'was squashed by a falling block',
        'was skewered by a falling stalactite',
        'went up in flames',
        'walked into fire',
        'burned to death',
        'was burned to a crisp',
        'went off with a bang',  # Firework
        'tried to swim in lava',
        'was struck by lightning',
        'discovered the floor was lava',  # Magma block
        'walked into the danger zone',
        'was killed by magic',
        'froze to death',
        'was frozen to death',
        'was slain by',  # Player/mob attack
        'was stung to death',  # Bee
        'was obliterated by a sonically-charged shriek',  # Warden
        'was smashed by',  # Mace
        'was shot by',  # Arrow/bow/crossbow
        'was pummeled by',  # Snowball (rare)
        'was fireballed by',
        'was shot by a skull from',  # Wither skull
        'starved to death',
        'suffocated in a wall',
        'was squished too much',  # Entity cramming
        'was squashed by',
        'left the confines of this world',  # World border
        'was poked to death by a sweet berry bush',
        'was killed while trying to hurt',  # Thorns
        'was impaled by',  # Trident
        'fell out of the world',  # Void
        "didn't want to live in the same world as",
        'withered away',
        'died',  # Generic/kill command
        'was killed',
        'was roasted in dragon',  # Dragon breath
        'was sniped by',  # Shulker (Bedrock)
        'was spitballed by',  # Llama (Bedrock)
    ]
    
    # Compile a single regex pattern that matches any of the death keywords
    # Match lines that contain player name followed by any death keyword
    death_pattern = re.compile(r'\[.*?\]: (\w+) (' + '|'.join(re.escape(kw) for kw in death_keywords) + ')', re.IGNORECASE)
    
    for line in lines:
        match = death_pattern.search(line)
        if match:
            # Extract the full death message after the timestamp
            msg_start = line.find(']: ') + 3
            if msg_start > 3:
                death_msg = line[msg_start:].strip()
                # Avoid duplicate processing
                if death_msg and death_msg not in death_messages:
                    death_messages.append(death_msg)
    
    return death_messages


async def poll_loop():
    """
    Main polling loop that checks for player changes and posts to Discord.
    
    This coroutine runs continuously, checking the Minecraft server's player list
    at regular intervals and posting notifications when players join or leave.
    """
    global last_online
    
    await client.wait_until_ready()
    channel = client.get_channel(int(CHANNEL_ID))
    
    if channel is None:
        logger.error(f"[ERROR] Could not find Discord channel with ID: {CHANNEL_ID}")
        logger.error("Please verify the channel ID and bot permissions.")
        await client.close()
        return
    
    logger.info(f"[OK] Connected to Discord channel: #{channel.name}")
    logger.info(f"[INFO] Polling every {POLL_SECONDS} seconds")
    logger.info(f"[INFO] Logout notifications: {'ENABLED' if NOTIFY_LOGOUT else 'DISABLED'}")
    
    # Initialize last_online with current players to avoid false "join" notifications on startup
    try:
        last_online = rcon_list_players()
        if last_online:
            logger.info(f"[INFO] Currently online: {', '.join(sorted(last_online))}")
        else:
            logger.info("[INFO] No players currently online")
    except Exception as e:
        logger.warning(f"[WARNING] Could not query initial player list: {e}")
        logger.info("Will retry on next poll...")
        last_online = set()
    
    logger.info("[OK] Bot is now monitoring the Minecraft server!\n")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while not client.is_closed():
        try:
            # Query current player list
            current = rcon_list_players()
            
            # Reset error counter on successful query
            consecutive_errors = 0
            
            # Detect players who joined
            joined = current - last_online
            for player in sorted(joined):
                message = f"**{player}** joined the server"
                try:
                    await channel.send(message)
                    logger.info(f"[JOIN] {player} joined the server")
                except Exception as discord_error:
                    logger.error(f"Failed to send Discord message: {discord_error}")
            
            # Detect players who left (optional)
            if NOTIFY_LOGOUT:
                left = last_online - current
                for player in sorted(left):
                    message = f"**{player}** left the server"
                    try:
                        await channel.send(message)
                        logger.info(f"[LEAVE] {player} left the server")
                    except Exception as discord_error:
                        logger.error(f"Failed to send Discord message: {discord_error}")
            
            # Check for death messages
            death_messages = check_log_for_deaths()
            for death_msg in death_messages:
                message = f"[DEATH] {death_msg}"
                try:
                    await channel.send(message)
                    logger.info(f"[DEATH] {death_msg}")
                except Exception as discord_error:
                    logger.error(f"Failed to send Discord death message: {discord_error}")
            
            # Update state
            last_online = current
            
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Poll error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"[ERROR] Too many consecutive errors ({max_consecutive_errors}). Shutting down.")
                logger.error("Please check your RCON configuration and server status.")
                await client.close()
                return
        
        # Wait before next poll
        await asyncio.sleep(int(POLL_SECONDS))


async def on_ready():
    """Event handler called when the Discord bot successfully connects."""
    logger.info(f"[OK] Discord bot logged in as {client.user}")
    logger.info(f"   User ID: {client.user.id}")
    logger.info(f"   Connected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


async def main():
    """
    Main entry point for the bot.
    
    Initializes the Discord client and starts the polling loop.
    """
    global client
    
    # Create Discord client with minimal intents
    intents = Intents.default()
    intents.message_content = False
    intents.members = False
    intents.presences = False
    client = Client(intents=intents)
    
    # Register event handler
    client.event(on_ready)
    
    async with client:
        # Start the polling task
        client.loop.create_task(poll_loop())
        
        # Connect to Discord
        try:
            await client.start(TOKEN)
        except Exception as e:
            logger.error(f"[ERROR] Failed to start Discord client: {e}")
            raise


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Minecraft Discord Notification Bot")
    logger.info("=" * 70)
    
    # Validate configuration before starting
    if not validate_configuration():
        logger.error("\n[ERROR] Bot startup aborted due to configuration errors.")
        sys.exit(1)
    
    logger.info("\n[CONFIG] Configuration:")
    logger.info(f"   RCON Host: {RCON_HOST}:{RCON_PORT}")
    logger.info(f"   Discord Channel ID: {CHANNEL_ID}")
    logger.info(f"   Poll Interval: {POLL_SECONDS}s")
    logger.info(f"   Notify Logout: {NOTIFY_LOGOUT}\n")
    
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[INFO] Received shutdown signal (Ctrl+C)")
        logger.info("[INFO] Shutting down gracefully...")
    except Exception as e:
        logger.error(f"\n[ERROR] Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("[OK] Bot stopped successfully")
