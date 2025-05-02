"""
Configuration settings for the bot
"""

# Bot command prefix
COMMAND_PREFIX = "!"

# Bot activity message
ACTIVITY = "PvP Stats"

# Required intents for the bot
INTENTS = [
    "guilds",
    "guild_messages",
    "message_content",
    "guild_members",
    "guild_voice_states"
]

# MongoDB connection settings
MONGODB_SETTINGS = {
    "minPoolSize": 5,
    "maxPoolSize": 50,
    "connectTimeoutMS": 30000,
    "socketTimeoutMS": 30000,
    "serverSelectionTimeoutMS": 30000,
    "waitQueueTimeoutMS": 30000,
    "retryWrites": True,
}

# Database collection names
COLLECTIONS = {
    "guilds": "guilds",
    "players": "players",
    "kills": "kills",
    "events": "events",
    "connections": "connections",
    "economy": "economy",
    "transactions": "transactions",
}

# SFTP connection settings
SFTP_CONNECTION_SETTINGS = {
    "timeout": 30,
    "banner_timeout": 30,
    "auth_timeout": 30,
    "look_for_keys": False,
}

# SFTP CSV and log file patterns
CSV_FILENAME_PATTERN = r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\.csv"
LOG_FILENAME = "Deadside.log"

# CSV file structure
CSV_FIELDS = {
    "timestamp": 0,
    "killer_name": 1,
    "killer_id": 2,
    "victim_name": 3,
    "victim_id": 4,
    "weapon": 5,
    "distance": 6,
}

# Premium tiers configuration
PREMIUM_TIERS = {
    0: {  # Free tier
        "max_servers": 1,
        "features": ["killfeed"],
        "server_slots": 1,
    },
    1: {  # Basic premium
        "max_servers": 3,
        "features": ["killfeed", "events", "connections", "economy"],
        "server_slots": 3,
    },
    2: {  # Standard premium
        "max_servers": 5,
        "features": ["killfeed", "events", "connections", "stats", "economy", "gambling"],
        "server_slots": 5,
    },
    3: {  # Advanced premium
        "max_servers": 10,
        "features": ["killfeed", "events", "connections", "stats", "custom_embeds", "economy", "gambling"],
        "server_slots": 10,
    }
}

# Suicide messages for randomization
SUICIDE_MESSAGES = [
    "found the fastest way back to base",
    "decided life was too hard",
    "couldn't handle the pressure",
    "took the easy way out",
    "met a fatal error in judgment",
    "disconnected from reality",
    "chose a more direct path to respawn",
    "performed an unscheduled rapid disassembly",
    "ragequit in real life",
    "experienced a catastrophic user error",
    "became one with the void",
    "achieved peak efficiency in getting back to spawn",
    "executed the ultimate shortcut",
]

# Type-specific suicide messages
SUICIDE_MESSAGES_BY_TYPE = {
    "menu": [
        "pressed Alt+F4 IRL",
        "pulled their own plug",
        "found the 'Respawn' button",
        "CTD (crashed to death)",
        "force-quit their existence",
        "executed /kill in real life",
        "preferred to start fresh",
        "performed a hard reset",
        "unexpectedly terminated",
        "experienced a critical runtime error"
    ],
    "fall": [
        "discovered gravity works",
        "forgot how to operate legs",
        "had a rapid unplanned dismount",
        "tested fall damage",
        "tried to fly without wings",
        "forgot parachutes don't come standard",
        "performed a terminal velocity check",
        "thought they could make that jump",
        "miscalculated the landing zone",
        "did a high-speed ground inspection"
    ],
    "other": [
        "decided to experiment with their own mortality",
        "wanted to see the respawn screen",
        "went out on their own terms",
        "created a self-inflicted skills issue",
        "proved they're their own worst enemy",
        "eliminated the middle man",
        "chose the path of most resistance",
        "wanted to start over with a clean slate",
        "completed a very personal quest",
        "took self-reliance to the extreme"
    ]
}

# Event types and patterns to match in log file
EVENT_PATTERNS = {
    "mission": r"Mission started: (.+)",
    "airdrop": r"Air drop inbound at location: (.+)",
    "crash": r"Helicopter crash site spawned at: (.+)",
    "trader": r"Trader spawned at: (.+)",
    "convoy": r"Convoy started route from (.+) to (.+)",
    "encounter": r"Special encounter triggered: (.+) at (.+)",
}

# Embed theme color (emerald green)
EMBED_COLOR = 0x50C878

# Default embed footer
EMBED_FOOTER = "Tower of Temptation PvP Statistics"

# Refresh intervals (in seconds)
KILLFEED_REFRESH_INTERVAL = 30
EVENTS_REFRESH_INTERVAL = 60
CONNECTION_REFRESH_INTERVAL = 60
