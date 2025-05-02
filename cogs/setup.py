"""
Setup commands for configuring servers and channels
"""
import logging
import re
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime

from models.guild import Guild
from models.server import Server
from utils.sftp import SFTPClient
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission
from utils.parsers import CSVParser

logger = logging.getLogger(__name__)

class Setup(commands.Cog):
    """Setup commands for configuring servers and channels"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="setup", description="Server setup commands")
    @commands.guild_only()
    async def setup(self, ctx):
        """Setup command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @setup.command(name="addserver", description="Add a game server to track PvP stats")
    @app_commands.describe(
        server_id="Unique ID for the server (letters, numbers, underscores only)",
        server_name="Friendly name to display for this server",
        host="SFTP host address",
        port="SFTP port (default: 22)",
        username="SFTP username",
        password="SFTP password"
    )
    @app_commands.guild_only()
    async def add_server(self, ctx, server_id: str, server_name: str, host: str, username: str, password: str, port: int = 22):
        """Add a new server to track"""
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
            
            # Validate server ID (no spaces, special chars except underscore)
            if not re.match(r'^[a-zA-Z0-9_]+$', server_id):
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Server ID",
                    "Server ID can only contain letters, numbers, and underscores."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Store SFTP information
            sftp_info = {
                "host": host,
                "port": port,
                "username": username,
                "password": password
            }
            
            # Validate SFTP info
            if not host or not username or not password:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid SFTP Information",
                    "Please provide valid host, username, and password for SFTP connection."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get or create guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                guild = await Guild.create(self.bot.db, ctx.guild.id, ctx.guild.name)
            
            # Check if we can add more servers (premium tier limit)
            if not guild.check_feature_access("killfeed"):
                embed = EmbedBuilder.create_error_embed(
                    "Feature Disabled",
                    "This guild does not have the Killfeed feature enabled. Please contact an administrator."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if we're at server limit
            max_servers = guild.get_max_servers()
            if len(guild.servers) >= max_servers:
                embed = EmbedBuilder.create_error_embed(
                    "Server Limit Reached",
                    f"This guild has reached the maximum number of servers ({max_servers}) for its premium tier."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if server ID already exists
            for server in guild.servers:
                if server.get("server_id") == server_id:
                    embed = EmbedBuilder.create_error_embed(
                        "Server Exists",
                        f"A server with ID '{server_id}' already exists in this guild."
                    , guild=guild_model)
                    await ctx.send(embed=embed)
                    return
            
            # Initial response
            embed = EmbedBuilder.create_base_embed(
                "Adding Server",
                f"Testing connection to {server_name}..."
            , guild=guild_model)
            message = await ctx.send(embed=embed)
            
            # Create SFTP client to test connection
            sftp_client = SFTPClient(
                host=sftp_info["host"],
                port=sftp_info["port"],
                username=sftp_info["username"],
                password=sftp_info["password"],
                server_id=server_id
            )
            
            # Test connection
            connected = await sftp_client.connect()
            if not connected:
                embed = EmbedBuilder.create_error_embed(
                    "Connection Failed",
                    f"Failed to connect to SFTP server: {sftp_client.last_error}"
                , guild=guild_model)
                await message.edit(embed=embed)
                return
            
            # Check if we can find CSV files
            embed = EmbedBuilder.create_base_embed(
                "Adding Server",
                f"Connected successfully. Looking for CSV files..."
            , guild=guild_model)
            await message.edit(embed=embed)
            
            csv_files = await sftp_client.get_all_csv_files()
            if not csv_files:
                embed = EmbedBuilder.create_error_embed(
                    "No CSV Files Found",
                    "Could not find any CSV files in the server. Please check the server ID and directory structure."
                , guild=guild_model)
                await message.edit(embed=embed)
                await sftp_client.disconnect()
                return
            
            # Check if we can find log file
            embed = EmbedBuilder.create_base_embed(
                "Adding Server",
                f"Found {len(csv_files)} CSV file(s). Looking for log file..."
            , guild=guild_model)
            await message.edit(embed=embed)
            
            log_file = await sftp_client.get_log_file()
            log_found = log_file is not None
            
            # Create server object
            server_data = {
                "server_id": server_id,
                "server_name": server_name,
                "guild_id": ctx.guild.id,
                "sftp_host": sftp_info["host"],
                "sftp_port": sftp_info["port"],
                "sftp_username": sftp_info["username"],
                "sftp_password": sftp_info["password"],
                "last_csv_line": 0,
                "last_log_line": 0
            }
            
            # Add server to guild
            add_result = await guild.add_server(server_data)
            if not add_result:
                embed = EmbedBuilder.create_error_embed(
                    "Error Adding Server",
                    "Failed to add server to the database. This may be due to a server limit restriction."
                , guild=guild_model)
                await message.edit(embed=embed)
                await sftp_client.disconnect()
                return
            
            # Success message
            embed = EmbedBuilder.create_success_embed(
                "Server Added Successfully",
                f"Server '{server_name}' has been added and is ready for channel setup."
            , guild=guild_model)
            
            # Add connection details
            connection_status = [
                f"CSV Files: {len(csv_files)} found",
                f"Log File: {'Found' if log_found else 'Not found'}"
            ]
            embed.add_field(
                name="Connection Status", 
                value="\n".join(connection_status),
                inline=False
            )
            
            # Add next steps
            next_steps = [
                "Use `/setup channels <server_id>` to configure notification channels.",
                "Use `/killfeed start <server_id>` to start monitoring the killfeed.",
                "If you have premium, use `/events start <server_id>` to monitor game events."
            ]
            embed.add_field(
                name="Next Steps", 
                value="\n".join(next_steps),
                inline=False
            )
            
            await message.edit(embed=embed)
            await sftp_client.disconnect()
            
        except Exception as e:
            logger.error(f"Error adding server: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while adding the server: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @setup.command(name="removeserver", description="Remove a server")
    @app_commands.describe(server_id="The ID of the server to remove")
    async def remove_server(self, ctx, server_id: str):
        """Remove a server from tracking"""
        
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
            
            # Get guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if server exists
            server_exists = False
            server_name = server_id
            for server in guild.servers:
                if server.get("server_id") == server_id:
                    server_exists = True
                    server_name = server.get("server_name", server_id)
                    break
            
            if not server_exists:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Confirmation message
            embed = EmbedBuilder.create_base_embed(
                "Confirm Server Removal",
                f"Are you sure you want to remove server '{server_name}' ({server_id})?\n\n"
                "This will stop all monitoring tasks and delete historical data for this server.\n"
                "This action cannot be undone."
            )
            
            # Create confirmation buttons
            class ConfirmView(discord.ui.View):
                def __init__(self, timeout=60):
                    super().__init__(timeout=timeout)
                    self.value = None
                
                @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
                async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                        return
                    self.value = True
                    self.stop()
                    await interaction.response.defer()
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You cannot use this button.", ephemeral=True)
                        return
                    self.value = False
                    self.stop()
                    await interaction.response.defer()
            
            # Send confirmation message
            view = ConfirmView()
            message = await ctx.send(embed=embed, view=view)
            
            # Wait for confirmation
            await view.wait()
            
            if view.value is None:
                # Timeout
                embed = EmbedBuilder.create_error_embed(
                    "Timed Out",
                    "Server removal cancelled due to timeout."
                , guild=guild_model)
                await message.edit(embed=embed, view=None)
                return
            
            if not view.value:
                # Cancelled
                embed = EmbedBuilder.create_error_embed(
                    "Cancelled",
                    "Server removal cancelled."
                , guild=guild_model)
                await message.edit(embed=embed, view=None)
                return
            
            # Update message
            embed = EmbedBuilder.create_base_embed(
                "Removing Server",
                f"Removing server '{server_name}' and stopping all monitoring tasks..."
            , guild=guild_model)
            await message.edit(embed=embed, view=None)
            
            # Stop running tasks
            for task_type in ["killfeed", "events"]:
                task_name = f"{task_type}_{ctx.guild.id}_{server_id}"
                if task_name in self.bot.background_tasks:
                    task = self.bot.background_tasks[task_name]
                    task.cancel()
                    self.bot.background_tasks.pop(task_name)
            
            # Remove SFTP connection if exists
            sftp_key = f"{ctx.guild.id}_{server_id}"
            if sftp_key in self.bot.sftp_connections:
                client = self.bot.sftp_connections.pop(sftp_key)
                await client.disconnect()
            
            # Remove server from database
            removed = await guild.remove_server(server_id)
            
            if removed:
                embed = EmbedBuilder.create_success_embed(
                    "Server Removed",
                    f"Server '{server_name}' has been removed successfully, along with all its data."
                , guild=guild_model)
                await message.edit(embed=embed)
            else:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"Failed to remove server '{server_name}' from the database."
                , guild=guild_model)
                await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing server: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while removing the server: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @setup.command(name="channels", description="Configure notification channels for a server")
    @app_commands.describe(
        server_id="The ID of the server to configure",
        killfeed_channel="Channel for killfeed notifications",
        events_channel="Channel for event notifications",
        connections_channel="Channel for player connection notifications",
        economy_channel="Channel for economy notifications (premium tier 2+)",
        voice_status_channel="Voice channel to update with player count"
    )
    async def setup_channels(self, ctx, 
                            server_id: str,
                            killfeed_channel: discord.TextChannel = None,
                            events_channel: discord.TextChannel = None,
                            connections_channel: discord.TextChannel = None,
                            economy_channel: discord.TextChannel = None,
                            voice_status_channel: discord.VoiceChannel = None):
        """Configure notification channels for a server"""
        
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
            
            # Get guild
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if server exists
            server = None
            for s in guild.servers:
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Prepare update data
            update_data = {}
            update_desc = []
            
            # Update killfeed channel
            if killfeed_channel:
                update_data["killfeed_channel_id"] = killfeed_channel.id
                update_desc.append(f"Killfeed Channel: {killfeed_channel.mention}")
            
            # Check premium status for events and connections
            if (events_channel or connections_channel) and not guild.check_feature_access("events"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Events and connections monitoring are premium features. Please upgrade to access these features."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Update events channel
            if events_channel:
                update_data["events_channel_id"] = events_channel.id
                update_desc.append(f"Events Channel: {events_channel.mention}")
            
            # Update connections channel
            if connections_channel:
                update_data["connections_channel_id"] = connections_channel.id
                update_desc.append(f"Connections Channel: {connections_channel.mention}")
            
            # Update voice status channel
            if voice_status_channel:
                update_data["voice_status_channel_id"] = voice_status_channel.id
                update_desc.append(f"Voice Status Channel: {voice_status_channel.mention}")
                
            # Update economy channel (premium tier 2+ feature)
            if economy_channel:
                # Check if guild has economy feature (tier 2+)
                if not guild.check_feature_access("economy"):
                    embed = EmbedBuilder.create_error_embed(
                        "Premium Feature",
                        "Economy features require Premium Tier 2 or higher. Please upgrade to access these features."
                    , guild=guild_model)
                    await ctx.send(embed=embed)
                    return
                    
                update_data["economy_channel_id"] = economy_channel.id
                update_desc.append(f"Economy Channel: {economy_channel.mention}")
            
            # Check if any updates were provided
            if not update_data:
                embed = EmbedBuilder.create_error_embed(
                    "No Changes",
                    "No channel updates were provided."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Update server
            updated = await server.update(update_data)
            
            if updated:
                embed = EmbedBuilder.create_success_embed(
                    "Channels Updated",
                    f"Channels for '{server.name}' have been updated successfully."
                , guild=guild_model)
                
                # Add channel info
                if update_desc:
                    embed.add_field(
                        name="Updated Channels", 
                        value="\n".join(update_desc),
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            else:
                embed = EmbedBuilder.create_error_embed(
                    "Update Failed",
                    "Failed to update server channels."
                , guild=guild_model)
                await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting up channels: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while setting up channels: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @setup.command(name="list", description="List all configured servers for this guild")
    async def list_servers(self, ctx):
        """List all configured servers for this guild"""
        
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

            # Get guild
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data or not guild_data.get("servers"):
                embed = EmbedBuilder.create_error_embed(
                    "No Servers Found",
                    "No servers have been configured for this guild yet."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get servers
            servers = guild_data.get("servers", [])
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                f"Configured Servers for {ctx.guild.name}",
                f"Total servers: {len(servers)}"
            , guild=guild_model)
            
            # Add server info
            for i, server in enumerate(servers):
                server_id = server.get("server_id", "Unknown")
                server_name = server.get("server_name", "Unknown")
                
                # Get channel names
                killfeed_channel = None
                events_channel = None
                connections_channel = None
                economy_channel = None
                voice_channel = None
                
                if "killfeed_channel_id" in server:
                    channel = ctx.guild.get_channel(server["killfeed_channel_id"])
                    killfeed_channel = channel.mention if channel else "Not found"
                
                if "events_channel_id" in server:
                    channel = ctx.guild.get_channel(server["events_channel_id"])
                    events_channel = channel.mention if channel else "Not found"
                
                if "connections_channel_id" in server:
                    channel = ctx.guild.get_channel(server["connections_channel_id"])
                    connections_channel = channel.mention if channel else "Not found"
                    
                if "economy_channel_id" in server:
                    channel = ctx.guild.get_channel(server["economy_channel_id"])
                    economy_channel = channel.mention if channel else "Not found"
                
                if "voice_status_channel_id" in server:
                    channel = ctx.guild.get_channel(server["voice_status_channel_id"])
                    voice_channel = channel.mention if channel else "Not found"
                
                # Check if monitoring tasks are running
                killfeed_running = f"killfeed_{ctx.guild.id}_{server_id}" in self.bot.background_tasks
                events_running = f"events_{ctx.guild.id}_{server_id}" in self.bot.background_tasks
                
                # Build field value
                field_value = []
                field_value.append(f"ID: `{server_id}`")
                
                if killfeed_channel:
                    field_value.append(f"Killfeed: {killfeed_channel} " +
                                      (f"({':green_circle:' if killfeed_running else ':red_circle:'})" 
                                       if killfeed_channel != "Not found" else ""))
                
                if events_channel:
                    field_value.append(f"Events: {events_channel} " +
                                      (f"({':green_circle:' if events_running else ':red_circle:'})" 
                                       if events_channel != "Not found" else ""))
                
                if connections_channel:
                    field_value.append(f"Connections: {connections_channel}")
                    
                if economy_channel:
                    field_value.append(f"Economy: {economy_channel}")
                
                if voice_channel:
                    field_value.append(f"Voice Status: {voice_channel}")
                
                # Add monitor status if none of the channels have it yet
                if not killfeed_channel and not events_channel:
                    status = []
                    if killfeed_running:
                        status.append("Killfeed: :green_circle:")
                    else:
                        status.append("Killfeed: :red_circle:")
                    
                    if events_running:
                        status.append("Events: :green_circle:")
                    else:
                        status.append("Events: :red_circle:")
                    
                    if status:
                        field_value.append(" | ".join(status))
                
                # Add to embed
                embed.add_field(
                    name=f"{i+1}. {server_name}",
                    value="\n".join(field_value),
                    inline=False
                )
            
            # Add premium info
            guild = Guild(self.bot.db, guild_data)
            tier = guild.premium_tier
            max_servers = guild.get_max_servers()
            
            # Get available features
            features = guild.get_available_features()
            
            # Format features with emoji indicators
            feature_list = []
            feature_list.append(f"{'✅' if 'killfeed' in features else '❌'} Killfeed")
            feature_list.append(f"{'✅' if 'events' in features else '❌'} Events")
            feature_list.append(f"{'✅' if 'connections' in features else '❌'} Connections")
            feature_list.append(f"{'✅' if 'stats' in features else '❌'} Stats")
            feature_list.append(f"{'✅' if 'economy' in features else '❌'} Economy")
            feature_list.append(f"{'✅' if 'gambling' in features else '❌'} Gambling")
            
            # Format economy info if available
            if 'economy' in features:
                economy_info = []
                if tier >= 2:
                    economy_info.append("💰 Weekly Interest: Enabled")
                else:
                    economy_info.append("💰 Weekly Interest: Disabled (requires Tier 2+)")
            else:
                economy_info = ["💰 Economy features not available (requires Tier 1+)"]
                
            embed.add_field(
                name="Premium Status",
                value=f"Tier: {tier}\nMax Servers: {max_servers}\nUsed: {len(servers)}/{max_servers}",
                inline=False
            )
            
            embed.add_field(
                name="Available Features",
                value="\n".join(feature_list),
                inline=True
            )
            
            embed.add_field(
                name="Economy Status",
                value="\n".join(economy_info),
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing servers: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while listing servers: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @setup.command(name="historicalparse", description="Parse all historical data for a server")
    @app_commands.describe(server_id="The ID of the server to parse historical data for")
    async def historical_parse(self, ctx, server_id: str):
        """Parse all historical data for a server"""
        
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
            
            # Check if guild has stats feature
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("stats"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Historical parsing is a premium feature. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get server
            server = None
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = Server(self.bot.db, s)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID '{server_id}' not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Initial response
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Starting historical parse for server '{server.name}'.\n\n"
                "This process will parse all CSV files and may take a long time depending on the amount of data."
            )
            message = await ctx.send(embed=embed)
            
            # Start background task for historical parsing
            task = asyncio.create_task(self._historical_parse_task(server, message))
            
            # Store task
            task_name = f"historical_{ctx.guild.id}_{server_id}"
            self.bot.background_tasks[task_name] = task
            
            # Clean up task when done
            task.add_done_callback(lambda t: self.bot.background_tasks.pop(task_name, None))
            
        except Exception as e:
            logger.error(f"Error starting historical parse: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while starting historical parse: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    async def _historical_parse_task(self, server, message):
        """Background task for parsing historical data"""
        
        try:
            # Get guild model for themed embed
            guild_data = None
            guild_model = None
            try:
                # We don't have ctx in this task, so we use server's guild_id
                guild_data = await self.bot.db.guilds.find_one({"guild_id": server.guild_id})
                if guild_data:
                    guild_model = Guild(self.bot.db, guild_data)
            except Exception as e:
                logger.warning(f"Error getting guild model: {e}")

            # Create SFTP client
            sftp_client = SFTPClient(
                host=server.sftp_host,
                port=server.sftp_port,
                username=server.sftp_username,
                password=server.sftp_password,
                server_id=server.id
            )
            
            # Connect to SFTP
            connected = await sftp_client.connect()
            if not connected:
                embed = EmbedBuilder.create_error_embed(
                    "Connection Failed",
                    f"Failed to connect to SFTP server: {sftp_client.last_error}"
                , guild=guild_model)
                await message.edit(embed=embed)
                return
            
            # Get all CSV files
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Connected to SFTP server. Retrieving CSV files..."
            , guild=guild_model)
            await message.edit(embed=embed)
            
            csv_files = await sftp_client.get_all_csv_files()
            if not csv_files:
                embed = EmbedBuilder.create_error_embed(
                    "No CSV Files Found",
                    "Could not find any CSV files in the server."
                , guild=guild_model)
                await message.edit(embed=embed)
                await sftp_client.disconnect()
                return
            
            # Update progress
            embed = EmbedBuilder.create_base_embed(
                "Historical Parse",
                f"Found {len(csv_files)} CSV file(s). Starting to parse data..."
            , guild=guild_model)
            await message.edit(embed=embed)
            
            # Process each file
            total_kills = 0
            total_lines = 0
            processed_files = 0
            last_progress_update = datetime.now()
            start_time = datetime.now()
            total_file_size = 0
            
            # First calculate total size for better progress reporting
            for file_path in csv_files:
                size = await sftp_client.get_file_size(file_path)
                total_file_size += size
                
            # Create progress embed function for reuse
            async def update_progress(current_size, current_files, kills, estimated=None):
                elapsed = (datetime.now() - start_time).total_seconds()
                progress_pct = min(99.9, (current_size / max(1, total_file_size)) * 100) if total_file_size > 0 else 0
                
                # Calculate rate and ETA
                kill_rate = kills / max(1, elapsed) * 60  # kills per minute
                
                status_lines = [
                    f"Files: {current_files}/{len(csv_files)} ({progress_pct:.1f}%)",
                    f"Events: {kills:,} kill events processed",
                    f"Rate: {kill_rate:.1f} events per minute"
                ]
                
                if estimated:
                    status_lines.append(f"Estimated time remaining: {estimated}")
                
                embed = EmbedBuilder.create_progress_embed(
                    "Historical Parse In Progress",
                    "\n".join(status_lines),
                    progress=current_size,
                    total=total_file_size
                )
                await message.edit(embed=embed)
            
            current_size = 0
            batch_size = 1000  # Process this many events before committing to DB
            
            for i, file_path in enumerate(csv_files):
                # Check file size
                file_size = await sftp_client.get_file_size(file_path)
                
                # Update initial progress
                if i == 0 or (datetime.now() - last_progress_update).total_seconds() > 15:
                    await update_progress(current_size, processed_files, total_kills)
                    last_progress_update = datetime.now()
                
                # Read file in chunks
                chunk_size = 10000  # Process more lines at a time for efficiency
                total_chunks = (file_size + chunk_size - 1) // chunk_size  # Ceiling division
                
                # Track batch for bulk inserts
                kill_batch = []
                
                for chunk in range(total_chunks):
                    start_line = chunk * chunk_size
                    lines = await sftp_client.read_file(file_path, start_line, chunk_size)
                    total_lines += len(lines)
                    
                    # Parse lines
                    kill_events = CSVParser.parse_kill_lines(lines)
                    
                    # Process kill events
                    for kill_event in kill_events:
                        # Add server ID
                        kill_event["server_id"] = server.id
                        kill_batch.append(kill_event)
                        
                        # When batch is full, insert and process
                        if len(kill_batch) >= batch_size:
                            # Bulk insert
                            if kill_batch:  # Make sure batch isn't empty
                                await self.bot.db.kills.insert_many(kill_batch)
                                
                                # Update player stats (bulk operation)
                                from cogs.killfeed import update_player_stats
                                for event in kill_batch:
                                    await update_player_stats(self.bot, server.id, event)
                                
                                # Update stats and clear batch
                                total_kills += len(kill_batch)
                                kill_batch = []
                    
                    # Update progress based on processed data
                    current_chunk_size = min(chunk_size, file_size - start_line)
                    current_size += current_chunk_size
                    
                    # Update progress every 60 seconds or every 3 chunks
                    if (datetime.now() - last_progress_update).total_seconds() > 60 or chunk % 3 == 0:
                        # Calculate ETA
                        if current_size > 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            bytes_per_second = current_size / elapsed
                            remaining_bytes = total_file_size - current_size
                            
                            if bytes_per_second > 0:
                                eta_seconds = remaining_bytes / bytes_per_second
                                eta_str = f"{int(eta_seconds//60)}m {int(eta_seconds%60)}s"
                            else:
                                eta_str = "calculating..."
                        else:
                            eta_str = "calculating..."
                        
                        await update_progress(current_size, processed_files, total_kills, eta_str)
                        last_progress_update = datetime.now()
                
                # Process any remaining events in the batch
                if kill_batch:
                    await self.bot.db.kills.insert_many(kill_batch)
                    
                    # Update player stats (bulk operation)
                    from cogs.killfeed import update_player_stats
                    for event in kill_batch:
                        await update_player_stats(self.bot, server.id, event)
                    
                    # Update stats
                    total_kills += len(kill_batch)
                    kill_batch = []
                
                # Mark file as processed
                processed_files += 1
                
                # Update progress after each file
                await update_progress(current_size, processed_files, total_kills)
                last_progress_update = datetime.now()
            
            # Final update
            embed = EmbedBuilder.create_success_embed(
                "Historical Parse Complete",
                f"Successfully parsed {len(csv_files)} CSV file(s) and processed {total_kills} kill events."
            , guild=guild_model)
            await message.edit(embed=embed)
            
            # Disconnect
            await sftp_client.disconnect()
            
        except asyncio.CancelledError:
            logger.info(f"Historical parse for server {server.id} cancelled")
            embed = EmbedBuilder.create_error_embed(
                "Parse Cancelled",
                "The historical parse has been cancelled."
            , guild=guild_model)
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in historical parse for server {server.id}: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred during the historical parse: {e}"
            , guild=guild_model)
            await message.edit(embed=embed)
    
    async def _check_permission(self, ctx) -> bool:
        """Check if user has permission to use the command"""
        # Check if user has admin permission
        if has_admin_permission(ctx):
            return True
        
        # If not, send error message
        # Get the guild model for theme
        guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
        embed = EmbedBuilder.create_error_embed(
            "Permission Denied",
            "You need administrator permission or the designated admin role to use this command.",
            guild=guild_model)
        await ctx.send(embed=embed, ephemeral=True)
        return False


async def setup(bot):
    """Set up the Setup cog"""
    await bot.add_cog(Setup(bot))
