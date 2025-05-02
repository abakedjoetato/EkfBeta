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
        self.theme = guild_data.get("theme", "default")
    
    @classmethod
    async def get_by_id(cls, db, guild_id: int) -> Optional['Guild']:
        """Get a guild by ID"""
        # Try both string and integer types to ensure consistent lookups
        # since MongoDB treats strings and integers as different types
        query = {
            "$or": [
                {"guild_id": guild_id},  # Try as original type
                {"guild_id": str(guild_id)},  # Try as string
                {"guild_id": int(guild_id) if str(guild_id).isdigit() else guild_id}  # Try as int if possible
            ]
        }
        
        guild_data = await db.guilds.find_one(query)
        
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
        
        # Create a query that matches both string and integer guild IDs
        query = {
            "$or": [
                {"guild_id": self.id},  # Original type
                {"guild_id": str(self.id)},  # String type
                {"guild_id": int(self.id) if str(self.id).isdigit() else self.id}  # Int type if possible
            ]
        }
        
        # Update guild
        result = await self.db.guilds.update_one(
            query,
            {"$set": update_data}
        )
        
        # If no update happened, log details for debugging
        if result.matched_count == 0:
            logger.warning(f"Guild update failed - no match found for guild ID {self.id} (type: {type(self.id).__name__})")
            # Try one more time with direct ID type query
            direct_result = await self.db.guilds.update_one(
                {"guild_id": self.id},
                {"$set": update_data}
            )
            if direct_result.matched_count == 0:
                logger.error(f"Guild update failed with direct ID query for guild ID {self.id}")
            else:
                result = direct_result
        
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
        # Check if server exists, comparing as strings for consistency
        server_exists = False
        for server in self.servers:
            s_id = server.get("server_id")
            if (s_id == server_id or 
                str(s_id) == str(server_id) or
                (isinstance(s_id, int) and server_id.isdigit() and s_id == int(server_id)) or
                (isinstance(s_id, str) and s_id.isdigit() and server_id.isdigit() and int(s_id) == int(server_id))):
                server_exists = True
                break
        
        if not server_exists:
            logger.warning(f"Server with ID {server_id} does not exist in guild {self.id}")
            return False
        
        # Create a query that matches both string and integer types for guild ID
        guild_query = {
            "$or": [
                {"guild_id": self.id},  # Original type
                {"guild_id": str(self.id)},  # String type
                {"guild_id": int(self.id) if str(self.id).isdigit() else self.id}  # Int type if possible
            ]
        }
        
        # Create server ID query that handles both string and integer types
        server_query = {
            "$or": [
                {"servers.server_id": server_id},  # Original format
                {"servers.server_id": str(server_id)},  # String format 
                {"servers.server_id": int(server_id) if server_id.isdigit() else server_id}  # Integer format if possible
            ]
        }
        
        # Remove server from guild using a robust query
        combined_query = {"$and": [guild_query, server_query]}
        logger.info(f"Removing server {server_id} from guild {self.id} with query: {combined_query}")
        
        result = await self.db.guilds.update_one(
            combined_query,
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
            
            # Delete player data completely
            await self.db.players.delete_many({"server_id": server_id})
            
            # Also delete any economy data associated with the server
            await self.db.economy.delete_many({"server_id": server_id})
            
            return True
        
        return False
    
    async def update_server(self, server_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a server in the guild"""
        # Set updated timestamp
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Create a query that matches both string and integer representations of guild ID
        # and handles both string and integer server IDs
        guild_query = {
            "$or": [
                {"guild_id": self.id},
                {"guild_id": str(self.id)},
                {"guild_id": int(self.id) if str(self.id).isdigit() else self.id}
            ]
        }
        
        server_query = {
            "$or": [
                {"servers.server_id": server_id},  # Original
                {"servers.server_id": str(server_id)},  # String type
                {"servers.server_id": int(server_id) if str(server_id).isdigit() else server_id}  # Int type if possible
            ]
        }
        
        # Combine the queries
        query = {
            "$and": [guild_query, server_query]
        }
        
        # First try with the original combined query approach
        result = await self.db.guilds.update_one(
            query,
            {"$set": {f"servers.$.{key}": value for key, value in update_data.items()}}
        )
        
        # If no match, try with direct types
        if result.matched_count == 0:
            logger.warning(f"Server update failed for guild ID {self.id}, server ID {server_id} with combined query")
            
            # Try direct update for both possible server_id formats
            direct_result = await self.db.guilds.update_one(
                {
                    "guild_id": self.id,
                    "servers.server_id": server_id
                },
                {"$set": {f"servers.$.{key}": value for key, value in update_data.items()}}
            )
            
            # If that didn't work and server_id can be an integer, try that format
            if direct_result.matched_count == 0 and server_id.isdigit():
                int_result = await self.db.guilds.update_one(
                    {
                        "guild_id": self.id,
                        "servers.server_id": int(server_id)
                    },
                    {"$set": {f"servers.$.{key}": value for key, value in update_data.items()}}
                )
                if int_result.matched_count > 0:
                    result = int_result
                    logger.info(f"Server update succeeded with integer server ID format")
            else:
                result = direct_result
                if direct_result.matched_count > 0:
                    logger.info(f"Server update succeeded with direct query")
        
        # Update local data if the update succeeded
        if result.modified_count > 0:
            for i, server in enumerate(self.servers):
                if str(server.get("server_id")) == str(server_id):  # Compare as strings for consistency
                    for key, value in update_data.items():
                        self.servers[i][key] = value
            self.data["servers"] = self.servers
            return True
        else:
            logger.error(f"Server update failed for guild ID {self.id}, server ID {server_id}")
        
        return False
    
    async def get_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get a server from the guild"""
        for server in self.servers:
            s_id = server.get("server_id")
            # Compare with multiple type formats to handle string/int discrepancies
            if (s_id == server_id or 
                str(s_id) == str(server_id) or 
                (isinstance(s_id, int) and server_id.isdigit() and s_id == int(server_id)) or
                (isinstance(s_id, str) and s_id.isdigit() and server_id.isdigit() and int(s_id) == int(server_id))):
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
        
    async def set_theme(self, theme_name: str) -> bool:
        """Set the theme for the guild
        
        Args:
            theme_name: The name of the theme to use
            
        Returns:
            bool: True if the theme was set successfully, False otherwise
        """
        from config import EMBED_THEMES
        
        # Validate theme exists
        if theme_name not in EMBED_THEMES and theme_name != "default":
            return False
            
        # Check if guild has custom theme feature (tier 3+)
        if theme_name != "default" and self.premium_tier < 3:
            return False
            
        # Update theme
        return await self.update({"theme": theme_name})
