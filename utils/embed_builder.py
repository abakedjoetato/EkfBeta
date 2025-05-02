"""
Utility for building consistent Discord embeds
"""
import random
import os
import discord
from datetime import datetime

from config import EMBED_THEMES, EMBED_COLOR, EMBED_FOOTER, SUICIDE_MESSAGES, SUICIDE_MESSAGES_BY_TYPE
from utils.embed_icons import (
    add_icon_to_embed, create_discord_file, get_event_icon,
    get_icon_for_embed_type, KILLFEED_ICON, DEFAULT_ICON,
    EVENT_ICONS, WEAPON_STATS_ICON, CONNECTIONS_ICON,
    LEADERBOARD_ICON, FACTIONS_ICON
)

class EmbedBuilder:
    """Builder for creating Discord embeds with consistent styling"""
    
    @staticmethod
    def create_base_embed(title=None, description=None, guild=None):
        """Create a base embed with consistent styling
        
        Args:
            title: The title of the embed
            description: The description of the embed
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with applied theme
        """
        # Determine theme to use
        theme_name = "default"
        
        # If a Guild model is passed, use its theme
        if guild and hasattr(guild, 'theme'):
            theme_name = guild.theme
        
        # Get theme settings
        theme = EMBED_THEMES.get(theme_name, EMBED_THEMES["default"])
        color = theme.get("color", EMBED_COLOR)
        footer = theme.get("footer", EMBED_FOOTER)
        
        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def create_kill_embed(kill_data, guild=None):
        """Create an embed for a kill event
        
        Args:
            kill_data: Dictionary with kill event data
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with kill information
        """
        # Handle suicide case
        if kill_data["is_suicide"]:
            # Get suicide type
            suicide_type = kill_data.get("suicide_type", "other")
            
            # Choose from type-specific messages if available, otherwise from general messages
            if suicide_type in SUICIDE_MESSAGES_BY_TYPE and SUICIDE_MESSAGES_BY_TYPE[suicide_type]:
                suicide_message = random.choice(SUICIDE_MESSAGES_BY_TYPE[suicide_type])
            else:
                suicide_message = random.choice(SUICIDE_MESSAGES)
                
            embed = EmbedBuilder.create_base_embed(
                title="☠️ Suicide",
                description=f"**{kill_data['killer_name']}** {suicide_message}",
                guild=guild
            )
            
            # Add suicide type as field
            suicide_type_display = {
                "menu": "Menu Suicide",
                "fall": "Falling Damage",
                "other": "Self-Inflicted"
            }
            embed.add_field(
                name="Method", 
                value=suicide_type_display.get(suicide_type, "Unknown"),
                inline=True
            )
            
            # Add killfeed icon to the suicide embed
            add_icon_to_embed(embed, KILLFEED_ICON)
            
        else:
            # Regular kill
            embed = EmbedBuilder.create_base_embed(
                title="⚔️ Kill Feed",
                description=f"**{kill_data['killer_name']}** killed **{kill_data['victim_name']}**",
                guild=guild
            )
            
            # Add weapon field
            embed.add_field(name="Weapon", value=kill_data["weapon"], inline=True)
            
            # Add distance field if available
            if kill_data["distance"] > 0:
                embed.add_field(name="Distance", value=f"{kill_data['distance']}m", inline=True)
            
            # Add killfeed icon to the kill embed
            add_icon_to_embed(embed, KILLFEED_ICON)
        
        # Add timestamp field
        timestamp_str = kill_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name="Time", value=timestamp_str, inline=True)
        
        return embed
    
    @staticmethod
    def create_event_embed(event_data, guild=None):
        """Create an embed for a game event
        
        Args:
            event_data: Dictionary with event data
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with event information
        """
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
        
        embed = EmbedBuilder.create_base_embed(title=title, description=description, guild=guild)
        
        # Add timestamp field
        timestamp_str = event_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name="Time", value=timestamp_str, inline=True)
        
        # Get the appropriate icon for this event type
        event_type = event_data["event_type"]
        icon_path = get_event_icon(event_type)
        add_icon_to_embed(embed, icon_path)
        
        return embed
    
    @staticmethod
    def create_stats_embed(player_data, server_name=None, guild=None):
        """Create an embed for player statistics"""
        player_name = player_data["player_name"]
        embed = EmbedBuilder.create_base_embed(
            title=f"📊 Player Stats: {player_name}",
            description=f"Statistics for {player_name}" + 
                        (f" on {server_name}" if server_name else ""),
            guild=guild
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
        
        # Add icon for player stats
        add_icon_to_embed(embed, WEAPON_STATS_ICON)
        
        return embed
    
    @staticmethod
    def create_server_stats_embed(server_data, guild=None):
        """Create an embed for server statistics"""
        server_name = server_data["server_name"]
        embed = EmbedBuilder.create_base_embed(
            title=f"📊 Server Stats: {server_name}",
            description=f"Statistics for {server_name}",
            guild=guild
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
        
        # Add icon for server stats
        add_icon_to_embed(embed, LEADERBOARD_ICON)
        
        return embed
    
    @staticmethod
    def create_error_embed(title, description, guild=None):
        """Create an embed for error messages
        
        Args:
            title: The title of the embed
            description: The description of the embed
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with error styling
        """
        # Use base embed for consistent theming, but override with red for errors
        embed = EmbedBuilder.create_base_embed(title, description, guild)
        embed.color = discord.Color.red()
        add_icon_to_embed(embed, get_icon_for_embed_type("error"))
        return embed
    
    @staticmethod
    def create_success_embed(title, description, guild=None):
        """Create an embed for success messages
        
        Args:
            title: The title of the embed
            description: The description of the embed
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with success styling
        """
        # Use base embed for consistent theming
        embed = EmbedBuilder.create_base_embed(title, description, guild)
        # For success embeds, we'll use green if default theme, otherwise use the theme color
        if not guild or not hasattr(guild, 'theme') or guild.theme == "default":
            embed.color = discord.Color.green()
        add_icon_to_embed(embed, get_icon_for_embed_type("success"))
        return embed
        
    @staticmethod
    def create_info_embed(title, description, guild=None):
        """Create an embed for information messages
        
        Args:
            title: The title of the embed
            description: The description of the embed
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with info styling
        """
        # Use base embed for consistent theming
        embed = EmbedBuilder.create_base_embed(title, description, guild)
        # For info embeds, we'll use blue
        embed.color = discord.Color.blue()
        add_icon_to_embed(embed, get_icon_for_embed_type("info"))
        return embed
    
    @staticmethod
    def create_progress_embed(title, description, progress=None, total=None, guild=None):
        """Create an embed for progress messages
        
        Args:
            title: The title of the embed
            description: The description of the embed
            progress: Optional current progress value
            total: Optional total goal value
            guild: Optional guild object to use theme from
            
        Returns:
            discord.Embed: The created embed with progress information
        """
        embed = EmbedBuilder.create_base_embed(title=title, description=description, guild=guild)
        
        if progress is not None and total is not None:
            percentage = min(100, round((progress / total) * 100))
            progress_bar = f"{percentage}% complete"
            embed.add_field(name="Progress", value=progress_bar, inline=False)
            embed.add_field(name="Status", value=f"{progress}/{total}", inline=False)
        
        # Add info icon to progress embeds
        add_icon_to_embed(embed, get_icon_for_embed_type("info"))
        
        return embed
