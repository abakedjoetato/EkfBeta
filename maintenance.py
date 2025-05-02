#!/usr/bin/env python
"""
Maintenance script for the Discord bot

This script provides utilities for maintaining and troubleshooting the Discord bot,
including restarting workflows, fixing database issues, and clearing error states.

Usage:
    python maintenance.py [command]

Commands:
    restart              - Restart the Discord bot workflow
    clear_errors         - Clear error states in the database
    list_servers         - List all servers configured in the database
    diagnose             - Run diagnostics on the bot's database
    fix_types            - Fix type inconsistencies in the database
    help                 - Show this help message
"""

import os
import sys
import signal
import asyncio
import logging
from datetime import datetime

# Function to connect to MongoDB
async def connect_to_mongodb():
    """Connect to MongoDB using URI from environment variables"""
    try:
        # Import necessary modules
        import os
        import motor.motor_asyncio
        from pymongo import MongoClient
        
        # Get MongoDB URI from environment
        mongodb_uri = os.environ.get('MONGODB_URI')
        if not mongodb_uri:
            logger.error("MONGODB_URI not found in environment variables")
            return None
        
        # Create client and database
        client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_uri)
        db = client.get_default_database()
        
        # Test connection
        info = await db.command('serverStatus')
        logger.info(f"Connected to MongoDB version: {info.get('version', 'unknown')}")
        
        # Return database instance
        return db
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        return None
from models.guild import Guild
from models.server import Server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('maintenance')

async def restart_bot():
    """Restart the Discord bot workflow"""
    try:
        # Find and kill the bot process
        import psutil
        
        logger.info("Looking for bot process...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0] and 'main.py' in ' '.join(cmdline):
                    logger.info(f"Found bot process: {proc.info['pid']}")
                    logger.info(f"Terminating process: {proc.info['pid']}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    logger.info("Bot process terminated. Workflow will restart automatically.")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        logger.warning("No bot process found. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error restarting bot: {e}")
        return False

async def clear_errors():
    """Clear error states in the database"""
    try:
        db = await connect_to_mongodb()
        
        # Reset error states in all servers
        result = await db.guilds.update_many(
            {}, 
            {"$set": {
                "servers.$[].error_state": False,
                "servers.$[].last_error": None,
                "servers.$[].error_count": 0,
                "servers.$[].updated_at": datetime.utcnow().isoformat()
            }}
        )
        
        logger.info(f"Cleared error states for {result.modified_count} servers")
        return True
    except Exception as e:
        logger.error(f"Error clearing error states: {e}")
        return False

async def list_servers():
    """List all servers configured in the database"""
    try:
        db = await connect_to_mongodb()
        
        # Find all guilds
        guilds = await db.guilds.find({}).to_list(length=None)
        
        if not guilds:
            logger.info("No guilds found in the database")
            return True
        
        logger.info(f"Found {len(guilds)} guilds in the database")
        
        for guild_data in guilds:
            guild = Guild(db, guild_data)
            logger.info(f"Guild: {guild.name} (ID: {guild.id}, Premium Tier: {guild.premium_tier})")
            
            if not guild.servers:
                logger.info("  No servers configured for this guild")
                continue
            
            logger.info(f"  Found {len(guild.servers)} servers:")
            for server_data in guild.servers:
                server = Server(db, server_data)
                logger.info(f"  - Server: {server.name} (ID: {server.id})")
                logger.info(f"    Host: {server.host}:{server.port}")
                logger.info(f"    Channels: Killfeed: {server.killfeed_channel_id}, " +
                           f"Events: {server.events_channel_id}, " +
                           f"Connections: {server.connections_channel_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error listing servers: {e}")
        return False

async def diagnose():
    """Run diagnostics on the bot's database"""
    try:
        db = await connect_to_mongodb()
        
        logger.info("Running database diagnostics...")
        
        # Check database connectivity
        try:
            info = await db.command('serverStatus')
            logger.info(f"Connected to MongoDB version: {info.get('version', 'unknown')}")
        except Exception as e:
            logger.error(f"Database connectivity issue: {e}")
        
        # Check guild and server collections
        guilds_count = await db.guilds.count_documents({})
        logger.info(f"Found {guilds_count} guilds in the database")
        
        # Check for type inconsistencies in channel IDs
        type_issues = []
        guilds = await db.guilds.find({}).to_list(length=None)
        
        for guild_data in guilds:
            for server_data in guild_data.get('servers', []):
                # Check channel ID fields
                channel_id_fields = [
                    "killfeed_channel_id", "events_channel_id", "connections_channel_id", 
                    "economy_channel_id", "voice_status_channel_id"
                ]
                
                for field in channel_id_fields:
                    if field in server_data and server_data[field] is not None:
                        if not isinstance(server_data[field], int):
                            type_issues.append({
                                "guild_id": guild_data.get('guild_id'),
                                "server_id": server_data.get('server_id'),
                                "field": field,
                                "value": server_data[field],
                                "type": type(server_data[field]).__name__
                            })
        
        if type_issues:
            logger.warning(f"Found {len(type_issues)} type inconsistencies:")
            for issue in type_issues:
                logger.warning(f"  Guild {issue['guild_id']}, Server {issue['server_id']}: " +
                             f"{issue['field']} is {issue['value']} (type: {issue['type']})")
        else:
            logger.info("No type inconsistencies found in channel IDs")
        
        return True
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return False

async def fix_types():
    """Fix type inconsistencies in the database"""
    try:
        db = await connect_to_mongodb()
        
        logger.info("Fixing type inconsistencies in the database...")
        
        # Get all guilds
        guilds = await db.guilds.find({}).to_list(length=None)
        fixed_count = 0
        
        for guild_data in guilds:
            guild_id = guild_data.get('guild_id')
            
            # Track if we need to update this guild
            need_update = False
            
            # Process each server in the guild
            for server_index, server_data in enumerate(guild_data.get('servers', [])):
                server_id = server_data.get('server_id')
                
                # Process channel ID fields
                channel_id_fields = [
                    "killfeed_channel_id", "events_channel_id", "connections_channel_id", 
                    "economy_channel_id", "voice_status_channel_id"
                ]
                
                for field in channel_id_fields:
                    if field in server_data and server_data[field] is not None:
                        # If it's not an integer, convert it
                        if not isinstance(server_data[field], int):
                            try:
                                old_value = server_data[field]
                                guild_data['servers'][server_index][field] = int(old_value)
                                need_update = True
                                logger.info(f"Converted {field} from {old_value} " +
                                           f"({type(old_value).__name__}) to " +
                                           f"{guild_data['servers'][server_index][field]} (int) " +
                                           f"for server {server_id} in guild {guild_id}")
                            except (ValueError, TypeError) as e:
                                logger.error(f"Could not convert {field} value {server_data[field]}: {e}")
            
            # Update the guild if needed
            if need_update:
                result = await db.guilds.replace_one({"_id": guild_data["_id"]}, guild_data)
                if result.modified_count > 0:
                    fixed_count += 1
        
        logger.info(f"Fixed type inconsistencies in {fixed_count} guilds")
        return True
    except Exception as e:
        logger.error(f"Error fixing type inconsistencies: {e}")
        return False

async def help_command():
    """Show help message"""
    print(__doc__)
    return True

async def main():
    # Map commands to functions
    commands = {
        "restart": restart_bot,
        "clear_errors": clear_errors,
        "list_servers": list_servers,
        "diagnose": diagnose,
        "fix_types": fix_types,
        "help": help_command
    }
    
    # Get command from arguments
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Error: Please specify a valid command")
        await help_command()
        return 1
    
    command = sys.argv[1]
    logger.info(f"Running command: {command}")
    
    # Execute the command
    result = await commands[command]()
    
    if result:
        logger.info(f"Command '{command}' completed successfully")
        return 0
    else:
        logger.error(f"Command '{command}' failed")
        return 1

if __name__ == "__main__":
    return_code = asyncio.run(main())
    sys.exit(return_code)
