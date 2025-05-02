"""
Event model for database operations
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class Event:
    """Event model for database operations"""
    
    def __init__(self, db, event_data):
        """Initialize event model"""
        self.db = db
        self.data = event_data
        self.id = event_data.get("_id")
        self.server_id = event_data.get("server_id")
        self.event_type = event_data.get("event_type")
        self.details = event_data.get("details", [])
        self.timestamp = event_data.get("timestamp")
        self.created_at = event_data.get("created_at")
    
    @classmethod
    async def create(cls, db, event_data: Dict[str, Any]) -> 'Event':
        """Create a new event"""
        # Required fields
        required_fields = ["server_id", "event_type", "timestamp"]
        for field in required_fields:
            if field not in event_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Set created timestamp
        event_data["created_at"] = datetime.utcnow().isoformat()
        
        # Insert event
        result = await db.events.insert_one(event_data)
        event_data["_id"] = result.inserted_id
        
        return cls(db, event_data)
    
    @classmethod
    async def get_by_server(cls, db, server_id: str, limit: int = 10, 
                           event_type: Optional[str] = None) -> List['Event']:
        """Get events for a server"""
        # Build query
        query = {"server_id": server_id}
        if event_type:
            query["event_type"] = event_type
        
        # Find events
        cursor = db.events.find(
            query,
            sort=[("timestamp", -1)],
            limit=limit
        )
        
        events = await cursor.to_list(length=None)
        
        return [cls(db, event_data) for event_data in events]
    
    @classmethod
    async def get_latest_by_type(cls, db, server_id: str, event_type: str) -> Optional['Event']:
        """Get the latest event of a specific type for a server"""
        # Find latest event
        event_data = await db.events.find_one(
            {
                "server_id": server_id,
                "event_type": event_type
            },
            sort=[("timestamp", -1)]
        )
        
        if not event_data:
            return None
        
        return cls(db, event_data)
    
    @classmethod
    async def count_by_type(cls, db, server_id: str, event_type: str) -> int:
        """Count events of a specific type for a server"""
        return await db.events.count_documents({
            "server_id": server_id,
            "event_type": event_type
        })
    
    @classmethod
    async def get_stats_by_type(cls, db, server_id: str) -> Dict[str, int]:
        """Get counts of events by type for a server"""
        pipeline = [
            {
                "$match": {"server_id": server_id}
            },
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        cursor = db.events.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        # Convert to dictionary
        stats = {}
        for result in results:
            stats[result["_id"]] = result["count"]
        
        return stats

class Connection:
    """Connection model for database operations"""
    
    def __init__(self, db, connection_data):
        """Initialize connection model"""
        self.db = db
        self.data = connection_data
        self.id = connection_data.get("_id")
        self.server_id = connection_data.get("server_id")
        self.player_id = connection_data.get("player_id")
        self.player_name = connection_data.get("player_name")
        self.action = connection_data.get("action")  # "connected" or "disconnected"
        self.platform = connection_data.get("platform")  # "PC" or "Console"
        self.timestamp = connection_data.get("timestamp")
        self.created_at = connection_data.get("created_at")
    
    @classmethod
    async def create(cls, db, connection_data: Dict[str, Any]) -> 'Connection':
        """Create a new connection event"""
        # Required fields
        required_fields = ["server_id", "player_id", "player_name", "action", "timestamp"]
        for field in required_fields:
            if field not in connection_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Set created timestamp
        connection_data["created_at"] = datetime.utcnow().isoformat()
        
        # Insert connection
        result = await db.connections.insert_one(connection_data)
        connection_data["_id"] = result.inserted_id
        
        # Create or update player
        from models.player import Player
        player_data = {
            "player_id": connection_data["player_id"],
            "player_name": connection_data["player_name"],
            "server_id": connection_data["server_id"],
            "active": True
        }
        await Player.create_or_update(db, player_data)
        
        return cls(db, connection_data)
    
    @classmethod
    async def get_by_player(cls, db, server_id: str, player_id: str, 
                           limit: int = 10) -> List['Connection']:
        """Get connection events for a player"""
        # Find connections
        cursor = db.connections.find(
            {
                "server_id": server_id,
                "player_id": player_id
            },
            sort=[("timestamp", -1)],
            limit=limit
        )
        
        connections = await cursor.to_list(length=None)
        
        return [cls(db, conn_data) for conn_data in connections]
    
    @classmethod
    async def get_latest_connections(cls, db, server_id: str, 
                                    limit: int = 10) -> List['Connection']:
        """Get latest connection events for a server"""
        # Find latest connections
        cursor = db.connections.find(
            {"server_id": server_id},
            sort=[("timestamp", -1)],
            limit=limit
        )
        
        connections = await cursor.to_list(length=None)
        
        return [cls(db, conn_data) for conn_data in connections]
    
    @classmethod
    async def get_online_players(cls, db, server_id: str) -> tuple:
        """Get currently online players"""
        # Get the last server restart event
        from models.event import Event
        restart_event = await Event.get_latest_by_type(db, server_id, "server_restart")
        
        restart_time = restart_event.timestamp if restart_event else datetime(1970, 1, 1)
        
        # Get all connection events since last restart
        pipeline = [
            {
                "$match": {
                    "server_id": server_id,
                    "timestamp": {"$gt": restart_time}
                }
            },
            {
                "$sort": {"timestamp": 1}
            }
        ]
        
        cursor = db.connections.aggregate(pipeline)
        connections = await cursor.to_list(length=None)
        
        # Track online players
        online_players = {}
        
        for conn in connections:
            player_id = conn["player_id"]
            
            if conn["action"] == "connected":
                online_players[player_id] = {
                    "name": conn["player_name"],
                    "platform": conn.get("platform", "Unknown"),
                    "connected_at": conn["timestamp"]
                }
            elif conn["action"] == "disconnected" and player_id in online_players:
                del online_players[player_id]
        
        return len(online_players), online_players
