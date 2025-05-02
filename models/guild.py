"""
Guild model for database operations
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from config import PREMIUM_TIERS

logger = logging.getLogger(__name__)

class Guild:
    """Guild model for database operations"""
    
    def __init__(self, db, guild_data):
        """Initialize guild model"""
        self.db = db
        self.data = guild_data
        self.id = guild_data.get("guild_id")
        self.name = guild_data.get("name")
        self.premium_tier = guild_data.get("premium_tier", 0)
        self.admin_role_id = guild_data.get("admin_role_id")
        self.servers = guild_data.get("servers", [])
        self.joined_at = guild_data.get("joined_at")
        self.updated_at = guild_data.get("updated_at")
    
    @classmethod
    async def get_by_id(cls, db, guild_id: int) -> Optional['Guild']:
        """Get a guild by ID"""
        guild_data = await db.guilds.find_one({"guild_id": guild_id})
        
        if not guild_data:
            return None
        
        return cls(db, guild_data)
    
    @classmethod
    async def create(cls, db, guild_id: int, name: str) -> 'Guild':
        """Create a new guild"""
        # Create guild data
        guild_data = {
            "guild_id": guild_id,
            "name": name,
            "premium_tier": 0,
            "servers": [],
            "joined_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Insert guild
        await db.guilds.insert_one(guild_data)
        
        return cls(db, guild_data)
    
    async def update(self, update_data: Dict[str, Any]) -> bool:
        """Update guild data"""
        # Set updated timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update guild
        result = await self.db.guilds.update_one(
            {"guild_id": self.id},
            {"$set": update_data}
        )
        
        # Update local data
        if result.modified_count > 0:
            for key, value in update_data.items():
                setattr(self, key, value)
                self.data[key] = value
            return True
        
        return False
    
    async def delete(self) -> bool:
        """Delete the guild"""
        # Delete guild
        result = await self.db.guilds.delete_one({"guild_id": self.id})
        
        return result.deleted_count > 0
    
    async def add_server(self, server_data: Dict[str, Any]) -> bool:
        """Add a server to the guild"""
        # Check if server already exists
        for server in self.servers:
            if server.get("server_id") == server_data.get("server_id"):
                logger.warning(f"Server with ID {server_data.get('server_id')} already exists in guild {self.id}")
                return False
        
        # Check premium tier limits
        max_servers = PREMIUM_TIERS.get(self.premium_tier, {}).get("max_servers", 1)
        if len(self.servers) >= max_servers:
            logger.warning(f"Guild {self.id} has reached the maximum number of servers for tier {self.premium_tier}")
            return False
        
        # Set timestamps
        server_data["created_at"] = datetime.utcnow().isoformat()
        server_data["updated_at"] = server_data["created_at"]
        
        # Set default values
        server_data.setdefault("last_csv_line", 0)
        server_data.setdefault("last_log_line", 0)
        
        # Add server to guild
        result = await self.db.guilds.update_one(
            {"guild_id": self.id},
            {"$push": {"servers": server_data}}
        )
        
        # Update local data
        if result.modified_count > 0:
            self.servers.append(server_data)
            self.data["servers"] = self.servers
            return True
        
        return False
    
    async def remove_server(self, server_id: str) -> bool:
        """Remove a server from the guild"""
        # Check if server exists
        server_exists = False
        for server in self.servers:
            if server.get("server_id") == server_id:
                server_exists = True
                break
        
        if not server_exists:
            logger.warning(f"Server with ID {server_id} does not exist in guild {self.id}")
            return False
        
        # Remove server from guild
        result = await self.db.guilds.update_one(
            {"guild_id": self.id},
            {"$pull": {"servers": {"server_id": server_id}}}
        )
        
        # Update local data
        if result.modified_count > 0:
            self.servers = [s for s in self.servers if s.get("server_id") != server_id]
            self.data["servers"] = self.servers
            
            # Delete all associated data
            # Delete kills
            await self.db.kills.delete_many({"server_id": server_id})
            
            # Delete events
            await self.db.events.delete_many({"server_id": server_id})
            
            # Delete connections
            await self.db.connections.delete_many({"server_id": server_id})
            
            # Keep players for historical purposes, but mark as inactive
            await self.db.players.update_many(
                {"server_id": server_id},
                {"$set": {"active": False}}
            )
            
            return True
        
        return False
    
    async def update_server(self, server_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a server in the guild"""
        # Set updated timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Update server
        result = await self.db.guilds.update_one(
            {
                "guild_id": self.id,
                "servers.server_id": server_id
            },
            {"$set": {f"servers.$.{key}": value for key, value in update_data.items()}}
        )
        
        # Update local data
        if result.modified_count > 0:
            for i, server in enumerate(self.servers):
                if server.get("server_id") == server_id:
                    for key, value in update_data.items():
                        self.servers[i][key] = value
            self.data["servers"] = self.servers
            return True
        
        return False
    
    async def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get a server from the guild"""
        for server in self.servers:
            if server.get("server_id") == server_id:
                return server
        return None
    
    async def set_premium_tier(self, tier: int) -> bool:
        """Set the premium tier for the guild"""
        if tier not in PREMIUM_TIERS:
            logger.error(f"Invalid premium tier: {tier}")
            return False
        
        return await self.update({"premium_tier": tier})
    
    async def set_admin_role(self, role_id: int) -> bool:
        """Set the admin role for the guild"""
        return await self.update({"admin_role_id": role_id})
    
    def check_feature_access(self, feature: str) -> bool:
        """Check if a feature is available for this guild's premium tier"""
        features = PREMIUM_TIERS.get(self.premium_tier, {}).get("features", [])
        return feature in features
    
    def get_available_features(self) -> List[str]:
        """Get all available features for this guild's premium tier"""
        return PREMIUM_TIERS.get(self.premium_tier, {}).get("features", [])
    
    def get_max_servers(self) -> int:
        """Get the maximum number of servers for this guild's premium tier"""
        return PREMIUM_TIERS.get(self.premium_tier, {}).get("max_servers", 1)
