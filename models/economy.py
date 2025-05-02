"""
Economy model for currency and gambling operations
"""
from typing import Dict, List, Any, Optional
from datetime import datetime

class Economy:
    """Economy model for currency and transaction operations"""
    
    def __init__(self, db, player_data):
        """Initialize economy model"""
        self.db = db
        self.player_id = player_data.get("player_id")
        self.server_id = player_data.get("server_id")
        self.currency = player_data.get("currency", 0)
        self.lifetime_earnings = player_data.get("lifetime_earnings", 0)
        self.last_daily = player_data.get("last_daily")
        self.transactions = player_data.get("transactions", [])
        self.gambling_stats = player_data.get("gambling_stats", {
            "blackjack": {"wins": 0, "losses": 0, "earnings": 0},
            "slots": {"wins": 0, "losses": 0, "earnings": 0}
        })
    
    @classmethod
    async def get_by_player(cls, db, player_id: str, server_id: str) -> Optional['Economy']:
        """Get economy data for a player"""
        player_data = await db.players.find_one({"player_id": player_id, "server_id": server_id})
        if not player_data:
            return None
        return cls(db, player_data)
    
    @classmethod
    async def create_or_update(cls, db, player_id: str, server_id: str) -> 'Economy':
        """Create or update economy data for a player"""
        player_data = await db.players.find_one({"player_id": player_id, "server_id": server_id})
        
        if not player_data:
            # Create new player record with economy data
            player_data = {
                "player_id": player_id,
                "server_id": server_id,
                "currency": 0,
                "lifetime_earnings": 0,
                "transactions": [],
                "gambling_stats": {
                    "blackjack": {"wins": 0, "losses": 0, "earnings": 0},
                    "slots": {"wins": 0, "losses": 0, "earnings": 0}
                }
            }
            await db.players.insert_one(player_data)
        
        return cls(db, player_data)
    
    async def add_currency(self, amount: int, source: str, details: Dict[str, Any] = None) -> int:
        """Add currency to player account and record transaction"""
        if amount <= 0:
            return self.currency
        
        # Update currency and lifetime earnings
        new_balance = self.currency + amount
        new_lifetime = self.lifetime_earnings + amount
        
        # Record transaction
        transaction = {
            "timestamp": datetime.utcnow(),
            "type": "credit",
            "amount": amount,
            "source": source,
            "balance": new_balance,
            "details": details or {}
        }
        
        # Update database
        result = await self.db.players.update_one(
            {"player_id": self.player_id, "server_id": self.server_id},
            {"$set": {
                "currency": new_balance,
                "lifetime_earnings": new_lifetime
            },
            "$push": {"transactions": transaction}}
        )
        
        if result.modified_count > 0:
            self.currency = new_balance
            self.lifetime_earnings = new_lifetime
            self.transactions.append(transaction)
        
        return self.currency
    
    async def remove_currency(self, amount: int, reason: str, details: Dict[str, Any] = None) -> bool:
        """Remove currency from player account and record transaction"""
        if amount <= 0 or amount > self.currency:
            return False
        
        # Update currency
        new_balance = self.currency - amount
        
        # Record transaction
        transaction = {
            "timestamp": datetime.utcnow(),
            "type": "debit",
            "amount": amount,
            "reason": reason,
            "balance": new_balance,
            "details": details or {}
        }
        
        # Update database
        result = await self.db.players.update_one(
            {"player_id": self.player_id, "server_id": self.server_id},
            {"$set": {"currency": new_balance},
            "$push": {"transactions": transaction}}
        )
        
        if result.modified_count > 0:
            self.currency = new_balance
            self.transactions.append(transaction)
            return True
        
        return False
    
    async def get_balance(self) -> int:
        """Get current balance"""
        return self.currency
    
    async def get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transactions"""
        if not self.transactions:
            return []
        
        sorted_transactions = sorted(
            self.transactions, 
            key=lambda x: x.get("timestamp", datetime.min), 
            reverse=True
        )
        
        return sorted_transactions[:limit]
    
    async def update_gambling_stats(self, game: str, won: bool, amount: int) -> bool:
        """Update gambling statistics for a player"""
        if game not in ["blackjack", "slots"]:
            return False
        
        # Prepare update object
        win_key = f"gambling_stats.{game}.wins"
        loss_key = f"gambling_stats.{game}.losses"
        earnings_key = f"gambling_stats.{game}.earnings"
        
        update = {}
        
        if won:
            update[win_key] = self.gambling_stats[game]["wins"] + 1
            update[earnings_key] = self.gambling_stats[game]["earnings"] + amount
        else:
            update[loss_key] = self.gambling_stats[game]["losses"] + 1
            update[earnings_key] = self.gambling_stats[game]["earnings"] - amount
        
        # Update database
        result = await self.db.players.update_one(
            {"player_id": self.player_id, "server_id": self.server_id},
            {"$set": update}
        )
        
        if result.modified_count > 0:
            if won:
                self.gambling_stats[game]["wins"] += 1
                self.gambling_stats[game]["earnings"] += amount
            else:
                self.gambling_stats[game]["losses"] += 1
                self.gambling_stats[game]["earnings"] -= amount
            return True
        
        return False
    
    async def get_gambling_stats(self) -> Dict[str, Any]:
        """Get gambling statistics for player"""
        return self.gambling_stats
    
    @classmethod
    async def get_richest_players(cls, db, server_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the richest players on a server"""
        cursor = db.players.find(
            {"server_id": server_id, "currency": {"$gt": 0}},
            {"player_id": 1, "player_name": 1, "currency": 1, "lifetime_earnings": 1}
        ).sort("currency", -1).limit(limit)
        
        return await cursor.to_list(length=None)
    
    async def claim_daily(self, amount: int = 100) -> (bool, str):
        """Claim daily reward"""
        now = datetime.utcnow()
        
        # Check if player already claimed today
        if self.last_daily:
            last_claim = self.last_daily
            if isinstance(last_claim, str):
                try:
                    last_claim = datetime.fromisoformat(last_claim.replace('Z', '+00:00'))
                except ValueError:
                    last_claim = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            time_diff = now - last_claim
            if time_diff.days < 1:
                hours_left = 24 - (time_diff.seconds // 3600)
                return False, f"You can claim your daily reward in {hours_left} hours"
        
        # Update last claim and add currency
        result = await self.db.players.update_one(
            {"player_id": self.player_id, "server_id": self.server_id},
            {"$set": {"last_daily": now}}
        )
        
        if result.modified_count > 0:
            self.last_daily = now
            await self.add_currency(amount, "daily_reward")
            return True, f"You claimed your daily reward of {amount} credits!"
        
        return False, "Failed to claim daily reward. Please try again."
