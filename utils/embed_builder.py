"""
Utility for building consistent Discord embeds
"""
import random
import discord
from datetime import datetime

from config import EMBED_COLOR, EMBED_FOOTER, SUICIDE_MESSAGES

class EmbedBuilder:
    """Builder for creating Discord embeds with consistent styling"""
    
    @staticmethod
    def create_base_embed(title=None, description=None):
        """Create a base embed with consistent styling"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER)
        return embed
    
    @staticmethod
    def create_kill_embed(kill_data):
        """Create an embed for a kill event"""
        # Handle suicide case
        if kill_data["is_suicide"]:
            suicide_message = random.choice(SUICIDE_MESSAGES)
            embed = EmbedBuilder.create_base_embed(
                title="☠️ Suicide",
                description=f"**{kill_data['killer_name']}** {suicide_message}"
            )
            
            # Add suicide type as field
            suicide_type_display = {
                "menu": "Menu Suicide",
                "fall": "Falling Damage",
                "other": "Self-Inflicted"
            }
            embed.add_field(
                name="Method", 
                value=suicide_type_display.get(kill_data["suicide_type"], "Unknown"),
                inline=True
            )
            
        else:
            # Regular kill
            embed = EmbedBuilder.create_base_embed(
                title="⚔️ Kill Feed",
                description=f"**{kill_data['killer_name']}** killed **{kill_data['victim_name']}**"
            )
            
            # Add weapon field
            embed.add_field(name="Weapon", value=kill_data["weapon"], inline=True)
            
            # Add distance field if available
            if kill_data["distance"] > 0:
                embed.add_field(name="Distance", value=f"{kill_data['distance']}m", inline=True)
        
        # Add timestamp field
        timestamp_str = kill_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name="Time", value=timestamp_str, inline=True)
        
        return embed
    
    @staticmethod
    def create_event_embed(event_data):
        """Create an embed for a game event"""
        # Set title and description based on event type
        event_title_map = {
            "mission": "🎯 Mission Started",
            "airdrop": "🛩️ Air Drop Inbound",
            "crash": "🚁 Helicopter Crash",
            "trader": "💰 Trader Spawned",
            "convoy": "🚚 Convoy Started",
            "encounter": "⚠️ Special Encounter",
            "server_restart": "🔄 Server Restarted"
        }
        
        title = event_title_map.get(event_data["event_type"], "🔔 Game Event")
        
        # Format description based on event type and details
        if event_data["event_type"] == "server_restart":
            description = "The server has been restarted."
        elif event_data["event_type"] == "convoy":
            start, end = event_data["details"]
            description = f"Convoy traveling from **{start}** to **{end}**"
        elif event_data["event_type"] == "encounter":
            encounter_type, location = event_data["details"]
            description = f"**{encounter_type}** encounter at **{location}**"
        else:
            description = f"Location: **{event_data['details'][0]}**"
        
        embed = EmbedBuilder.create_base_embed(title=title, description=description)
        
        # Add timestamp field
        timestamp_str = event_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name="Time", value=timestamp_str, inline=True)
        
        return embed
    
    @staticmethod
    def create_stats_embed(player_data, server_name=None):
        """Create an embed for player statistics"""
        player_name = player_data["player_name"]
        embed = EmbedBuilder.create_base_embed(
            title=f"📊 Player Stats: {player_name}",
            description=f"Statistics for {player_name}" + 
                        (f" on {server_name}" if server_name else "")
        )
        
        # Add basic stats
        kills = player_data.get("kills", 0)
        deaths = player_data.get("deaths", 0)
        kdr = round(kills / max(deaths, 1), 2)
        
        embed.add_field(name="Kills", value=str(kills), inline=True)
        embed.add_field(name="Deaths", value=str(deaths), inline=True)
        embed.add_field(name="K/D Ratio", value=str(kdr), inline=True)
        
        # Add streak stats
        kill_streak = player_data.get("highest_killstreak", 0)
        death_streak = player_data.get("highest_deathstreak", 0)
        current_streak = player_data.get("current_streak", 0)
        
        embed.add_field(name="Highest Kill Streak", value=str(kill_streak), inline=True)
        embed.add_field(name="Highest Death Streak", value=str(death_streak), inline=True)
        
        # Add current streak
        if current_streak > 0:
            streak_type = "Kill"
        elif current_streak < 0:
            streak_type = "Death"
            current_streak = abs(current_streak)
        else:
            streak_type = "None"
            current_streak = 0
            
        embed.add_field(name="Current Streak", value=f"{streak_type}: {current_streak}", inline=True)
        
        # Add suicide stats
        suicides = player_data.get("suicides", 0)
        embed.add_field(name="Suicides", value=str(suicides), inline=True)
        
        # Add longest shot if available
        longest_shot = player_data.get("longest_shot", 0)
        if longest_shot > 0:
            embed.add_field(name="Longest Shot", value=f"{longest_shot}m", inline=True)
        
        # Add weapon stats if available
        weapons = player_data.get("weapons", {})
        if weapons:
            # Get most used weapon
            most_used = max(weapons.items(), key=lambda x: x[1])
            embed.add_field(
                name="Favorite Weapon", 
                value=f"{most_used[0]} ({most_used[1]} kills)", 
                inline=True
            )
        
        return embed
    
    @staticmethod
    def create_server_stats_embed(server_data):
        """Create an embed for server statistics"""
        server_name = server_data["server_name"]
        embed = EmbedBuilder.create_base_embed(
            title=f"📊 Server Stats: {server_name}",
            description=f"Statistics for {server_name}"
        )
        
        # Add basic stats
        total_kills = server_data.get("total_kills", 0)
        total_deaths = server_data.get("total_deaths", 0)
        total_suicides = server_data.get("total_suicides", 0)
        
        embed.add_field(name="Total Kills", value=str(total_kills), inline=True)
        embed.add_field(name="Total Deaths", value=str(total_deaths), inline=True)
        embed.add_field(name="Total Suicides", value=str(total_suicides), inline=True)
        
        # Add player stats
        total_players = server_data.get("total_players", 0)
        online_players = server_data.get("online_players", 0)
        
        embed.add_field(name="Total Players", value=str(total_players), inline=True)
        embed.add_field(name="Online Players", value=str(online_players), inline=True)
        
        # Add weapon stats if available
        weapons = server_data.get("weapons", {})
        if weapons:
            # Get most used weapon
            most_used = max(weapons.items(), key=lambda x: x[1])
            embed.add_field(
                name="Most Used Weapon", 
                value=f"{most_used[0]} ({most_used[1]} kills)", 
                inline=True
            )
        
        return embed
    
    @staticmethod
    def create_error_embed(title, description):
        """Create an embed for error messages"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER)
        return embed
    
    @staticmethod
    def create_success_embed(title, description):
        """Create an embed for success messages"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=EMBED_FOOTER)
        return embed
    
    @staticmethod
    def create_progress_embed(title, description, progress=None, total=None):
        """Create an embed for progress messages"""
        embed = EmbedBuilder.create_base_embed(title=title, description=description)
        
        if progress is not None and total is not None:
            percentage = min(100, round((progress / total) * 100))
            progress_bar = f"{percentage}% complete"
            embed.add_field(name="Progress", value=progress_bar, inline=False)
            embed.add_field(name="Status", value=f"{progress}/{total}", inline=False)
        
        return embed
