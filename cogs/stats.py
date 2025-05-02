"""
Statistics commands for player and server stats
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from models.server import Server
from models.player import Player
from models.guild import Guild
from utils.embed_builder import EmbedBuilder
from utils.helpers import paginate_embeds, format_time_ago

logger = logging.getLogger(__name__)


async def server_id_autocomplete(interaction, current):
    """Autocomplete for server IDs"""
    try:
        # Get user's guild ID
        guild_id = interaction.guild_id
        
        # Get cached server data or fetch it
        cog = interaction.client.get_cog("Stats")
        
        # Update cache if needed
        if guild_id not in cog.server_autocomplete_cache or \
           (datetime.now() - cog.server_autocomplete_cache.get(guild_id, {}).get("last_update", datetime.min)).total_seconds() > 300:
            
            # Fetch guild data
            guild_data = await interaction.client.db.guilds.find_one({"guild_id": guild_id})
            
            if guild_data and "servers" in guild_data:
                # Update cache
                cog.server_autocomplete_cache[guild_id] = {
                    "servers": [
                        {
                            "id": server.get("server_id", ""),
                            "name": server.get("server_name", "Unknown Server")
                        }
                        for server in guild_data.get("servers", [])
                    ],
                    "last_update": datetime.now()
                }
        
        # Get servers from cache
        servers = cog.server_autocomplete_cache.get(guild_id, {}).get("servers", [])
        
        # Filter by current input
        filtered_servers = [
            app_commands.Choice(name=f"{server['name']} ({server['id']})", value=server['id'])
            for server in servers
            if current.lower() in server['id'].lower() or current.lower() in server['name'].lower()
        ]
        
        return filtered_servers[:25]
        
    except Exception as e:
        logger.error(f"Error in server autocomplete: {e}", exc_info=True)
        return [app_commands.Choice(name="Error loading servers", value="error")]


async def player_name_autocomplete(interaction, current):
    """Autocomplete for player names"""
    try:
        # Get user's guild ID and the server ID from the command options
        guild_id = interaction.guild_id
        
        # Try to get the server_id from the interaction
        server_id = None
        for option in interaction.data.get("options", []):
            if option.get("name") == "server_id":
                server_id = option.get("value")
                break
            
            # Check in subcommands
            for suboption in option.get("options", []):
                if suboption.get("name") == "server_id":
                    server_id = suboption.get("value")
                    break
        
        if not server_id:
            return [app_commands.Choice(name="Select a server first", value="")]
        
        # Get cached player data or fetch it
        cog = interaction.client.get_cog("Stats")
        cache_key = f"{guild_id}_{server_id}"
        
        # Update cache if needed
        if cache_key not in cog.player_autocomplete_cache or \
           (datetime.now() - cog.player_autocomplete_cache.get(cache_key, {}).get("last_update", datetime.min)).total_seconds() > 300:
            
            # Fetch players for this server
            players_cursor = interaction.client.db.players.find(
                {"server_id": server_id, "active": True},
                {"player_id": 1, "player_name": 1}
            ).limit(1000)  # Limit to prevent huge result sets
            
            players = await players_cursor.to_list(length=1000)
            
            if players:
                # Update cache
                cog.player_autocomplete_cache[cache_key] = {
                    "players": [
                        {
                            "id": player.get("player_id", ""),
                            "name": player.get("player_name", "Unknown Player")
                        }
                        for player in players
                    ],
                    "last_update": datetime.now()
                }
        
        # Get players from cache
        players = cog.player_autocomplete_cache.get(cache_key, {}).get("players", [])
        
        # Filter by current input
        if current:
            filtered_players = [
                app_commands.Choice(name=player['name'], value=player['name'])
                for player in players
                if current.lower() in player['name'].lower()
            ]
        else:
            # Without filtering, take a sample of players
            import random
            sample_size = min(25, len(players))
            sampled_players = random.sample(players, sample_size) if sample_size > 0 else []
            
            filtered_players = [
                app_commands.Choice(name=player['name'], value=player['name'])
                for player in sampled_players
            ]
        
        return filtered_players[:25]
        
    except Exception as e:
        logger.error(f"Error in player autocomplete: {e}", exc_info=True)
        return [app_commands.Choice(name="Error loading players", value="")]


class Stats(commands.Cog):
    """Stats commands for player and server stats"""
    
    def __init__(self, bot):
        self.bot = bot
        self.server_autocomplete_cache = {}
        self.player_autocomplete_cache = {}
    
    @commands.hybrid_group(name="stats", description="Statistics commands")
    @commands.guild_only()
    async def stats(self, ctx):
        """Stats command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @stats.command(name="player", description="View player statistics")
    @app_commands.describe(
        server_id="The server ID to check stats for",
        player_name="The player name to search for"
    )
    @app_commands.autocomplete(
        server_id=server_id_autocomplete,
        player_name=player_name_autocomplete
    )
    async def player_stats(self, ctx, server_id: str, player_name: str):
        """View statistics for a player"""
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to stats feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Player statistics is a premium feature. Please upgrade to access this feature."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the player(s)
            players = await Player.get_by_name(self.bot.db, player_name, server_id)
            
            if not players:
                embed = EmbedBuilder.create_error_embed(
                    "Player Not Found",
                    f"Player '{player_name}' not found on server {server_name}."
                )
                await ctx.send(embed=embed)
                return
            
            # If multiple players found with similar names, use exact match or first match
            player = None
            for p in players:
                if p.name.lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                player = players[0]
            
            # Get detailed player stats
            player_stats = await player.get_detailed_stats()
            
            # Create embed
            embed = EmbedBuilder.create_stats_embed(player_stats, server_name)
            
            # Add combat statistics
            combat_kills = player_stats.get("combat_kills", 0)
            embed.add_field(
                name="Combat Stats", 
                value=f"Combat Kills: {combat_kills}\nMelee Kills: {player_stats.get('melee_percentage', 0)}%", 
                inline=True
            )
            
            # Add weapon category breakdown
            weapon_categories = player_stats.get("weapon_categories", {})
            if weapon_categories:
                # Format categories
                category_str = "\n".join([f"{category.title()}: {count} kills" 
                                       for category, count in weapon_categories.items()])
                embed.add_field(name="Weapon Categories", value=category_str, inline=True)
            
            # Add weapon stats if available
            weapons = player_stats.get("weapons", {})
            if weapons:
                # Get top 3 weapons
                sorted_weapons = sorted(weapons.items(), key=lambda x: x[1], reverse=True)[:3]
                weapon_str = "\n".join([f"{weapon}: {count} kills" for weapon, count in sorted_weapons])
                embed.add_field(name="Top Weapons", value=weapon_str, inline=False)
            
            # Add victim and nemesis info (only show player names, no IDs)
            favorite_victim = player_stats.get("favorite_victim")
            if favorite_victim:
                embed.add_field(
                    name="Favorite Victim",
                    value=f"{favorite_victim['player_name']} ({favorite_victim['kill_count']} kills)",
                    inline=True
                )
            
            nemesis = player_stats.get("nemesis")
            if nemesis:
                embed.add_field(
                    name="Nemesis",
                    value=f"{nemesis['player_name']} ({nemesis['kill_count']} kills)",
                    inline=True
                )
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting player stats: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting player stats: {e}"
            )
            await ctx.send(embed=embed)
    
    @stats.command(name="server", description="View server statistics")
    @app_commands.describe(server_id="The server ID to check stats for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def server_stats(self, ctx, server_id: str):
        """View statistics for a server"""
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to stats feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Server statistics is a premium feature. Please upgrade to access this feature."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                )
                await ctx.send(embed=embed)
                return
            
            # Get server stats
            server_stats = await server.get_server_stats()
            
            # Create embed
            embed = EmbedBuilder.create_server_stats_embed(server_stats)
            
            # Add top killers
            top_killers = server_stats.get("top_killers", [])
            if top_killers:
                killer_str = "\n".join([
                    f"{i+1}. {killer['player_name']}: {killer['kills']} kills"
                    for i, killer in enumerate(top_killers[:5])
                ])
                embed.add_field(name="Top Killers", value=killer_str, inline=False)
            
            # Add top weapons
            top_weapons = server_stats.get("top_weapons", [])
            if top_weapons:
                weapon_str = "\n".join([
                    f"{i+1}. {weapon['weapon']}: {weapon['kills']} kills"
                    for i, weapon in enumerate(top_weapons[:5])
                ])
                embed.add_field(name="Top Weapons", value=weapon_str, inline=False)
            
            # Add recent events
            recent_events = server_stats.get("recent_events", [])
            if recent_events:
                event_str = "\n".join([
                    f"{event['event_type']}: {format_time_ago(event['timestamp'])}"
                    for event in recent_events[:3]
                ])
                embed.add_field(name="Recent Events", value=event_str, inline=False)
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting server stats: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting server stats: {e}"
            )
            await ctx.send(embed=embed)
    
    @stats.command(name="leaderboard", description="View player leaderboards")
    @app_commands.describe(
        server_id="The server ID to check leaderboards for",
        stat="The statistic to rank by",
        limit="Number of players to show (max 25)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    @app_commands.choices(stat=[
        app_commands.Choice(name="Kills", value="kills"),
        app_commands.Choice(name="Deaths", value="deaths"),
        app_commands.Choice(name="K/D Ratio", value="kdr"),
        app_commands.Choice(name="Longest Shot", value="longest_shot"),
        app_commands.Choice(name="Kill Streak", value="highest_killstreak"),
        app_commands.Choice(name="Suicides", value="suicides")
    ])
    async def leaderboard(self, ctx, server_id: str, stat: str, limit: int = 10):
        """View leaderboards for a specific stat"""
        try:
            # Validate limit
            if limit < 1:
                limit = 10
            elif limit > 25:
                limit = 25
            
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to stats feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Leaderboards are a premium feature. Please upgrade to access this feature."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                )
                await ctx.send(embed=embed)
                return
            
            # Get leaderboard data
            leaderboard_data = await Player.get_leaderboard(self.bot.db, server_id, stat, limit)
            
            if not leaderboard_data:
                embed = EmbedBuilder.create_error_embed(
                    "No Data",
                    f"No player data found for '{stat}' on server {server_name}."
                )
                await ctx.send(embed=embed)
                return
            
            # Create pretty stat name mapping
            stat_names = {
                "kills": "Kills",
                "deaths": "Deaths",
                "kdr": "K/D Ratio",
                "longest_shot": "Longest Shot",
                "highest_killstreak": "Highest Kill Streak",
                "suicides": "Suicides"
            }
            
            stat_display = stat_names.get(stat, stat.title())
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                f"🏆 {stat_display} Leaderboard",
                f"Top {len(leaderboard_data)} players on {server_name}"
            )
            
            # Add leaderboard entries
            value_suffix = "m" if stat == "longest_shot" else ""
            
            leaderboard_str = ""
            for i, entry in enumerate(leaderboard_data):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                leaderboard_str += f"{medal} **{entry['player_name']}**: {entry['value']}{value_suffix}\n"
            
            embed.description = leaderboard_str
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting the leaderboard: {e}"
            )
            await ctx.send(embed=embed)
    
    @stats.command(name="weapon", description="View weapon statistics")
    @app_commands.describe(
        server_id="The server ID to check stats for",
        weapon_name="The weapon name to search for (partial match)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    @stats.command(name="weapon_categories", description="View statistics by weapon category")
    @app_commands.describe(
        server_id="The server ID to check stats for"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def weapon_categories(self, ctx, server_id: str):
        """View statistics by weapon category"""
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to stats feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Weapon category statistics is a premium feature. Please upgrade to access this feature."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    server_name = s.get("server_name", server_id)
                    break
                    
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Server {server_id} not found. Please check your server ID."
                )
                await ctx.send(embed=embed)
                return
            
            # Import weapon utilities
            from utils.weapon_stats import get_weapon_category, WEAPON_CATEGORIES
            
            # Query all weapons used on this server
            pipeline = [
                {
                    "$match": {
                        "server_id": server_id,
                        "is_suicide": False
                    }
                },
                {
                    "$group": {
                        "_id": "$weapon",
                        "kills": {"$sum": 1}
                    }
                }
            ]
            
            cursor = self.bot.db.kills.aggregate(pipeline)
            weapons = await cursor.to_list(length=None)
            
            if not weapons:
                embed = EmbedBuilder.create_error_embed(
                    "No Data",
                    f"No weapon data found for server {server_name}."
                )
                await ctx.send(embed=embed)
                return
                
            # Compile category stats
            category_stats = {}
            total_kills = 0
            
            for weapon in weapons:
                weapon_name = weapon["_id"]
                kill_count = weapon["kills"]
                total_kills += kill_count
                
                category = get_weapon_category(weapon_name)
                if category not in category_stats:
                    category_stats[category] = 0
                category_stats[category] += kill_count
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                f"📊 Weapon Category Stats",
                f"Weapon category breakdown on {server_name}"
            )
            
            # Add total kills
            embed.add_field(name="Total Kills", value=str(total_kills), inline=False)
            
            # Add category stats
            for category, kills in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                if category == "unknown" or category == "death_types":
                    continue
                    
                percentage = round((kills / total_kills) * 100, 1)
                embed.add_field(
                    name=category.replace("_", " ").title(),
                    value=f"{kills} kills ({percentage}%)",
                    inline=True
                )
            
            # Add definitions section
            definitions = []
            for category in category_stats.keys():
                if category in WEAPON_CATEGORIES and category not in ["death_types", "unknown"]:
                    weapons_list = WEAPON_CATEGORIES[category]
                    if len(weapons_list) > 3:
                        weapons_str = ", ".join(weapons_list[:3]) + f" and {len(weapons_list)-3} more"
                    else:
                        weapons_str = ", ".join(weapons_list)
                    definitions.append(f"**{category.replace('_', ' ').title()}**: {weapons_str}")
            
            if definitions:
                embed.add_field(name="Category Definitions", value="\n".join(definitions), inline=False)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting weapon category stats: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting weapon category stats: {e}"
            )
            await ctx.send(embed=embed)
            
    async def weapon_stats(self, ctx, server_id: str, weapon_name: str):
        """View statistics for a specific weapon"""
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to stats feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Weapon statistics is a premium feature. Please upgrade to access this feature."
                )
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                )
                await ctx.send(embed=embed)
                return
            
            # Import weapon utilities
            from utils.weapon_stats import get_weapon_category, is_actual_weapon, get_weapon_details

            # Query kills for this weapon
            pipeline = [
                {
                    "$match": {
                        "server_id": server_id,
                        "weapon": {"$regex": weapon_name, "$options": "i"},
                        "is_suicide": False
                    }
                },
                {
                    "$group": {
                        "_id": "$weapon",
                        "kills": {"$sum": 1},
                        "avg_distance": {"$avg": "$distance"},
                        "max_distance": {"$max": "$distance"},
                        "min_distance": {"$min": "$distance"},
                        "killers": {"$addToSet": "$killer_id"}
                    }
                },
                {
                    "$sort": {"kills": -1}
                },
                {
                    "$limit": 5
                }
            ]
            
            cursor = self.bot.db.kills.aggregate(pipeline)
            weapon_stats = await cursor.to_list(length=None)
            
            if not weapon_stats:
                embed = EmbedBuilder.create_error_embed(
                    "No Data",
                    f"No data found for weapons matching '{weapon_name}' on server {server_name}."
                )
                await ctx.send(embed=embed)
                return
            
            # Create embeds for each weapon
            embeds = []
            
            for weapon in weapon_stats:
                weapon_name = weapon["_id"]
                weapon_category = get_weapon_category(weapon_name)
                
                # Get top users of this weapon (only store names, no IDs)
                top_users_pipeline = [
                    {
                        "$match": {
                            "server_id": server_id,
                            "weapon": weapon_name,
                            "is_suicide": False
                        }
                    },
                    {
                        "$group": {
                            "_id": {"$toLower": "$killer_name"},
                            "name": {"$first": "$killer_name"},
                            "kills": {"$sum": 1},
                            "avg_distance": {"$avg": "$distance"},
                            "max_distance": {"$max": "$distance"}
                        }
                    },
                    {
                        "$sort": {"kills": -1}
                    },
                    {
                        "$limit": 5
                    }
                ]
                
                top_users_cursor = self.bot.db.kills.aggregate(top_users_pipeline)
                top_users = await top_users_cursor.to_list(length=None)
                
                # Get detailed weapon information
                weapon_details = get_weapon_details(weapon_name)
                
                # Create embed with weapon category
                embed = EmbedBuilder.create_base_embed(
                    f"🔫 {weapon_name} Stats",
                    f"Weapon statistics on {server_name}"
                )
                
                # Add basic stats
                embed.add_field(name="Weapon Type", value=weapon_details.get("type", weapon_category.title()), inline=True)
                embed.add_field(name="Total Kills", value=str(weapon["kills"]), inline=True)
                embed.add_field(name="Unique Users", value=str(len(weapon["killers"])), inline=True)
                
                # Add weapon details if available
                if weapon_details.get("ammo"):
                    embed.add_field(name="Ammunition", value=weapon_details["ammo"], inline=True)
                if weapon_details.get("damage"):
                    embed.add_field(name="Damage", value=str(weapon_details["damage"]), inline=True)
                if weapon_details.get("effective_range"):
                    embed.add_field(name="Effective Range", value=weapon_details["effective_range"], inline=True)
                if weapon_details.get("fire_rate"):
                    embed.add_field(name="Fire Rate", value=weapon_details["fire_rate"], inline=True)
                
                # Add weapon description if available
                if weapon_details.get("description"):
                    embed.add_field(name="Description", value=weapon_details["description"], inline=False)
                
                # Add distance statistics in one field
                distance_info = []
                if weapon.get("avg_distance"):
                    distance_info.append(f"Avg: {round(weapon['avg_distance'], 1)}m")
                if weapon.get("min_distance"):
                    distance_info.append(f"Min: {round(weapon['min_distance'], 1)}m")
                if weapon.get("max_distance"):
                    distance_info.append(f"Max: {round(weapon['max_distance'], 1)}m")
                
                if distance_info:
                    embed.add_field(
                        name="Distance Stats", 
                        value="\n".join(distance_info), 
                        inline=False
                    )
                
                # Add top users (only show names, not IDs)
                if top_users:
                    top_users_str = "\n".join([
                        f"{i+1}. **{user['name']}**: {user['kills']} kills" +
                        (f" (max: {round(user['max_distance'], 1)}m)" if user.get('max_distance') else "")
                        for i, user in enumerate(top_users)
                    ])
                    embed.add_field(name="Top Users", value=top_users_str, inline=False)
                
                # Special note for non-weapon kills
                if not is_actual_weapon(weapon_name):
                    if weapon_name == "land_vehicle":
                        embed.add_field(
                            name="Special Note",
                            value="Vehicle kills represent players killed by vehicles",
                            inline=False
                        )
                    elif weapon_name in ["falling", "suicide_by_relocation"]:
                        embed.add_field(
                            name="Special Note",
                            value="This represents a death type rather than an actual weapon",
                            inline=False
                        )
                
                embeds.append(embed)
            
            # Send the first embed with pagination if multiple
            if len(embeds) > 1:
                current_embed, view = paginate_embeds(embeds)
                await ctx.send(embed=current_embed, view=view)
            else:
                await ctx.send(embed=embeds[0])
            
        except Exception as e:
            logger.error(f"Error getting weapon stats: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting weapon stats: {e}"
            )
            await ctx.send(embed=embed)


async def setup(bot):
    """Set up the Stats cog"""
    await bot.add_cog(Stats(bot))
