"""
Helper utility functions for various tasks
"""
import re
import logging
import random
import discord
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

def get_guild_premium_tier(guild_data: Dict[str, Any]) -> int:
    """Get the premium tier for a guild"""
    return guild_data.get("premium_tier", 0)

def is_feature_enabled(guild_data: Dict[str, Any], feature: str) -> bool:
    """Check if a feature is enabled for a guild based on premium tier"""
    from config import PREMIUM_TIERS
    
    tier = get_guild_premium_tier(guild_data)
    available_features = PREMIUM_TIERS.get(tier, {}).get("features", [])
    
    return feature in available_features

def can_add_server(guild_data: Dict[str, Any]) -> bool:
    """Check if a guild can add more servers based on premium tier"""
    from config import PREMIUM_TIERS
    
    tier = get_guild_premium_tier(guild_data)
    max_servers = PREMIUM_TIERS.get(tier, {}).get("max_servers", 1)
    current_servers = len(guild_data.get("servers", []))
    
    return current_servers < max_servers

def format_timestamp(timestamp: datetime) -> str:
    """Format a timestamp for display"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def create_pagination_buttons() -> discord.ui.View:
    """Create pagination buttons for embeds"""
    view = discord.ui.View()
    
    # First page button
    first_button = discord.ui.Button(
        emoji="⏮️", 
        style=discord.ButtonStyle.gray, 
        custom_id="pagination_first"
    )
    view.add_item(first_button)
    
    # Previous page button
    prev_button = discord.ui.Button(
        emoji="◀️", 
        style=discord.ButtonStyle.gray, 
        custom_id="pagination_prev"
    )
    view.add_item(prev_button)
    
    # Page indicator (disabled button)
    page_indicator = discord.ui.Button(
        label="Page 1", 
        style=discord.ButtonStyle.gray, 
        disabled=True,
        custom_id="pagination_indicator"
    )
    view.add_item(page_indicator)
    
    # Next page button
    next_button = discord.ui.Button(
        emoji="▶️", 
        style=discord.ButtonStyle.gray, 
        custom_id="pagination_next"
    )
    view.add_item(next_button)
    
    # Last page button
    last_button = discord.ui.Button(
        emoji="⏭️", 
        style=discord.ButtonStyle.gray, 
        custom_id="pagination_last"
    )
    view.add_item(last_button)
    
    return view

def paginate_embeds(embeds: List[discord.Embed], page: int = 0) -> tuple:
    """Get the current embed and update page indicator"""
    if not embeds:
        # Return empty embed if no embeds
        return discord.Embed(
            title="No Data",
            description="No data available to display.",
            color=discord.Color.red()
        ), None
    
    # Ensure page is within bounds
    page = max(0, min(page, len(embeds) - 1))
    
    # Get current embed
    current_embed = embeds[page]
    
    # Create view with pagination buttons
    view = create_pagination_buttons()
    
    # Update page indicator
    for item in view.children:
        if item.custom_id == "pagination_indicator":
            item.label = f"Page {page + 1}/{len(embeds)}"
    
    return current_embed, view

async def update_voice_channel_name(bot, guild_id: int, channel_id: int, player_count: int, queue_count: int = 0):
    """Update the voice channel name to show player counts"""
    try:
        # Get guild and channel
        guild = bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Could not find guild with ID {guild_id}")
            return False
        
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            logger.error(f"Could not find voice channel with ID {channel_id} in guild {guild.name}")
            return False
        
        # Format channel name
        if queue_count > 0:
            new_name = f"Players: {player_count} (Queue: {queue_count})"
        else:
            new_name = f"Players: {player_count}"
        
        # Update channel name if different
        if channel.name != new_name:
            await channel.edit(name=new_name)
            logger.info(f"Updated voice channel name to '{new_name}' in guild {guild.name}")
        
        return True
    
    except discord.Forbidden:
        logger.error(f"Missing permissions to edit voice channel in guild {guild_id}")
        return False
    except Exception as e:
        logger.error(f"Error updating voice channel name: {e}", exc_info=True)
        return False

def parse_sftp_url(url: str) -> Dict[str, Any]:
    """Parse an SFTP URL into components"""
    # Pattern: sftp://username:password@host:port
    pattern = r"sftp://([^:]+):([^@]+)@([^:]+):(\d+)"
    match = re.match(pattern, url)
    
    if not match:
        return None
    
    username, password, host, port = match.groups()
    
    return {
        "host": host,
        "port": int(port),
        "username": username,
        "password": password
    }

def format_time_ago(timestamp: datetime) -> str:
    """Format a timestamp as a relative time (e.g., '5 minutes ago')"""
    now = datetime.utcnow()
    delta = now - timestamp
    
    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    
    minutes = (delta.seconds // 60) % 60
    if minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    
    return "just now"

def has_admin_permission(ctx) -> bool:
    """Check if user has admin permission"""
    # Guild owner always has permission
    if ctx.author.id == ctx.guild.owner_id:
        return True
    
    # Check for administrator permission
    if ctx.author.guild_permissions.administrator:
        return True
    
    # Check for specific admin role
    admin_role_id = get_admin_role_id(ctx.guild.id)
    if admin_role_id and admin_role_id in [role.id for role in ctx.author.roles]:
        return True
    
    return False

async def get_admin_role_id(bot, guild_id: int) -> Optional[int]:
    """Get the admin role ID for a guild"""
    guild_data = await bot.db.guilds.find_one({"guild_id": guild_id})
    if not guild_data:
        return None
    
    return guild_data.get("admin_role_id")

def is_home_guild_admin(bot, user_id: int) -> bool:
    """Check if user is an admin in the home guild"""
    if not bot.home_guild_id:
        return False
    
    # Bot owner is always a home guild admin
    if user_id == bot.owner_id:
        return True
    
    # Get home guild
    home_guild = bot.get_guild(bot.home_guild_id)
    if not home_guild:
        return False
    
    # Get member in home guild
    member = home_guild.get_member(user_id)
    if not member:
        return False
    
    # Guild owner is admin
    if member.id == home_guild.owner_id:
        return True
    
    # Check for administrator permission
    if member.guild_permissions.administrator:
        return True
    
    return False
