"""
Bot initialization and configuration
"""
import os
import logging
import discord
from discord.ext import commands
import asyncio

from config import COMMAND_PREFIX, INTENTS, ACTIVITY
from utils.db import initialize_db

logger = logging.getLogger(__name__)

async def initialize_bot():
    """Initialize and configure the Discord bot instance"""
    # Set up intents
    intents = discord.Intents.default()
    for intent_name in INTENTS:
        if hasattr(intents, intent_name):
            setattr(intents, intent_name, True)

    # Create bot instance
    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or(COMMAND_PREFIX),
        intents=intents,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=ACTIVITY
        ),
        help_command=None
    )

    # Initialize database connection
    db = await initialize_db()
    bot.db = db

    # Store important bot variables
    bot.home_guild_id = 0
    if os.getenv("HOME_GUILD_ID"):
        try:
            bot.home_guild_id = int(os.getenv("HOME_GUILD_ID"))
        except (ValueError, TypeError):
            logger.warning("Invalid HOME_GUILD_ID environment variable")
    
    # Owner ID is hardcoded for security
    bot.owner_id = 462961235382763520  # Your Discord User ID
    
    # Initialize connections and task trackers
    bot.sftp_connections = {}
    bot.background_tasks = {}
    bot.server_monitors = {}
    
    # Add base event handlers
    @bot.event
    async def on_ready():
        """Called when the bot is ready"""
        guilds = len(bot.guilds)
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Connected to {guilds} guilds")
        
        # Load extension cogs
        await load_extensions(bot)
        
        # Start background tasks for all registered servers
        await setup_background_tasks(bot)

    @bot.event
    async def on_guild_join(guild):
        """Called when the bot joins a new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        # Create guild document in database
        guild_data = {
            "guild_id": guild.id,
            "name": guild.name,
            "premium_tier": 0,
            "joined_at": discord.utils.utcnow().isoformat(),
            "servers": []
        }
        await bot.db.guilds.update_one(
            {"guild_id": guild.id}, 
            {"$setOnInsert": guild_data}, 
            upsert=True
        )

    @bot.event
    async def on_command_error(ctx, error):
        """Global error handler for commands"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Bad argument: {error}")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(f"I need the following permissions to run this command: {perms}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
        else:
            logger.error(f"Command error: {error}", exc_info=True)
            await ctx.send(f"An error occurred: {error}")

    return bot

async def load_extensions(bot):
    """Load all extension cogs"""
    extensions = [
        "cogs.admin",
        "cogs.killfeed",
        "cogs.stats",
        "cogs.events",
        "cogs.setup",
        "cogs.premium",
        "cogs.economy"
    ]
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            logger.info(f"Loaded extension: {extension}")
        except Exception as e:
            logger.error(f"Failed to load extension {extension}: {e}", exc_info=True)

async def pay_interest_task(bot):
    """Background task to pay interest to all players weekly"""
    try:
        # Wait until the bot is ready
        await bot.wait_until_ready()
        
        # Import the economy model
        from models.economy import Economy
        from models.guild import Guild
        
        logger.info("Started weekly interest payment task")
        
        while not bot.is_closed():
            # Wait for 1 week (in seconds)
            # For testing, you can reduce this to a smaller value
            await asyncio.sleep(7 * 24 * 60 * 60)  # 7 days
            
            # Get all guilds with registered servers
            cursor = bot.db.guilds.find({"servers": {"$exists": True, "$ne": []}})
            
            async for guild_doc in cursor:
                guild_id = guild_doc["guild_id"]
                guild = Guild(bot.db, guild_doc)
                
                # Only process guilds with premium tier 2+
                if guild.premium_tier < 2:
                    continue
                
                interest_rate = 0.01  # 1% interest
                
                # Process each server in the guild
                for server in guild_doc["servers"]:
                    server_id = server["server_id"]
                    
                    # Pay interest to all players
                    players_paid, total_interest = await Economy.pay_interest_to_all(
                        bot.db, server_id, interest_rate
                    )
                    
                    if players_paid > 0:
                        logger.info(
                            f"Paid {total_interest} credits of interest to {players_paid} players "
                            f"on server {server_id} (Guild: {guild_id})"
                        )
                        
                        # Try to send a notification to the configured economy channel
                        try:
                            # Find the server's economy channel if set
                            economy_channel_id = server.get("economy_channel_id")
                            if economy_channel_id:
                                channel = bot.get_channel(int(economy_channel_id))
                                if channel:
                                    await channel.send(
                                        f"💰 **Weekly Interest Paid**\n"
                                        f"Paid {total_interest} credits of interest to {players_paid} players\n"
                                        f"Current interest rate: {interest_rate*100:.1f}%"
                                    )
                        except Exception as e:
                            logger.error(f"Error sending interest notification: {e}")
    
    except Exception as e:
        logger.error(f"Error in interest payment task: {e}", exc_info=True)

async def setup_background_tasks(bot):
    """Set up background tasks for all registered servers"""
    # Get all guilds with registered servers
    cursor = bot.db.guilds.find({"servers": {"$exists": True, "$ne": []}})
    
    # Start weekly interest payment task (premium tier 2+ feature)
    interest_task = asyncio.create_task(pay_interest_task(bot))
    bot.background_tasks["interest_payment"] = interest_task
    
    async for guild_doc in cursor:
        guild_id = guild_doc["guild_id"]
        
        # For each server in the guild, start monitoring
        for server in guild_doc["servers"]:
            server_id = server["server_id"]
            
            # Import the background task functions
            from cogs.killfeed import start_killfeed_monitor
            from cogs.events import start_events_monitor
            
            # Get guild premium tier
            premium_tier = guild_doc.get("premium_tier", 0)
            
            # Start killfeed monitor (available for all tiers)
            killfeed_task = asyncio.create_task(
                start_killfeed_monitor(bot, guild_id, server_id)
            )
            task_name = f"killfeed_{guild_id}_{server_id}"
            bot.background_tasks[task_name] = killfeed_task
            
            # Start events monitor (premium tier 1+)
            if premium_tier >= 1:
                events_task = asyncio.create_task(
                    start_events_monitor(bot, guild_id, server_id)
                )
                task_name = f"events_{guild_id}_{server_id}"
                bot.background_tasks[task_name] = events_task
