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
        bot = await initialize_bot()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.critical("DISCORD_TOKEN environment variable not set. Exiting.")
            return
        
        await bot.start(token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
