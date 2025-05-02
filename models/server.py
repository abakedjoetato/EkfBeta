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
    
    @classmethod
    async def get_by_id(cls, db, server_id: str, guild_id: int = None) -> Optional['Server']:
        """Get a server by ID"""
        # Build query
        query = {"server_id": server_id}
        if guild_id:
            query["guild_id"] = guild_id
        
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
            {"guild_id": server_data["guild_id"]},
            {"$push": {"servers": server_data}}
        )
        
        return cls(db, server_data)
    
    async def update(self, update_data: Dict[str, Any]) -> bool:
        """Update server data"""
        # Set updated timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update specific fields in the server document within the guild
        result = await self.db.guilds.update_one(
            {
                "guild_id": self.guild_id,
                "servers.server_id": self.id
            },
            {"$set": {f"servers.$.{key}": value for key, value in update_data.items()}}
        )
        
        # Update local data
        if result.modified_count > 0:
            for key, value in update_data.items():
                setattr(self, key, value)
                self.data[key] = value
            return True
        
        return False
    
    async def delete(self) -> bool:
        """Delete the server"""
        # Remove server from guild
        result = await self.db.guilds.update_one(
            {"guild_id": self.guild_id},
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
    
    async def get_top_weapons(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the top weapons by kill count"""
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
        
        return [{"weapon": w["_id"], "kills": w["count"]} for w in weapons]
    
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
        
        return [{"player_id": k["_id"], "player_name": k["name"], "kills": k["kills"]} for k in killers]
    
    async def get_server_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats for this server"""
        # Get basic counts
        kill_count = await self.get_kill_count()
        suicide_count = await self.get_suicide_count()
        player_count = await self.get_player_count()
        online_count, _ = await self.get_online_player_count()
        
        # Get top weapons
        top_weapons = await self.get_top_weapons()
        
        # Get top killers
        top_killers = await self.get_top_killers()
        
        # Get recent events
        recent_events_cursor = self.db.events.find(
            {"server_id": self.id},
            sort=[("timestamp", -1)],
            limit=5
        )
        recent_events = await recent_events_cursor.to_list(length=None)
        
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
