"""Diagnostic tool for inspecting database state"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("diagnose")

# Try to import the database connection
sys.path.append(os.getcwd())
try:
    from utils.db import initialize_db
    from models.server import Server
    from models.guild import Guild
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

async def diagnose_server(guild_id: int, server_id: str):
    """Diagnose issues with a server"""
    logger.info(f"Starting diagnosis for server {server_id} in guild {guild_id}")
    
    # Connect to the database
    try:
        db = await initialize_db()
        logger.info("Connected to MongoDB successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return
    
    # Check if guild exists - try both string and int formats
    str_query = await db.guilds.find_one({"guild_id": str(guild_id)})
    int_query = await db.guilds.find_one({"guild_id": guild_id})
    
    guild_data = str_query or int_query
    if not guild_data:
        logger.error(f"Guild with ID {guild_id} not found in database (tried both string and int types)")
        return
    
    logger.info(f"Guild found with query type: {'string' if str_query else 'integer'}")
    logger.info(f"Guild ID in DB: {guild_data.get('guild_id')} (type: {type(guild_data.get('guild_id')).__name__})")
    
    logger.info(f"Found guild in database: {guild_data.get('name')}")
    
    # Check server list
    servers = guild_data.get("servers", [])
    logger.info(f"Guild has {len(servers)} servers configured")
    
    for i, server in enumerate(servers):
        s_id = server.get("server_id")
        logger.info(f"Server {i+1}: ID={s_id} (type={type(s_id).__name__}), Name={server.get('server_name')}")
        
        if (s_id == server_id or 
            str(s_id) == str(server_id) or 
            (isinstance(s_id, int) and server_id.isdigit() and s_id == int(server_id)) or 
            (isinstance(s_id, str) and s_id.isdigit() and server_id.isdigit() and int(s_id) == int(server_id))):
            
            logger.info(f"Found target server: {server.get('server_name')}")
            logger.info(f"Server Data: {server}")
            
            # Check channel configuration
            channel_config = {
                "killfeed_channel_id": server.get("killfeed_channel_id"),
                "events_channel_id": server.get("events_channel_id"),
                "connections_channel_id": server.get("connections_channel_id"),
                "economy_channel_id": server.get("economy_channel_id"),
                "voice_status_channel_id": server.get("voice_status_channel_id")
            }
            
            logger.info("Channel configuration:")
            for channel_type, channel_id in channel_config.items():
                logger.info(f"  {channel_type}: {channel_id} (type={type(channel_id).__name__ if channel_id is not None else 'None'})")
            
            # Test update operation
            logger.info("Testing channel update operation...")
            server_obj = Server(db, server)
            
            # Create test update
            test_update = {}
            for key, value in channel_config.items():
                if value is not None:
                    test_update[key] = value
                    
            logger.info(f"Update data: {test_update}")
            
            if test_update:
                result = await server_obj.update(test_update)
                logger.info(f"Update result: {result}")
            else:
                logger.info("No channel IDs to test update with")
            
    
    # Check raw MongoDB queries
    logger.info("Testing raw MongoDB update operations...")
    
    # Try direct MongoDB update
    try:
        # First, let's confirm server_id exists
        query_result = await db.guilds.count_documents({"servers.server_id": server_id})
        logger.info(f"Documents matching server_id={server_id}: {query_result}")
        
        # Try updating with server_id as string
        str_result = await db.guilds.update_one(
            {"guild_id": str(guild_id), "servers.server_id": server_id},
            {"$set": {"servers.$.test_field": "test_value_string"}}
        )
        logger.info(f"Update with string ID - matched: {str_result.matched_count}, modified: {str_result.modified_count}")
        
        # Try updating with server_id as int if possible
        if server_id.isdigit():
            int_result = await db.guilds.update_one(
                {"guild_id": str(guild_id), "servers.server_id": int(server_id)},
                {"$set": {"servers.$.test_field": "test_value_int"}}
            )
            logger.info(f"Update with int ID - matched: {int_result.matched_count}, modified: {int_result.modified_count}")
    
    except Exception as e:
        logger.error(f"Error during raw MongoDB operations: {e}")

async def list_guilds(db):
    """List all guilds in the database"""
    logger.info("Listing all guilds in the database...")
    
    cursor = db.guilds.find({})
    guilds = await cursor.to_list(length=None)
    
    if not guilds:
        logger.error("No guilds found in the database")
        return
    
    logger.info(f"Found {len(guilds)} guilds:")
    for guild in guilds:
        guild_id = guild.get('guild_id')
        guild_id_type = type(guild_id).__name__
        logger.info(f"  Guild ID: {guild_id} | Type: {guild_id_type} | Name: {guild.get('name')}")
        
        # Try explicit queries with this guild ID to verify type handling
        str_match = await db.guilds.find_one({"guild_id": str(guild_id)})
        int_match = None
        if isinstance(guild_id, str) and guild_id.isdigit():
            int_match = await db.guilds.find_one({"guild_id": int(guild_id)})
        elif isinstance(guild_id, int):
            int_match = await db.guilds.find_one({"guild_id": guild_id})
            
        logger.info(f"    Query by string: {str_match is not None}")
        logger.info(f"    Query by int: {int_match is not None}")
        
        servers = guild.get('servers', [])
        logger.info(f"  Servers: {len(servers)}")
        for server in servers:
            server_id = server.get('server_id')
            server_id_type = type(server_id).__name__
            logger.info(f"    Server ID: {server_id} | Type: {server_id_type} | Name: {server.get('server_name')}")
            
            # Check for channel configurations
            channel_ids = {
                "killfeed": server.get("killfeed_channel_id"),
                "events": server.get("events_channel_id"),
                "connections": server.get("connections_channel_id"),
                "economy": server.get("economy_channel_id"),
                "voice": server.get("voice_status_channel_id")
            }
            logger.info(f"      Channel IDs: {channel_ids}")

async def main():
    """Main function"""
    # Connect to database
    try:
        db = await initialize_db()
        logger.info("Connected to MongoDB successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return
    
    # List all guilds first
    await list_guilds(db)
    
    # Then try diagnosis on a specific guild/server if requested
    guild_id = 1219706687980568769  # Replace with your guild ID
    server_id = "7020"  # Replace with your server ID
    
    await diagnose_server(guild_id, server_id)

if __name__ == "__main__":
    asyncio.run(main())
