# Minecraft Discord Bot - Setup

This bot writes a announcement message into a discord channel if someone connect, disconnects or dies on your server.

### 1. Discord Bot Setup
1. Go to https://discord.com/developers/applications
2. Click "New Application" → name it
3. Go to "Bot" tab → "Add Bot"
4. Under token, click "Reset Token" → **Copy this token**
5. Go to "OAuth2" → "URL Generator"
   - Check: `bot`
   - Check: `Send Messages`, `View Channels`
   - Copy the URL and open it to invite bot to your server

### 2. Get Channel ID
1. Discord → Settings → Advanced → Enable "Developer Mode"
2. Right-click your channel → "Copy Channel ID"

### 3. Enable RCON on Minecraft
In your server.properties:
```
enable-rcon=true
rcon.port=25575
rcon.password=your_password_here
```
Restart server. Make sure port 25575 is open.

### 4. Fill in .env (Basic Configuration)
```
DISCORD_TOKEN=your_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
RCON_HOST=your.server.address
RCON_PORT=25575
RCON_PASSWORD=your_rcon_password
POLL_SECONDS=5
NOTIFY_LOGOUT=true
```

### 5. SFTP Access for Death Message Notifications (Optional)
Add these to your .env:
```
SFTP_HOST=your.server.hostname
SFTP_PORT=2022
SFTP_USERNAME=your_sftp_username
SFTP_LOG_PATH=/logs/latest.log
LOG_FILE_PATH=
```

**Important: Password with Special Characters**
If your SFTP password contains special characters, create a file named `.sftp_password` in the bot directory with ONLY your password:
The bot will automatically read from this file if the .env password appears truncated.

### 6. Install and Run
```bash
python -m pip install -r requirements.txt
python test_config.py  # Validates everything
python bot.py          # Start the bot
```

## Common Issues
**RCON connection refused**
- Verify enable-rcon=true in server.properties
- Check port 25575 is open
- Restart MC server

**Discord channel not found**
- Check channel ID is correct
- Bot must be invited to server and have permission to read + write message and view channels

**SFTP connection fails**
- Check port (usually 2022, not 22)
- Ensure SFTP_LOG_PATH is correct (default is /logs/latest.log)
