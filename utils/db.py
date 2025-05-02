"""
Database utility functions for MongoDB connections and operations
"""
import os
import logging
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import MONGODB_SETTINGS, COLLECTIONS

logger = logging.getLogger(__name__)

async def initialize_db():
    """Initialize MongoDB connection and return database object"""
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        logger.critical("MONGODB_URI environment variable not set. Exiting.")
        raise ValueError("MONGODB_URI environment variable not set")
    
    try:
        # Create client with configuration
        client = motor.motor_asyncio.AsyncIOMotorClient(
            mongodb_uri, 
            **MONGODB_SETTINGS
        )
        
        # Check connection
        await client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Get database
        db_name = os.getenv("MONGODB_DB", "pvp_stats_bot")
        db = client[db_name]
        
        # Create collections and indexes
        await create_collections_and_indexes(db)
        
        return db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.critical(f"Failed to connect to MongoDB: {e}")
        raise

async def create_collections_and_indexes(db):
    """Create necessary collections and indexes"""
    try:
        # Ensure collections exist (MongoDB creates them on first access)
        for collection_name in COLLECTIONS.values():
            try:
                await db.create_collection(collection_name)
                logger.info(f"Created collection: {collection_name}")
            except:
                # Collection already exists
                pass
        
        # Create indexes
        # Guild collection indexes
        await db[COLLECTIONS["guilds"]].create_index("guild_id", unique=True)
        
        # Players collection indexes
        await db[COLLECTIONS["players"]].create_index([
            ("server_id", 1),
            ("player_id", 1)
        ], unique=True)
        await db[COLLECTIONS["players"]].create_index("player_name")
        
        # Kills collection indexes
        await db[COLLECTIONS["kills"]].create_index([
            ("server_id", 1),
            ("timestamp", 1)
        ])
        await db[COLLECTIONS["kills"]].create_index("killer_id")
        await db[COLLECTIONS["kills"]].create_index("victim_id")
        
        # Events collection indexes
        await db[COLLECTIONS["events"]].create_index([
            ("server_id", 1),
            ("timestamp", 1)
        ])
        await db[COLLECTIONS["events"]].create_index("event_type")
        
        # Connections collection indexes
        await db[COLLECTIONS["connections"]].create_index([
            ("server_id", 1),
            ("player_id", 1),
            ("timestamp", 1)
        ])
        
        logger.info("Created all necessary indexes")
    except Exception as e:
        logger.error(f"Error creating collections or indexes: {e}", exc_info=True)
        raise
