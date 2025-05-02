"""
Tower of Temptation PvP Statistics Discord Bot
Main entry point for the application
"""
import asyncio
import logging
import os
from bot import initialize_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to run the Discord bot"""
    try:
        # Force a global sync of commands when starting the bot
        # This is particularly useful when switching between test and production bots
        force_sync = True
        
        bot = await initialize_bot(force_sync=force_sync)
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.critical("DISCORD_TOKEN environment variable not set. Exiting.")
            return
        
        # Command syncing is now handled directly in bot.py on_ready event
        
        await bot.start(token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
