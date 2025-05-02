"""
Server model for database operations
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class Server:
    """Server model for database operations"""
    
    def __init__(self, db, server_data):
        """Initialize server model"""
        self.db = db
        self.data = server_data
        self.id = server_data.get("server_id")
        self.name = server_data.get("server_name")
        self.guild_id = server_data.get("guild_id")
        self.sftp_host = server_data.get("sftp_host")
        self.sftp_port = server_data.get("sftp_port")
        self.sftp_username = server_data.get("sftp_username")
        self.sftp_password = server_data.get("sftp_password")
        self.killfeed_channel_id = server_data.get("killfeed_channel_id")
        self.events_channel_id = server_data.get("events_channel_id")
        self.connections_channel_id = server_data.get("connections_channel_id")
        self.voice_status_channel_id = server_data.get("voice_status_channel_id")
        self.last_csv_line = server_data.get("last_csv_line", 0)
        self.last_log_line = server_data.get("last_log_line", 0)
        self.created_at = server_data.get("created_at")
        self.updated_at = server_data.get("updated_at")
        
        # Event notification settings - default to all enabled
        self.event_notifications = server_data.get("event_notifications", {
            "mission": True,
            "airdrop": True,
            "crash": True,
            "trader": True,
            "convoy": True,
            "encounter": True,
            "server_restart": True
        })
        
        # Connection notification settings - default to all enabled
        self.connection_notifications = server_data.get("connection_notifications", {
            "connect": True,
            "disconnect": True
        })
        
        # Suicide notification settings - default to all enabled
        self.suicide_notifications = server_data.get("suicide_notifications", {
            "menu": True,
            "fall": True,
            "other": True
        })
    
    @classmethod
    async def get_by_id(cls, db, server_id: str, guild_id: Optional[int] = None) -> Optional['Server']:
        """Get a server by ID"""
        # Build query
        query = {"server_id": server_id}
        if guild_id:
            query["guild_id"] = str(guild_id)  # Convert to string to avoid type issues
        
        # Find server in guild collection
        guild_data = await db.guilds.find_one({
            "servers.server_id": server_id
        })
        
        if not guild_data:
            return None
        
        # Find the server in the guild's servers array
        server_data = None
        for server in guild_data.get("servers", []):
            if server.get("server_id") == server_id:
                server_data = server
                break
        
        if not server_data:
            return None
        
        return cls(db, server_data)
    
    @classmethod
    async def create(cls, db, server_data: Dict[str, Any]) -> 'Server':
        """Create a new server"""
        # Set timestamps
        server_data["created_at"] = datetime.utcnow().isoformat()
        server_data["updated_at"] = server_data["created_at"]
        
        # Set default values
        server_data.setdefault("last_csv_line", 0)
        server_data.setdefault("last_log_line", 0)
        
        # Add server to guild
        await db.guilds.update_one(
            {"guild_id": str(server_data["guild_id"])},
            {"$push": {"servers": server_data}}
        )
        
        return cls(db, server_data)
    
    async def update(self, update_data: Dict[str, Any]) -> bool:
        """Update server data"""
        # Set updated timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Log the update operation for detailed debugging
        logger.info(f"Updating server {self.id} in guild {self.guild_id} with data: {update_data}")
        
        # Ensure channel IDs are stored as integers, not strings
        channel_id_fields = [
            "killfeed_channel_id", "events_channel_id", "connections_channel_id", 
            "economy_channel_id", "voice_status_channel_id"
        ]
        
        # Convert any channel IDs to integers before updating
        for field in channel_id_fields:
            if field in update_data and update_data[field] is not None:
                try:
                    # Ensure channel IDs are stored as integers
                    update_data[field] = int(update_data[field])
                    logger.info(f"Converted {field} to integer: {update_data[field]}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting {field} to integer: {e}")
        
        # Update specific fields in the server document within the guild
        try:
            # Simplify the query to ensure we match the exact server
            # Convert guild_id to int to ensure consistent type matching
            int_guild_id = int(self.guild_id) if str(self.guild_id).isdigit() else self.guild_id
            
            # Direct query for the specific server using the server_id
            # This is the most reliable way to find the exact server document
            query = {
                "guild_id": int_guild_id,
                "servers.server_id": self.id
            }
            
            # Create the update document with proper dot notation for nested fields
            update_doc = {}
            for key, value in update_data.items():
                update_doc[f"servers.$.{key}"] = value
            
            # Execute the update with detailed logging
            logger.info(f"Executing MongoDB update with query: {query}")
            logger.info(f"Update document: {update_doc}")
            
            result = await self.db.guilds.update_one(
                query,
                {"$set": update_doc}
            )
            
            logger.info(f"MongoDB update result: matched={result.matched_count}, modified={result.modified_count}")
            
            # Update local data if the update was successful
            if result.matched_count > 0:
                for key, value in update_data.items():
                    setattr(self, key, value)
                    self.data[key] = value
                
                # Verify the update was actually saved by retrieving the document again
                verification_doc = await self.db.guilds.find_one({
                    "guild_id": int_guild_id,
                    "servers.server_id": self.id
                })
                
                if verification_doc:
                    # Find the updated server in the servers array
                    for server in verification_doc.get("servers", []):
                        if server.get("server_id") == self.id:
                            # Verify each updated field
                            for key, value in update_data.items():
                                actual_value = server.get(key)
                                logger.info(f"Verification - Field '{key}': expected={value}, actual={actual_value}")
                                if actual_value != value:
                                    logger.warning(f"Field '{key}' was not updated correctly. Expected: {value}, Got: {actual_value}")
                            break
                
                return True
            else:
                # If no document was matched, try the fallback method
                logger.warning(f"Initial update failed for server {self.id}. Trying fallback update method.")
                
                # Retrieve the guild document to confirm it exists
                guild_doc = await self.db.guilds.find_one({"guild_id": int_guild_id})
                if not guild_doc:
                    logger.error(f"Guild {self.guild_id} not found in MongoDB")
                    return False
                
                # Search for the server in the guild document
                server_exists = False
                server_data = None
                
                for server in guild_doc.get("servers", []):
                    s_id = server.get("server_id")
                    logger.info(f"Checking server in DB: {s_id} (type: {type(s_id)}) against {self.id} (type: {type(self.id)})")
                    
                    # Compare server IDs (including type conversion if needed)
                    if str(s_id) == str(self.id):
                        server_exists = True
                        server_data = server
                        logger.info(f"Found server with ID: {s_id} (type: {type(s_id)})")
                        break
                
                if server_exists and server_data:
                    # Fallback method: Replace the entire server document
                    logger.info(f"Using fallback update method for server {self.id}")
                    
                    # Create an updated copy of the server data
                    updated_server = server_data.copy()
                    for key, value in update_data.items():
                        updated_server[key] = value
                    
                    try:
                        # First, remove the old server document
                        pull_result = await self.db.guilds.update_one(
                            {"guild_id": int_guild_id},
                            {"$pull": {"servers": {"server_id": self.id}}}
                        )
                        
                        logger.info(f"Pull result: matched={pull_result.matched_count}, modified={pull_result.modified_count}")
                        
                        # Then add the updated server document
                        push_result = await self.db.guilds.update_one(
                            {"guild_id": int_guild_id},
                            {"$push": {"servers": updated_server}}
                        )
                        
                        logger.info(f"Push result: matched={push_result.matched_count}, modified={push_result.modified_count}")
                        
                        if push_result.modified_count > 0:
                            # Update local data
                            for key, value in update_data.items():
                                setattr(self, key, value)
                                self.data[key] = value
                            
                            # Verify the update was successful
                            verification = await self.db.guilds.find_one({
                                "guild_id": int_guild_id,
                                "servers.server_id": self.id
                            })
                            
                            if verification:
                                logger.info(f"Fallback update successful for server {self.id}")
                                return True
                    except Exception as alt_e:
                        logger.error(f"Error in fallback update method: {alt_e}", exc_info=True)
                else:
                    logger.error(f"Server {self.id} not found in guild document")
            
            # If we reach this point, the update failed
            logger.error(f"Failed to update server {self.id} in guild {self.guild_id}")
            return False
            
        except Exception as e:
            logger.error(f"MongoDB update error: {e}", exc_info=True)
            return False
    
    async def delete(self) -> bool:
        """Delete the server"""
        # Create a query that matches both string and integer types for guild ID
        guild_query = {
            "$or": [
                {"guild_id": self.guild_id},  # Original type
                {"guild_id": str(self.guild_id)},  # String type
                {"guild_id": int(self.guild_id) if str(self.guild_id).isdigit() else self.guild_id}  # Int type if possible
            ]
        }
        
        # Create a query that matches both string and integer server IDs
        server_query = {
            "$or": [
                {"servers.server_id": self.id},  # Original type
                {"servers.server_id": str(self.id)},  # String type
                {"servers.server_id": int(self.id) if str(self.id).isdigit() else self.id}  # Int type if possible
            ]
        }
        
        # Remove server from guild with a robust type-flexible query
        result = await self.db.guilds.update_one(
            {"$and": [guild_query, server_query]},
            {"$pull": {"servers": {"server_id": self.id}}}
        )
        
        # Delete all associated data
        if result.modified_count > 0:
            # Delete kills
            await self.db.kills.delete_many({"server_id": self.id})
            
            # Delete events
            await self.db.events.delete_many({"server_id": self.id})
            
            # Delete connections
            await self.db.connections.delete_many({"server_id": self.id})
            
            # Keep players for historical purposes, but mark as inactive
            await self.db.players.update_many(
                {"server_id": self.id},
                {"$set": {"active": False}}
            )
            
            return True
        
        return False
    
    async def update_last_csv_line(self, line_number: int) -> bool:
        """Update the last processed CSV line"""
        return await self.update({"last_csv_line": line_number})
    
    async def update_last_log_line(self, line_number: int) -> bool:
        """Update the last processed log line"""
        return await self.update({"last_log_line": line_number})
    
    async def get_players(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all players for this server"""
        query = {"server_id": self.id}
        if active_only:
            query["active"] = True
        
        cursor = self.db.players.find(query)
        players = await cursor.to_list(length=None)
        
        return players
    
    async def get_player_count(self) -> int:
        """Get the count of players for this server"""
        return await self.db.players.count_documents({"server_id": self.id})
    
    async def get_online_player_count(self) -> tuple:
        """Get the count of online players and their info"""
        # Get the last server restart event
        last_restart = await self.db.events.find_one(
            {
                "server_id": self.id,
                "event_type": "server_restart"
            },
            sort=[("timestamp", -1)]
        )
        
        restart_time = last_restart["timestamp"] if last_restart else datetime(1970, 1, 1)
        
        # Get all connection events since last restart
        pipeline = [
            {
                "$match": {
                    "server_id": self.id,
                    "timestamp": {"$gt": restart_time}
                }
            },
            {
                "$sort": {"timestamp": 1}
            }
        ]
        
        cursor = self.db.connections.aggregate(pipeline)
        connections = await cursor.to_list(length=None)
        
        # Track online players
        online_players = {}
        
        for conn in connections:
            player_id = conn["player_id"]
            
            if conn["action"] == "connected":
                online_players[player_id] = conn["player_name"]
            elif conn["action"] == "disconnected" and player_id in online_players:
                del online_players[player_id]
        
        return len(online_players), online_players
    
    async def get_kill_count(self) -> int:
        """Get the count of kills for this server"""
        return await self.db.kills.count_documents({
            "server_id": self.id,
            "is_suicide": False
        })
    
    async def get_suicide_count(self) -> int:
        """Get the count of suicides for this server"""
        return await self.db.kills.count_documents({
            "server_id": self.id,
            "is_suicide": True
        })
    
    async def get_event_count(self) -> int:
        """Get the count of events for this server"""
        return await self.db.events.count_documents({"server_id": self.id})
    
    async def get_top_weapons(self, limit: int = 5, include_details: bool = False) -> List[Dict[str, Any]]:
        """Get the top weapons by kill count
        
        Args:
            limit: Maximum number of weapons to return
            include_details: Whether to include detailed weapon information
            
        Returns:
            List of weapon dictionaries with kill counts and optionally details
        """
        pipeline = [
            {
                "$match": {
                    "server_id": self.id,
                    "is_suicide": False
                }
            },
            {
                "$group": {
                    "_id": "$weapon",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": limit
            }
        ]
        
        cursor = self.db.kills.aggregate(pipeline)
        weapons = await cursor.to_list(length=None)
        
        if not include_details:
            return [{"weapon": w["_id"], "kills": w["count"]} for w in weapons]
            
        # Import the weapon details function
        from utils.weapon_stats import get_weapon_details
        
        # Include detailed weapon information
        result = []
        for w in weapons:
            weapon_name = w["_id"]
            weapon_data = {
                "weapon": weapon_name,
                "kills": w["count"]
            }
            
            # Add detailed information if available
            details = get_weapon_details(weapon_name)
            if details:
                weapon_data["category"] = details.get("category")
                weapon_data["type"] = details.get("type")
                weapon_data["ammo"] = details.get("ammo")
                weapon_data["description"] = details.get("description")
                
            result.append(weapon_data)
            
        return result
    
    async def get_top_killers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the top killers by kill count"""
        pipeline = [
            {
                "$match": {
                    "server_id": self.id,
                    "is_suicide": False
                }
            },
            {
                "$group": {
                    "_id": "$killer_id",
                    "name": {"$first": "$killer_name"},
                    "kills": {"$sum": 1}
                }
            },
            {
                "$sort": {"kills": -1}
            },
            {
                "$limit": limit
            }
        ]
        
        cursor = self.db.kills.aggregate(pipeline)
        killers = await cursor.to_list(length=None)
        
        # Return only player names, not IDs, for security
        return [{"player_name": k["name"], "kills": k["kills"]} for k in killers]
    
    async def get_server_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats for this server"""
        # Get basic counts
        kill_count = await self.get_kill_count()
        suicide_count = await self.get_suicide_count()
        player_count = await self.get_player_count()
        online_count, _ = await self.get_online_player_count()
        
        # Get top weapons with detailed information
        top_weapons = await self.get_top_weapons(include_details=True)
        
        # Get top killers
        top_killers = await self.get_top_killers()
        
        # Get recent events
        recent_events_cursor = self.db.events.find(
            {"server_id": self.id},
            sort=[("timestamp", -1)],
            limit=5
        )
        raw_events = await recent_events_cursor.to_list(length=None)
        
        # Filter out sensitive information like player IDs
        recent_events = []
        for event in raw_events:
            # Create a safe copy without IDs
            safe_event = {
                "event_type": event.get("event_type"),
                "timestamp": event.get("timestamp"),
                "details": event.get("details", [])
            }
            # If player names are present, include them without IDs
            if "player_name" in event:
                safe_event["player_name"] = event["player_name"]
            # Add the safe event to our list
            recent_events.append(safe_event)
        
        # Compile stats
        stats = {
            "server_id": self.id,
            "server_name": self.name,
            "total_kills": kill_count,
            "total_suicides": suicide_count,
            "total_deaths": kill_count + suicide_count,
            "total_players": player_count,
            "online_players": online_count,
            "top_weapons": top_weapons,
            "top_killers": top_killers,
            "recent_events": recent_events
        }
        
        return stats
    
    async def update_event_notifications(self, settings: Dict[str, bool]) -> bool:
        """Update event notification settings
        
        Args:
            settings: Dictionary of event type to boolean indicating if notifications should be sent
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Update the event_notifications field
        update_data = {}
        
        # Only update the specified settings and keep existing ones
        updated_settings = self.event_notifications.copy()
        updated_settings.update(settings)
        
        update_data["event_notifications"] = updated_settings
        
        return await self.update(update_data)
    
    async def update_connection_notifications(self, settings: Dict[str, bool]) -> bool:
        """Update connection notification settings
        
        Args:
            settings: Dictionary of connection type to boolean indicating if notifications should be sent
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Update the connection_notifications field
        update_data = {}
        
        # Only update the specified settings and keep existing ones
        updated_settings = self.connection_notifications.copy()
        updated_settings.update(settings)
        
        update_data["connection_notifications"] = updated_settings
        
        return await self.update(update_data)
    
    async def update_suicide_notifications(self, settings: Dict[str, bool]) -> bool:
        """Update suicide notification settings
        
        Args:
            settings: Dictionary of suicide type to boolean indicating if notifications should be sent
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Update the suicide_notifications field
        update_data = {}
        
        # Only update the specified settings and keep existing ones
        updated_settings = self.suicide_notifications.copy()
        updated_settings.update(settings)
        
        update_data["suicide_notifications"] = updated_settings
        
        return await self.update(update_data)
