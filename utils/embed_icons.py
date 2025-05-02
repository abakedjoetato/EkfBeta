"""Utility module for embedding icons in Discord embeds"""

import os
import discord
from typing import Dict, Optional, Any, Union

# Define the mapping for event types to icon files
EVENT_ICONS = {
    "mission": "attached_assets/Leonardo_Phoenix_10_Design_an_esportsstyle_logo_with_no_text_a_3-removebg-preview.png",
    "airdrop": "attached_assets/output_-_2025-04-20T215916.316-removebg-preview (3).png",  # Using killfeed icon as fallback
    "crash": "attached_assets/Leonardo_Phoenix_10_Design_an_esportsstyle_logo_with_no_text_a_2-removebg-preview.png",
    "trader": "attached_assets/Leonardo_Phoenix_10_Create_an_esportsstyle_logo_with_no_text_a_0-removebg-preview.png",
    "convoy": "attached_assets/output - 2025-04-19T181237.933.jpg",  # Using main logo as fallback
    "encounter": "attached_assets/output - 2025-04-19T181237.933.jpg",  # Using main logo as fallback
    "server_restart": "attached_assets/output - 2025-04-19T181237.933.jpg"  # Using main logo as fallback
}

# Define icon paths for other embed types
KILLFEED_ICON = "attached_assets/output_-_2025-04-20T215916.316-removebg-preview (3).png"
CONNECTIONS_ICON = "attached_assets/be9bd1ee-0557-4e74-9091-3e73118ee8f1__1_-removebg-preview.png"
LEADERBOARD_ICON = "attached_assets/Leonardo_Phoenix_10_Design_a_custom_logo_for_a_Discord_embed_2-removebg-preview.png"
WEAPON_STATS_ICON = "attached_assets/output_-_2025-04-20T233634.671-removebg-preview.png"
FACTIONS_ICON = "attached_assets/d9e7043d-a313-4e9f-9f56-64cc97f0166b__1_-removebg-preview.png"
ECONOMY_ICON = "attached_assets/Leonardo_Phoenix_10_Design_a_custom_logo_for_a_Discord_embed_2-removebg-preview.png"
GAMBLING_ICON = "attached_assets/output_-_2025-04-20T233634.671-removebg-preview.png"
DEFAULT_ICON = "attached_assets/output - 2025-04-19T181237.933.jpg"

# Cache for Discord Files to avoid recreating them
file_cache: Dict[str, discord.File] = {}

def get_event_icon(event_type: str) -> Optional[str]:
    """Get the icon file path for an event type
    
    Args:
        event_type: The type of event
        
    Returns:
        str: Path to the icon file or None if not found
    """
    return EVENT_ICONS.get(event_type, DEFAULT_ICON)

def create_discord_file(icon_path: str) -> Optional[discord.File]:
    """Create a Discord File object for an icon
    
    Args:
        icon_path: Path to the icon file
        
    Returns:
        discord.File: The created file object or None if file doesn't exist
    """
    # Check if file exists
    if not os.path.exists(icon_path):
        return None
        
    # Use cache if available
    if icon_path in file_cache:
        # Create a fresh copy to avoid "File already consumed" errors
        return discord.File(icon_path, filename=os.path.basename(icon_path))
    
    # Create new file object
    file = discord.File(icon_path, filename=os.path.basename(icon_path))
    file_cache[icon_path] = file
    return file

def add_icon_to_embed(embed: discord.Embed, icon_path: Optional[str]) -> None:
    """Add an icon to an embed as a thumbnail
    
    Args:
        embed: The Discord embed to modify
        icon_path: Path to the icon file or None
    """
    if not icon_path or not os.path.exists(icon_path):
        return
        
    # Set the thumbnail URL to reference the attached file
    embed.set_thumbnail(url=f"attachment://{os.path.basename(icon_path)}")
    return

async def send_embed_with_icon(ctx_or_channel, embed: discord.Embed, icon_path: Optional[str], **kwargs) -> Optional[discord.Message]:
    """Helper function to send an embed with its icon consistently
    
    Args:
        ctx_or_channel: Context or channel to send the message to
        embed: The embed to send
        icon_path: Path to the icon file to attach
        **kwargs: Additional keyword arguments to pass to the send method
        
    Returns:
        discord.Message: The sent message or None if failed
    """
    try:
        # Create the file for the icon if a path is provided
        file = None
        if icon_path and os.path.exists(icon_path):
            file = create_discord_file(icon_path)
            # Add the icon to the embed
            add_icon_to_embed(embed, icon_path)
        
        # Send the message with the file if available
        if hasattr(ctx_or_channel, 'send'):
            if file:
                return await ctx_or_channel.send(embed=embed, file=file, **kwargs)
            else:
                return await ctx_or_channel.send(embed=embed, **kwargs)
        elif hasattr(ctx_or_channel, 'followup'):
            if file:
                return await ctx_or_channel.followup.send(embed=embed, file=file, **kwargs)
            else:
                return await ctx_or_channel.followup.send(embed=embed, **kwargs)
        return None
    except Exception as e:
        # Fall back to sending without the file if there's an error
        try:
            if hasattr(ctx_or_channel, 'send'):
                return await ctx_or_channel.send(embed=embed, **kwargs)
            elif hasattr(ctx_or_channel, 'followup'):
                return await ctx_or_channel.followup.send(embed=embed, **kwargs)
            return None
        except:
            return None

def get_icon_for_embed_type(embed_type: str) -> Optional[str]:
    """Get the appropriate icon for an embed type
    
    Args:
        embed_type: The type of embed (kill, event, stats, etc.)
        
    Returns:
        str: Path to the icon file
    """
    icon_map = {
        "kill": KILLFEED_ICON,
        "event": DEFAULT_ICON,  # Will be overridden by specific event type
        "stats": DEFAULT_ICON,
        "server_stats": DEFAULT_ICON,
        "weapon_stats": WEAPON_STATS_ICON,
        "leaderboard": LEADERBOARD_ICON,
        "connection": CONNECTIONS_ICON,
        "faction": FACTIONS_ICON,
        "economy": ECONOMY_ICON,
        "gambling": GAMBLING_ICON,
        "error": DEFAULT_ICON,
        "success": DEFAULT_ICON,
        "info": DEFAULT_ICON,
    }
    
    return icon_map.get(embed_type, DEFAULT_ICON)
