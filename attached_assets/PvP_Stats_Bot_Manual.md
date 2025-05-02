
# Tower of Temptation PvP Statistics Discord Bot - Build Manual

## Overview
This bot is a high-performance, multi-guild, multi-server PvP statistics and event tracking system using Discord. It includes real-time and historical data parsing from CSV and log files obtained via SFTP. The bot is scalable, modular, and designed for advanced customization and premium feature tiers.

## Core Systems
### 1. Multi-Guild & Multi-Server Support
- Each Discord guild can register multiple servers.
- Each server connection uses unique SFTP credentials and a `ServerID`.
- Connection root is found using pattern: `host_serverID`.

### 2. SFTP Integration
- Use provided SFTP credentials to recursively locate:
  - Latest `.csv` file by timestamp for killfeed parsing.
  - All `.csv` files for historical data parsing.
  - `Deadside.log` for event and connection tracking.
- Detect when a new `Deadside.log` is created (reset player count).

### 3. Parsers
- **Killfeed Parser**: Uses latest `.csv` for real-time updates.
- **Historical Parser**: On server add, parses all `.csv` for full stats. 
  - Tracks line position to avoid duplicates.
  - Outputs progress update every 60s.
- **Events/Connections Parser**: Parses `Deadside.log` for:
  - Event types: Missions, Airdrops, Crashes, Traders, Convoys, Encounters.
  - Player connections and console/PC detection.
  - Voice channel name reflects online and queued players.

## Stats & Tracking
- Suicides:
  - If killer == victim: suicide.
  - If weapon == `suicide_by_relocation`: menu suicide.
  - If weapon == `Falling`: fall death.
  - Randomized messages in embed output.
  - Tracked separately (not kills or deaths).
- Track everything:
  - Kills, Deaths, KDR, Longest Shot, Kill/Death Streaks
  - Weapon usage stats and leaderboards.

## Discord UI & UX
- Use latest Pycord and Discord API.
- Use embeds with:
  - Emerald-themed survival look (custom logos as placeholders).
  - Randomized flavor text for suicide events.
  - Professional design, no codeblocks or emojis.
- Commands:
  - Use parent/subcommands, autocomplete, buttons, modals, pagination.
- Admin Permissions:
  - Role-based.
  - Only guild admins can change settings or add servers.
  - Home guild admins (set by bot owner) can assign premium.

## Premium System
- Premium is guild-based.
- Free tier: Killfeed only.
- Premium tiers unlock:
  - More server slots.
  - Event/connection output.
  - Stats features.
  - Customizable embeds and interfaces.

## Technical Requirements
- Use: Python 3.11+, Pycord, Motor (MongoDB async driver).
- Ensure all commands prone to timeouts use background tasks.
- Show immediate "in progress" and then update with results.
- Recheck this manual every 60s and adapt.
- Avoid Replit checkpoint abuse:
  - Modular structure.
  - Efficient memory handling.
  - Only import what you use.
- Challenge: **Build in ≤10 Replit checkpoints**.
- No monkey patches, fix scripts, or quick hacks. Use only best practices.

## Goal
To create the most advanced PvP Discord bot available, exceeding all others in complexity, depth, customization, and user control.

---
