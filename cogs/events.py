"""
Events commands and background tasks for monitoring server events
"""
import logging
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from models.guild import Guild
from models.server import Server
from models.event import Event, Connection
from utils.sftp import SFTPClient
from utils.parsers import LogParser
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission, update_voice_channel_name

logger = logging.getLogger(__name__)

async def server_id_autocomplete(interaction, current):
    """Autocomplete for server IDs"""
    try:
        # Get user's guild ID
        guild_id = interaction.guild_id
        
        # Get cached server data or fetch it
        cog = interaction.client.get_cog("Events")
        if not cog:
            cog = interaction.client.get_cog("Stats")  # Fallback to Stats cog cache
        
        if not cog or not hasattr(cog, "server_autocomplete_cache"):
            # Initialize cache if it doesn't exist
            if not hasattr(cog, "server_autocomplete_cache"):
                cog.server_autocomplete_cache = {}
        
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
            app_commands.Choice(name=server['name'], value=server['id'])
            for server in servers
            if current.lower() in server['id'].lower() or current.lower() in server['name'].lower()
        ]
        
        return filtered_servers[:25]
        
    except Exception as e:
        logger.error(f"Error in server autocomplete: {e}", exc_info=True)
        return [app_commands.Choice(name="Error loading servers", value="error")]

class Events(commands.Cog):
    """Events commands and background tasks"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="events", description="Server events commands")
    @commands.guild_only()
    async def events(self, ctx):
        """Events command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @events.command(name="help", description="Get help with events commands")
    async def events_help(self, ctx):
        """Show help for events commands"""
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            embed = EmbedBuilder.create_base_embed(
                "Events Commands Help",
                "Use these commands to manage event monitoring and notifications for your servers."
            , guild=guild_model)
            
            # Basic commands
            basic_commands = [
                "`/events start server:<name>` - Start monitoring events for a server",
                "`/events stop server:<name>` - Stop monitoring events for a server",
                "`/events status` - Check the status of all event monitors",
                "`/events list server:<name> [event_type:all] [limit:10]` - List recent events",
                "`/events online server:<name>` - List online players"
            ]
            
            embed.add_field(
                name="📊 Basic Commands",
                value="\n".join(basic_commands),
                inline=False
            )
            
            # Notification configuration commands
            config_commands = [
                "`/events config server:<name> ...` - Configure game event notifications",
                "  ↳ Set which game events (missions, airdrops, etc.) trigger notifications",
                "`/events conn_config server:<name> ...` - Configure connection notifications",
                "  ↳ Enable/disable player connect and disconnect notifications",
                "`/events suicide_config server:<name> ...` - Configure suicide notifications",
                "  ↳ Enable/disable different types of suicide notifications"
            ]
            
            embed.add_field(
                name="⚙️ Notification Configuration",
                value="\n".join(config_commands),
                inline=False
            )
            
            # Customization tips
            tips = [
                "**Reduce Channel Spam**: Disable notifications for common events",
                "**Focus on Important Events**: Keep rare events like airdrops enabled",
                "**Silence Suicides**: Disable menu/fall suicides if they happen too often",
                "**Admin Only**: These commands require administrator permissions"
            ]
            
            embed.add_field(
                name="💡 Tips",
                value="\n".join(tips),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error displaying events help: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="start", description="Start monitoring events for a server")
    @app_commands.describe(server_id="Select a server by name to monitor")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def start(self, ctx, server_id: str):
        """Start the events monitor for a server"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to events feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("events"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Events monitoring is a premium feature. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if server exists in this guild
            server_exists = False
            for server in guild_data.get("servers", []):
                if server.get("server_id") == server_id:
                    server_exists = True
                    break
            
            if not server_exists:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Server '{server_id}' not found in this guild. Please use an existing server name."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Start events monitor
            task_name = f"events_{ctx.guild.id}_{server_id}"
            
            # Check if task is already running
            if task_name in self.bot.background_tasks:
                # If task exists but is done, remove it
                if self.bot.background_tasks[task_name].done():
                    self.bot.background_tasks.pop(task_name)
                else:
                    embed = EmbedBuilder.create_error_embed(
                        "Already Running",
                        f"Events monitor for server {server_id} is already running."
                    , guild=guild_model)
                    await ctx.send(embed=embed)
                    return
            
            # Create initial response
            embed = EmbedBuilder.create_base_embed(
                "Starting Events Monitor",
                f"Starting events monitor for server {server_id}..."
            , guild=guild_model)
            message = await ctx.send(embed=embed)
            
            # Start the task
            task = asyncio.create_task(
                start_events_monitor(self.bot, ctx.guild.id, server_id)
            )
            self.bot.background_tasks[task_name] = task
            
            # Add callback to handle completion
            task.add_done_callback(
                lambda t: asyncio.create_task(
                    self._handle_task_completion(t, ctx.guild.id, server_id, message)
                )
            )
            
            # Update response after a short delay
            await asyncio.sleep(2)
            embed = EmbedBuilder.create_success_embed(
                "Events Monitor Started",
                f"Events monitor for server {server_id} has been started successfully."
            , guild=guild_model)
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error starting events monitor: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while starting the events monitor: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="stop", description="Stop monitoring events for a server")
    @app_commands.describe(server_id="Select a server by name to stop monitoring")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def stop(self, ctx, server_id: str):
        """Stop the events monitor for a server"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Check if task is running
            task_name = f"events_{ctx.guild.id}_{server_id}"
            if task_name not in self.bot.background_tasks:
                embed = EmbedBuilder.create_error_embed(
                    "Not Running",
                    f"Events monitor for server {server_id} is not running."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Cancel the task
            task = self.bot.background_tasks[task_name]
            task.cancel()
            
            # Remove the task
            self.bot.background_tasks.pop(task_name)
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Events Monitor Stopped",
                f"Events monitor for server {server_id} has been stopped successfully."
            , guild=guild_model)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error stopping events monitor: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while stopping the events monitor: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="status", description="Check events monitor status")
    async def status(self, ctx):
        """Check the status of events monitors for this guild"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check running tasks for this guild
            running_monitors = []
            for task_name, task in self.bot.background_tasks.items():
                if task_name.startswith(f"events_{ctx.guild.id}_"):
                    parts = task_name.split("_")
                    if len(parts) >= 3:
                        server_id = parts[2]
                        
                        # Find server name
                        server_name = server_id
                        for server in guild_data.get("servers", []):
                            if server.get("server_id") == server_id:
                                server_name = server.get("server_name", server_id)
                                break
                        
                        running_monitors.append({
                            "server_id": server_id,
                            "server_name": server_name,
                            "status": "Running" if not task.done() else "Completed"
                        })
            
            # Create embed
            if running_monitors:
                embed = EmbedBuilder.create_base_embed(
                    "Events Monitor Status",
                    f"Currently running events monitors for {ctx.guild.name}"
                , guild=guild_model)
                
                for monitor in running_monitors:
                    embed.add_field(
                        name=f"{monitor['server_name']} ({monitor['server_id']})",
                        value=f"Status: {monitor['status']}",
                        inline=False
                    )
            else:
                embed = EmbedBuilder.create_base_embed(
                    "Events Monitor Status",
                    f"No events monitors are currently running for {ctx.guild.name}."
                , guild=guild_model)
                
                # Add instructions
                embed.add_field(
                    name="How to Start",
                    value="Use `/events start server:<server_name>` to start monitoring a server.",
                    inline=False
                )
                
                # Add premium notice if needed
                guild = Guild(self.bot.db, guild_data)
                if not guild.check_feature_access("events"):
                    embed.add_field(
                        name="Premium Feature",
                        value="Events monitoring is a premium feature. Please upgrade to access this feature.",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking events status: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while checking events status: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="list", description="List recent events for a server")
    @app_commands.describe(
        server_id="Select a server by name to list events for",
        event_type="Filter events by type",
        limit="Number of events to show (max 20)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="All Events", value="all"),
        app_commands.Choice(name="Missions", value="mission"),
        app_commands.Choice(name="Airdrops", value="airdrop"),
        app_commands.Choice(name="Helicopter Crashes", value="crash"),
        app_commands.Choice(name="Traders", value="trader"),
        app_commands.Choice(name="Convoys", value="convoy"),
        app_commands.Choice(name="Special Encounters", value="encounter"),
        app_commands.Choice(name="Server Restarts", value="server_restart")
    ])
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def list_events(self, ctx, server_id: str, event_type: str = "all", limit: int = 10):
        """List recent events for a server"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Validate limit
            if limit < 1:
                limit = 10
            elif limit > 20:
                limit = 20
            
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to events feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("events"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Events monitoring is a premium feature. Please upgrade to access this feature."
                , guild=guild_model)
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
                    f"Server '{server_id}' not found in this guild. Please use an existing server name."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get events
            if event_type == "all":
                events = await Event.get_by_server(self.bot.db, server_id, limit)
            else:
                events = await Event.get_by_server(self.bot.db, server_id, limit, event_type)
            
            if not events:
                embed = EmbedBuilder.create_error_embed(
                    "No Events",
                    f"No events found for server {server_name}" +
                    (f" with type '{event_type}'" if event_type != "all" else "")
                )
                await ctx.send(embed=embed)
                return
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                "Recent Events",
                f"Recent events for {server_name}" +
                (f" (Type: {event_type})" if event_type != "all" else "")
            )
            
            # Add events to embed
            for i, event in enumerate(events):
                # Format timestamp
                timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                # Format details based on event type
                if event.event_type == "server_restart":
                    details = "Server restarted"
                elif event.event_type == "convoy":
                    start, end = event.details
                    details = f"From {start} to {end}"
                elif event.event_type == "encounter":
                    encounter_type, location = event.details
                    details = f"{encounter_type} at {location}"
                else:
                    details = event.details[0] if event.details else "No details"
                
                # Get event emoji
                event_emoji = {
                    "mission": "🎯",
                    "airdrop": "🛩️",
                    "crash": "🚁",
                    "trader": "💰",
                    "convoy": "🚚",
                    "encounter": "⚠️",
                    "server_restart": "🔄"
                }.get(event.event_type, "🔔")
                
                # Add to embed
                name = f"{event_emoji} {event.event_type.title()} ({timestamp_str})"
                embed.add_field(name=name, value=details, inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing events: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while listing events: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="players", description="List online players for a server")
    @app_commands.describe(server_id="Select a server by name to list players for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def online_players(self, ctx, server_id: str):
        """List online players for a server"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to connections feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("connections"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Player connections is a premium feature. Please upgrade to access this feature."
                , guild=guild_model)
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
                    f"Server '{server_id}' not found in this guild. Please use an existing server name."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get online players
            player_count, online_players = await server.get_online_player_count()
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                "Online Players",
                f"Currently {player_count} player(s) online on {server_name}"
            , guild=guild_model)
            
            # Add players to embed
            if player_count > 0:
                # Convert to list and sort by name
                players_list = [
                    {"id": player_id, "name": player_name}
                    for player_id, player_name in online_players.items()
                ]
                players_list.sort(key=lambda p: p["name"])
                
                # Format player list
                players_text = "\n".join([
                    f"{i+1}. {player['name']}"
                    for i, player in enumerate(players_list)
                ])
                
                embed.add_field(name="Players", value=players_text, inline=False)
            else:
                embed.add_field(name="Players", value="No players currently online", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing online players: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while listing online players: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="config", description="Configure event notifications")
    @app_commands.describe(
        server_id="Select a server by name to configure",
        mission="Enable mission event notifications (True/False)",
        airdrop="Enable airdrop event notifications (True/False)",
        crash="Enable crash event notifications (True/False)",
        trader="Enable trader event notifications (True/False)",
        convoy="Enable convoy event notifications (True/False)",
        encounter="Enable encounter event notifications (True/False)",
        server_restart="Enable server restart notifications (True/False)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def configure_events(self, ctx, server_id: str, 
                             mission: Optional[bool] = None,
                             airdrop: Optional[bool] = None,
                             crash: Optional[bool] = None,
                             trader: Optional[bool] = None,
                             convoy: Optional[bool] = None,
                             encounter: Optional[bool] = None,
                             server_restart: Optional[bool] = None):
        """Configure which event notifications are enabled"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Get server
            server = await Server.get_by_id(self.bot.db, server_id, ctx.guild.id)
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Could not find server with ID {server_id} for this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Build settings dictionary from provided arguments
            settings = {}
            if mission is not None:
                settings["mission"] = mission
            if airdrop is not None:
                settings["airdrop"] = airdrop
            if crash is not None:
                settings["crash"] = crash
            if trader is not None:
                settings["trader"] = trader
            if convoy is not None:
                settings["convoy"] = convoy
            if encounter is not None:
                settings["encounter"] = encounter
            if server_restart is not None:
                settings["server_restart"] = server_restart
            
            # If no settings were provided, show current settings
            if not settings:
                embed = EmbedBuilder.create_base_embed(
                    "Event Notification Settings",
                    f"Current event notification settings for {server.name}"
                , guild=guild_model)
                
                # Add current settings to embed
                notification_settings = []
                for event_type, enabled in server.event_notifications.items():
                    status = "✅ Enabled" if enabled else "❌ Disabled"
                    notification_settings.append(f"{event_type.replace('_', ' ').title()}: {status}")
                
                embed.add_field(
                    name="Event Types",
                    value="\n".join(notification_settings) or "No event types configured",
                    inline=False
                )
                
                embed.add_field(
                    name="How to Configure",
                    value="Use `/events config server:<server_name> event_type:<true/false>` to enable or disable notifications. " \
                          "For example, `/events config server:my_server mission:true airdrop:false`.",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return
            
            # Update settings
            success = await server.update_event_notifications(settings)
            if not success:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Failed to update event notification settings. Please try again later."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create success embed
            embed = EmbedBuilder.create_success_embed(
                "Event Notifications Updated",
                f"Successfully updated event notification settings for {server.name}."
            , guild=guild_model)
            
            # Add updated settings to embed
            updated_settings = []
            for event_type, enabled in settings.items():
                status = "✅ Enabled" if enabled else "❌ Disabled"
                updated_settings.append(f"{event_type.replace('_', ' ').title()}: {status}")
            
            embed.add_field(
                name="Updated Settings",
                value="\n".join(updated_settings),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error configuring event notifications: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="conn_config", description="Configure connection notifications")
    @app_commands.describe(
        server_id="Select a server by name to configure",
        connect="Enable player connection notifications (True/False)",
        disconnect="Enable player disconnection notifications (True/False)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def configure_connections(self, ctx, server_id: str, 
                                connect: Optional[bool] = None,
                                disconnect: Optional[bool] = None):
        """Configure which connection notifications are enabled"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Get server
            server = await Server.get_by_id(self.bot.db, server_id, ctx.guild.id)
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Could not find server with ID {server_id} for this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Build settings dictionary from provided arguments
            settings = {}
            if connect is not None:
                settings["connect"] = connect
            if disconnect is not None:
                settings["disconnect"] = disconnect
            
            # If no settings were provided, show current settings
            if not settings:
                embed = EmbedBuilder.create_base_embed(
                    "Connection Notification Settings",
                    f"Current connection notification settings for {server.name}"
                , guild=guild_model)
                
                # Add current settings to embed
                notification_settings = []
                for conn_type, enabled in server.connection_notifications.items():
                    status = "✅ Enabled" if enabled else "❌ Disabled"
                    notification_settings.append(f"{conn_type.replace('_', ' ').title()}: {status}")
                
                embed.add_field(
                    name="Connection Types",
                    value="\n".join(notification_settings) or "No connection types configured",
                    inline=False
                )
                
                embed.add_field(
                    name="How to Configure",
                    value="Use `/events conn_config server:<server_name> connect:<true/false> disconnect:<true/false>` to enable or disable notifications.",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return
            
            # Update settings
            success = await server.update_connection_notifications(settings)
            if not success:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Failed to update connection notification settings. Please try again later."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create success embed
            embed = EmbedBuilder.create_success_embed(
                "Connection Notifications Updated",
                f"Successfully updated connection notification settings for {server.name}."
            , guild=guild_model)
            
            # Add updated settings to embed
            updated_settings = []
            for conn_type, enabled in settings.items():
                status = "✅ Enabled" if enabled else "❌ Disabled"
                updated_settings.append(f"{conn_type.replace('_', ' ').title()}: {status}")
            
            embed.add_field(
                name="Updated Settings",
                value="\n".join(updated_settings),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error configuring connection notifications: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @events.command(name="suicide_config", description="Configure suicide notifications")
    @app_commands.describe(
        server_id="Select a server by name to configure",
        menu="Enable menu suicide notifications (True/False)",
        fall="Enable fall damage suicide notifications (True/False)",
        other="Enable other suicide notifications (True/False)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def configure_suicides(self, ctx, server_id: str, 
                               menu: Optional[bool] = None,
                               fall: Optional[bool] = None,
                               other: Optional[bool] = None):
        """Configure which suicide notifications are enabled"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Get server
            server = await Server.get_by_id(self.bot.db, server_id, ctx.guild.id)
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Could not find server with ID {server_id} for this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Build settings dictionary from provided arguments
            settings = {}
            if menu is not None:
                settings["menu"] = menu
            if fall is not None:
                settings["fall"] = fall
            if other is not None:
                settings["other"] = other
            
            # If no settings were provided, show current settings
            if not settings:
                embed = EmbedBuilder.create_base_embed(
                    "Suicide Notification Settings",
                    f"Current suicide notification settings for {server.name}"
                , guild=guild_model)
                
                # Add current settings to embed
                notification_settings = []
                for suicide_type, enabled in server.suicide_notifications.items():
                    status = "✅ Enabled" if enabled else "❌ Disabled"
                    notification_settings.append(f"{suicide_type.replace('_', ' ').title()}: {status}")
                
                embed.add_field(
                    name="Suicide Types",
                    value="\n".join(notification_settings) or "No suicide types configured",
                    inline=False
                )
                
                embed.add_field(
                    name="How to Configure",
                    value="Use `/events suicide_config server:<server_name> menu:<true/false> fall:<true/false> other:<true/false>` " \
                          "to enable or disable notifications.",
                    inline=False
                )
                
                await ctx.send(embed=embed)
                return
            
            # Update settings
            success = await server.update_suicide_notifications(settings)
            if not success:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Failed to update suicide notification settings. Please try again later."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create success embed
            embed = EmbedBuilder.create_success_embed(
                "Suicide Notifications Updated",
                f"Successfully updated suicide notification settings for {server.name}."
            , guild=guild_model)
            
            # Add updated settings to embed
            updated_settings = []
            for suicide_type, enabled in settings.items():
                status = "✅ Enabled" if enabled else "❌ Disabled"
                updated_settings.append(f"{suicide_type.replace('_', ' ').title()}: {status}")
            
            embed.add_field(
                name="Updated Settings",
                value="\n".join(updated_settings),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error configuring suicide notifications: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    async def _check_permission(self, ctx) -> bool:
        """Check if user has permission to use the command"""
        # Initialize guild_model to None first to avoid UnboundLocalError
        guild_model = None
        
        # Check if user has admin permission
        if has_admin_permission(ctx):
            return True
        
        # If not, send error message
        # Get the guild model for theme
        try:
            guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
        except Exception as e:
            logger.warning(f"Error getting guild model in permission check: {e}")
            
        embed = EmbedBuilder.create_error_embed(
            "Permission Denied",
            "You need administrator permission or the designated admin role to use this command.",
            guild=guild_model)
        await ctx.send(embed=embed, ephemeral=True)
        return False
    
    async def _handle_task_completion(self, task, guild_id, server_id, message):
        """Handle completion of a background task"""
        try:
            # Check if task was cancelled
            if task.cancelled():
                logger.info(f"Events monitor for server {server_id} was cancelled.")
                return
            
            # Check if task completed with an exception
            if task.exception():
                logger.error(
                    f"Events monitor for server {server_id} failed: {task.exception()}", 
                    exc_info=task.exception()
                )
                
                # Update message if still exists
                try:
                    # Find the guild for the server
                    try:
                        guild_data = await self.bot.db.guilds.find_one({"servers.server_id": server_id})
                        guild_model = None
                        if guild_data:
                            guild_model = Guild(self.bot.db, guild_data)
                        
                        embed = EmbedBuilder.create_error_embed(
                            "Events Monitor Failed",
                            f"The events monitor for server {server_id} has failed: {task.exception()}",
                            guild=guild_model
                        )
                    except Exception as ex:
                        # Fallback to simple error embed
                        logger.error(f"Error creating themed embed: {ex}")
                        embed = EmbedBuilder.create_error_embed(
                            "Events Monitor Failed",
                            f"The events monitor for server {server_id} has failed: {task.exception()}"
                        )
                    await message.edit(embed=embed)
                except:
                    pass
                
                return
            
            # Task completed normally
            logger.info(f"Events monitor for server {server_id} completed successfully.")
            
        except Exception as e:
            logger.error(f"Error handling task completion: {e}", exc_info=True)


async def start_events_monitor(bot, guild_id: int, server_id: str):
    """Background task to monitor events for a server"""
    from config import EVENTS_REFRESH_INTERVAL
    
    # Check if we actually have server data in the database
    # This prevents errors when the bot starts up with empty database
    if await bot.db.guilds.count_documents({"guild_id": guild_id, "servers": {"$exists": True, "$ne": []}}) == 0:
        logger.warning(f"No servers found for guild {guild_id} - skipping events monitor")
        return
        
    # Check if guild exists in bot's cache
    discord_guild = bot.get_guild(int(guild_id))
    if not discord_guild:
        logger.error(f"Guild {guild_id} not found in bot's cache - skipping events monitor")
        return
        
    logger.info(f"Starting events monitor for server {server_id} in guild {guild_id}")
    
    try:
        # Get server data
        server = await Server.get_by_id(bot.db, server_id, guild_id)
        if not server:
            logger.error(f"Server {server_id} not found in guild {guild_id}")
            return
            
        # Verify channel configuration
        events_channel_id = server.events_channel_id
        if not events_channel_id:
            logger.warning(f"No events channel configured for server {server_id} in guild {guild_id}")
            return
        
        # Create SFTP client connection or use existing one
        sftp_key = f"{guild_id}_{server_id}"
        if sftp_key in bot.sftp_connections:
            sftp_client = bot.sftp_connections[sftp_key]
            
            # Ensure connection is alive
            if not sftp_client.connected:
                connected = await sftp_client.connect()
                if not connected:
                    logger.error(f"Failed to connect to SFTP server for {server_id}: {sftp_client.last_error}")
                    return
        else:
            # Create new connection
            sftp_client = SFTPClient(
                host=server.sftp_host,
                port=server.sftp_port,
                username=server.sftp_username,
                password=server.sftp_password,
                server_id=server.id
            )
            
            # Try to connect
            connected = await sftp_client.connect()
            if not connected:
                logger.error(f"Failed to connect to SFTP server for {server_id}: {sftp_client.last_error}")
                return
            
            # Store client for later use
            bot.sftp_connections[sftp_key] = sftp_client
        
        # Get channels
        guild = bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild {guild_id} not found")
            await sftp_client.disconnect()
            return
        
        events_channel_id = server.events_channel_id
        events_channel = guild.get_channel(events_channel_id) if events_channel_id else None
        
        connections_channel_id = server.connections_channel_id
        connections_channel = guild.get_channel(connections_channel_id) if connections_channel_id else None
        
        voice_channel_id = server.voice_status_channel_id
        
        # Main monitoring loop
        while True:
            try:
                # Get log file
                log_file = await sftp_client.get_log_file()
                if not log_file:
                    logger.warning(f"No log file found for server {server_id}")
                    await asyncio.sleep(EVENTS_REFRESH_INTERVAL)
                    continue
                
                # Get last processed line number
                last_line = server.last_log_line
                
                # Get total lines in the file with timeout protection
                try:
                    total_lines = await sftp_client.get_file_size(
                        log_file,
                        chunk_size=5000  # Use a reasonable chunk size for better performance
                    )
                    
                    # If no new lines, sleep and continue
                    if total_lines <= last_line:
                        await asyncio.sleep(EVENTS_REFRESH_INTERVAL)
                        continue
                        
                    # Read new lines with timeout protection
                    new_lines = await sftp_client.read_file(
                        log_file, 
                        start_line=last_line,
                        max_lines=None,  # Read all new lines
                        chunk_size=1000  # Process in smaller chunks to prevent timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout reading log data for {server_id}, will retry")
                    # Reconnect after timeout
                    await sftp_client.disconnect()
                    await asyncio.sleep(1)
                    await sftp_client.connect()
                    await asyncio.sleep(EVENTS_REFRESH_INTERVAL)
                    continue
                
                if not new_lines:
                    await asyncio.sleep(EVENTS_REFRESH_INTERVAL)
                    continue
                
                # Parse new lines
                events, connections = LogParser.parse_log_lines(new_lines)
                
                # Process events
                if events and events_channel:
                    for event_data in events:
                        await process_event(bot, server, event_data, events_channel)
                
                # Process connections
                if connections and connections_channel:
                    for connection_data in connections:
                        await process_connection(bot, server, connection_data, connections_channel)
                
                # Update voice channel with player count
                if voice_channel_id:
                    # Get current player count
                    player_count, _ = await server.get_online_player_count()
                    
                    # Update voice channel
                    await update_voice_channel_name(bot, guild_id, voice_channel_id, player_count)
                
                # Update last processed line
                await server.update_last_log_line(last_line + len(new_lines))
                
            except asyncio.CancelledError:
                logger.info(f"Events monitor for server {server_id} cancelled")
                break
                
            except Exception as e:
                logger.error(f"Error in events monitor for server {server_id}: {e}", exc_info=True)
            
            # Sleep before next check
            await asyncio.sleep(EVENTS_REFRESH_INTERVAL)
        
    except asyncio.CancelledError:
        logger.info(f"Events monitor for server {server_id} cancelled")
        
    except Exception as e:
        logger.error(f"Error in events monitor for server {server_id}: {e}", exc_info=True)
        
    finally:
        # No need to clean up SFTP connection as killfeed monitor might be using it
        logger.info(f"Events monitor for server {server_id} stopped")


async def process_event(bot, server, event_data, channel):
    """Process an event and update the database"""
    try:
        # Create timestamp object if it's a string
        if isinstance(event_data["timestamp"], str):
            event_data["timestamp"] = datetime.fromisoformat(event_data["timestamp"])
        
        # Add server_id to the event
        event_data["server_id"] = server.id
        
        # Create event in database
        event = await Event.create(bot.db, event_data)
        
        # Check if this type of event notification is enabled
        event_type = event_data.get("type")
        if event_type in server.event_notifications and not server.event_notifications.get(event_type, True):
            logger.debug(f"Skipping notification for {event_type} event as it's disabled for server {server.id}")
            return
        
        # Get guild model for themed embed
        guild_data = await bot.db.guilds.find_one({"servers.server_id": server.id})
        guild_model = None
        if guild_data:
            guild_model = Guild(bot.db, guild_data)
        
        # Create embed for the event
        embed = EmbedBuilder.create_event_embed(event_data, guild=guild_model)
        
        # Get the icon file for the specific event type
        from utils.embed_icons import create_discord_file, get_event_icon
        # Get the event icon based on the event type
        event_icon_path = get_event_icon(event_data.get("type", "unknown"))
        icon_file = create_discord_file(event_icon_path) if event_icon_path else None
        
        # Send to channel with the event icon
        if icon_file:
            await channel.send(embed=embed, file=icon_file)
        else:
            # Fallback if file can't be created
            await channel.send(embed=embed)
        
        # Handle server restart event specially
        if event_data["type"] == "server_restart":
            # Reset player count tracking
            logger.info(f"Server restart detected for {server.id}")
        
    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)


async def process_connection(bot, server, connection_data, channel):
    """Process a connection event and update the database"""
    try:
        # Create timestamp object if it's a string
        if isinstance(connection_data["timestamp"], str):
            connection_data["timestamp"] = datetime.fromisoformat(connection_data["timestamp"])
        
        # Add server_id to the connection
        connection_data["server_id"] = server.id
        
        # Create connection in database
        connection = await Connection.create(bot.db, connection_data)
        
        # Get connection action
        action = connection_data["action"]
        
        # Check if this type of connection notification is enabled
        if action in server.connection_notifications and not server.connection_notifications.get(action, True):
            logger.debug(f"Skipping notification for {action} connection as it's disabled for server {server.id}")
            return
        
        # Get guild model for themed embed
        guild_data = await bot.db.guilds.find_one({"servers.server_id": server.id})
        guild_model = None
        if guild_data:
            guild_model = Guild(bot.db, guild_data)

        # Create base embed with theme
        if action == "connected":
            title = "🟢 Player Connected"
        else:
            title = "🔴 Player Disconnected"
            
        player_name = connection_data["player_name"]
        platform = connection_data.get("platform", "Unknown")
        
        # Create themed base embed
        embed = EmbedBuilder.create_base_embed(
            title=title,
            description=f"**{player_name}** has {action} to the server",
            guild=guild_model
        )
        
        # Override color for connection status
        if action == "connected":
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.red()
            
        embed.timestamp = connection_data["timestamp"]
        embed.add_field(name="Platform", value=platform, inline=True)
        
        # Get the icon file for the connection event
        from utils.embed_icons import create_discord_file, CONNECTIONS_ICON
        icon_file = create_discord_file(CONNECTIONS_ICON)
        
        # Send to channel with connection icon
        if icon_file:
            await channel.send(embed=embed, file=icon_file)
        else:
            # Fallback if file can't be created
            await channel.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error processing connection: {e}", exc_info=True)


async def setup(bot):
    """Set up the Events cog"""
    await bot.add_cog(Events(bot))
