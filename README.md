# Emeralds PvP Stats Bot

A sophisticated Discord bot utility for comprehensive game data analysis, leveraging advanced event tracking and dynamic visualization techniques for Deadside.

## Features

- PvP Kill Tracking: Real-time monitoring and stats for player kills
- Event Tracking: Monitor in-game events like airdrops, missions, and trader spawns
- Player Statistics: Comprehensive player performance metrics
- Economy System: Virtual currency earned through kills
- Premium Tiers: Scalable feature access with tiered premium options

## Deployment Guide for Railway

### Prerequisites

1. Create a Railway account: https://railway.app/
2. Install Railway CLI: https://docs.railway.app/develop/cli

### Steps to Deploy

1. **Login to Railway**

```bash
railway login
```

2. **Link the Project**

```bash
railway link
```

*Note: Dependencies are automatically installed based on the configuration in railway.json*

3. **Set Required Environment Variables**

From the Railway dashboard, add the following environment variables:

- `DISCORD_TOKEN`: Your Discord bot token
- `MONGODB_URI`: MongoDB connection string
- `OWNER_ID`: Discord ID of the bot owner

4. **Deploy the Bot**

```bash
railway up
```

5. **Verify Status**

Check the deployment status in your Railway dashboard.

## Configuration

The bot will use the environment variables set in Railway. Make sure all required variables are set before deployment.

## Monitoring

Monitor your bot's logs and performance in the Railway dashboard to ensure it's functioning correctly.

## Maintenance Tools

This bot includes maintenance utilities to help with troubleshooting and management:

### Restart Script

If you need to manually restart the bot, use:

```bash
./restart_bot.sh
```

This will terminate the current bot process and allow the workflow system to restart it automatically.

### Maintenance Utility

The `maintenance.py` script provides various utilities for maintaining and troubleshooting the bot:

```bash
# Show available commands
python maintenance.py help

# Restart the bot
python maintenance.py restart

# List all configured servers
python maintenance.py list_servers

# Run diagnostics on the database
python maintenance.py diagnose

# Fix type inconsistencies in the database
python maintenance.py fix_types

# Clear error states in the database
python maintenance.py clear_errors
```

### Type Handling

All channel IDs are stored as integers in the database and explicitly converted to integers before being used with Discord's API. This ensures consistent behavior across the application.

---

Powered By Discord.gg/EmeraldServers