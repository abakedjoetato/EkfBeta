"""
Player model for database operations
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class Player:
    """Player model for database operations"""
    
    def __init__(self, db, player_data):
        """Initialize player model"""
        self.db = db
        self.data = player_data
        self.id = player_data.get("player_id")
        self.name = player_data.get("player_name")
        self.server_id = player_data.get("server_id")
        self.kills = player_data.get("kills", 0)
        self.deaths = player_data.get("deaths", 0)
        self.suicides = player_data.get("suicides", 0)
        self.weapons = player_data.get("weapons", {})
        self.victims = player_data.get("victims", {})
        self.killers = player_data.get("killers", {})
        self.longest_shot = player_data.get("longest_shot", 0)
        self.highest_killstreak = player_data.get("highest_killstreak", 0)
        self.highest_deathstreak = player_data.get("highest_deathstreak", 0)
        self.current_streak = player_data.get("current_streak", 0)
        self.active = player_data.get("active", True)
        self.first_seen = player_data.get("first_seen")
        self.last_seen = player_data.get("last_seen")
        self.updated_at = player_data.get("updated_at")
    
    @classmethod
    async def get_by_id(cls, db, player_id: str, server_id: str) -> Optional['Player']:
        """Get a player by ID"""
        player_data = await db.players.find_one({
            "player_id": player_id,
            "server_id": server_id
        })
        
        if not player_data:
            return None
        
        return cls(db, player_data)
    
    @classmethod
    async def get_by_name(cls, db, player_name: str, server_id: str) -> List['Player']:
        """Get players by name (case-insensitive)"""
        cursor = db.players.find({
            "player_name": {"$regex": f"^{player_name}$", "$options": "i"},
            "server_id": server_id,
            "active": True
        })
        
        players = await cursor.to_list(length=None)
        
        return [cls(db, player_data) for player_data in players]
    
    @classmethod
    async def create_or_update(cls, db, player_data: Dict[str, Any]) -> 'Player':
        """Create or update a player"""
        # Required fields
        required_fields = ["player_id", "player_name", "server_id"]
        for field in required_fields:
            if field not in player_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if player exists
        player_id = player_data["player_id"]
        server_id = player_data["server_id"]
        
        existing_player = await cls.get_by_id(db, player_id, server_id)
        
        if existing_player:
            # Update player
            await existing_player.update(player_data)
            return existing_player
        else:
            # Create new player
            # Set timestamps
            now = datetime.utcnow().isoformat()
            player_data.setdefault("first_seen", now)
            player_data.setdefault("last_seen", now)
            player_data.setdefault("updated_at", now)
            
            # Set default values
            player_data.setdefault("kills", 0)
            player_data.setdefault("deaths", 0)
            player_data.setdefault("suicides", 0)
            player_data.setdefault("weapons", {})
            player_data.setdefault("victims", {})
            player_data.setdefault("killers", {})
            player_data.setdefault("longest_shot", 0)
            player_data.setdefault("highest_killstreak", 0)
            player_data.setdefault("highest_deathstreak", 0)
            player_data.setdefault("current_streak", 0)
            player_data.setdefault("active", True)
            
            # Insert player
            await db.players.insert_one(player_data)
            
            return cls(db, player_data)
    
    async def update(self, update_data: Dict[str, Any]) -> bool:
        """Update player data"""
        # Set updated timestamp
        now = datetime.utcnow().isoformat()
        update_data["updated_at"] = now
        update_data.setdefault("last_seen", now)
        
        # Update player
        result = await self.db.players.update_one(
            {
                "player_id": self.id,
                "server_id": self.server_id
            },
            {"$set": update_data}
        )
        
        # Update local data
        if result.modified_count > 0:
            for key, value in update_data.items():
                setattr(self, key, value)
                self.data[key] = value
            return True
        
        return False
    
    async def record_kill(self, victim_id: str, victim_name: str, weapon: str, distance: int = 0) -> bool:
        """Record a kill for this player"""
        # Update kills count
        update_data = {
            "kills": self.kills + 1,
            "last_seen": datetime.utcnow().isoformat()
        }
        
        # Update weapons dictionary
        weapons = self.weapons.copy()
        weapons[weapon] = weapons.get(weapon, 0) + 1
        update_data["weapons"] = weapons
        
        # Update victims dictionary
        victims = self.victims.copy()
        victims[victim_id] = {
            "name": victim_name,
            "count": victims.get(victim_id, {}).get("count", 0) + 1
        }
        update_data["victims"] = victims
        
        # Update streak
        current_streak = self.current_streak
        if current_streak < 0:
            # Was on a death streak, now reset
            current_streak = 1
        else:
            # Continue or start kill streak
            current_streak += 1
        
        update_data["current_streak"] = current_streak
        
        # Update highest kill streak if needed
        if current_streak > self.highest_killstreak:
            update_data["highest_killstreak"] = current_streak
        
        # Update longest shot if needed
        if distance > self.longest_shot:
            update_data["longest_shot"] = distance
        
        # Update player
        return await self.update(update_data)
    
    async def record_death(self, killer_id: str, killer_name: str) -> bool:
        """Record a death for this player"""
        # Update deaths count
        update_data = {
            "deaths": self.deaths + 1,
            "last_seen": datetime.utcnow().isoformat()
        }
        
        # Update killers dictionary
        killers = self.killers.copy()
        killers[killer_id] = {
            "name": killer_name,
            "count": killers.get(killer_id, {}).get("count", 0) + 1
        }
        update_data["killers"] = killers
        
        # Update streak
        current_streak = self.current_streak
        if current_streak > 0:
            # Was on a kill streak, now reset
            current_streak = -1
        else:
            # Continue or start death streak
            current_streak -= 1
        
        update_data["current_streak"] = current_streak
        
        # Update highest death streak if needed
        if abs(current_streak) > self.highest_deathstreak and current_streak < 0:
            update_data["highest_deathstreak"] = abs(current_streak)
        
        # Update player
        return await self.update(update_data)
    
    async def record_suicide(self, suicide_type: str = "other") -> bool:
        """Record a suicide for this player"""
        # Update suicides count and deaths count
        update_data = {
            "suicides": self.suicides + 1,
            "deaths": self.deaths + 1,
            "last_seen": datetime.utcnow().isoformat()
        }
        
        # Update streak (suicides count as deaths for streaks)
        current_streak = self.current_streak
        if current_streak > 0:
            # Was on a kill streak, now reset
            current_streak = -1
        else:
            # Continue or start death streak
            current_streak -= 1
        
        update_data["current_streak"] = current_streak
        
        # Update highest death streak if needed
        if abs(current_streak) > self.highest_deathstreak and current_streak < 0:
            update_data["highest_deathstreak"] = abs(current_streak)
        
        # Update player
        return await self.update(update_data)
    
    async def get_nemesis(self) -> Optional[Dict[str, Any]]:
        """Get the player's nemesis (player who killed them the most)"""
        if not self.killers:
            return None
        
        # Find killer with highest count
        nemesis_id = None
        nemesis_count = 0
        
        for killer_id, data in self.killers.items():
            count = data.get("count", 0)
            if count > nemesis_count:
                nemesis_id = killer_id
                nemesis_count = count
        
        if not nemesis_id:
            return None
        
        # Get nemesis data
        nemesis_data = self.killers[nemesis_id]
        
        return {
            "player_id": nemesis_id,
            "player_name": nemesis_data["name"],
            "kill_count": nemesis_count
        }
    
    async def get_favorite_victim(self) -> Optional[Dict[str, Any]]:
        """Get the player's favorite victim (player they killed the most)"""
        if not self.victims:
            return None
        
        # Find victim with highest count
        victim_id = None
        victim_count = 0
        
        for vid, data in self.victims.items():
            count = data.get("count", 0)
            if count > victim_count:
                victim_id = vid
                victim_count = count
        
        if not victim_id:
            return None
        
        # Get victim data
        victim_data = self.victims[victim_id]
        
        return {
            "player_id": victim_id,
            "player_name": victim_data["name"],
            "kill_count": victim_count
        }
    
    async def get_favorite_weapon(self) -> Optional[Dict[str, Any]]:
        """Get the player's favorite weapon (weapon they used the most)"""
        if not self.weapons:
            return None
        
        # Find weapon with highest count
        weapon_name = None
        weapon_count = 0
        
        for name, count in self.weapons.items():
            if count > weapon_count:
                weapon_name = name
                weapon_count = count
        
        if not weapon_name:
            return None
        
        return {
            "weapon": weapon_name,
            "kill_count": weapon_count
        }
    
    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed stats for this player"""
        # Calculate K/D ratio
        kdr = self.kills / max(self.deaths, 1)
        
        # Get nemesis
        nemesis = await self.get_nemesis()
        
        # Get favorite victim
        favorite_victim = await self.get_favorite_victim()
        
        # Get favorite weapon
        favorite_weapon = await self.get_favorite_weapon()
        
        # Get advanced weapon stats
        from utils.weapon_stats import analyze_player_weapon_stats
        weapon_analysis = analyze_player_weapon_stats(self.weapons)
        
        # Compile stats (exclude player_id from being shown in UI)
        stats = {
            "player_name": self.name,
            "server_id": self.server_id,
            "kills": self.kills,
            "deaths": self.deaths,
            "suicides": self.suicides,
            "kdr": round(kdr, 2),
            "longest_shot": self.longest_shot,
            "highest_killstreak": self.highest_killstreak,
            "highest_deathstreak": self.highest_deathstreak,
            "current_streak": self.current_streak,
            "nemesis": nemesis,
            "favorite_victim": favorite_victim,
            "favorite_weapon": favorite_weapon,
            "weapon_categories": weapon_analysis.get("category_breakdown", {}),
            "most_used_category": weapon_analysis.get("most_used_category"),
            "melee_percentage": weapon_analysis.get("melee_percentage", 0),
            "combat_kills": weapon_analysis.get("combat_kills", 0),
            "weapons": self.weapons,  # Keep all weapon data for detailed stats
            "first_seen": self.first_seen,
            "last_seen": self.last_seen
        }
        
        return stats
    
    @classmethod
    async def get_leaderboard(cls, db, server_id: str, stat: str = "kills", limit: int = 10) -> List[Dict[str, Any]]:
        """Get a leaderboard for a specific stat"""
        valid_stats = ["kills", "deaths", "suicides", "kdr", "longest_shot", 
                        "highest_killstreak", "highest_deathstreak"]
        
        if stat not in valid_stats:
            logger.error(f"Invalid stat for leaderboard: {stat}")
            return []
        
        # Special case for KDR
        if stat == "kdr":
            # Get all active players
            cursor = db.players.find({
                "server_id": server_id,
                "active": True,
                "kills": {"$gt": 0}  # Only include players with kills
            })
            
            players = await cursor.to_list(length=None)
            
            # Calculate KDR for each player
            for player in players:
                player["kdr"] = round(player["kills"] / max(player["deaths"], 1), 2)
            
            # Sort by KDR
            players.sort(key=lambda x: x["kdr"], reverse=True)
            
            # Limit results
            players = players[:limit]
            
            return [{
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "value": p["kdr"]
            } for p in players]
        
        # All other stats
        pipeline = [
            {
                "$match": {
                    "server_id": server_id,
                    "active": True,
                    stat: {"$gt": 0}  # Only include players with non-zero stat
                }
            },
            {
                "$sort": {stat: -1}
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "player_id": 1,
                    "player_name": 1,
                    "value": f"${stat}"
                }
            }
        ]
        
        cursor = db.players.aggregate(pipeline)
        leaderboard = await cursor.to_list(length=None)
        
        return leaderboard
