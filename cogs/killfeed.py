"""
Killfeed commands and background tasks for monitoring kill feeds
"""
import logging
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Dict, List, Any, Optional

from models.guild import Guild
from models.server import Server
from models.player import Player
from utils.sftp import SFTPClient
from utils.parsers import CSVParser
from utils.embed_builder import EmbedBuilder
from utils.helpers import has_admin_permission

logger = logging.getLogger(__name__)

class Killfeed(commands.Cog):
    """Killfeed commands and background tasks"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="killfeed", description="Killfeed commands")
    @commands.guild_only()
    async def killfeed(self, ctx):
        """Killfeed command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @killfeed.command(name="start", description="Start monitoring killfeed for a server")
    @app_commands.describe(server_id="The ID of the server to monitor")
    async def start(self, ctx, server_id: str):
        """Start the killfeed monitor for a server"""
        try:
            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                )
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
                    f"Server with ID {server_id} not found in this guild."
                )
                await ctx.send(embed=embed)
                return
            
            # Start killfeed monitor
            task_name = f"killfeed_{ctx.guild.id}_{server_id}"
            
            # Check if task is already running
            if task_name in self.bot.background_tasks:
                # If task exists but is done, remove it
                if self.bot.background_tasks[task_name].done():
                    self.bot.background_tasks.pop(task_name)
                else:
                    embed = EmbedBuilder.create_error_embed(
                        "Already Running",
                        f"Killfeed monitor for server {server_id} is already running."
                    )
                    await ctx.send(embed=embed)
                    return
            
            # Create initial response
            embed = EmbedBuilder.create_base_embed(
                "Starting Killfeed Monitor",
                f"Starting killfeed monitor for server {server_id}..."
            )
            message = await ctx.send(embed=embed)
            
            # Start the task
            task = asyncio.create_task(
                start_killfeed_monitor(self.bot, ctx.guild.id, server_id)
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
                "Killfeed Monitor Started",
                f"Killfeed monitor for server {server_id} has been started successfully."
            )
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error starting killfeed monitor: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while starting the killfeed monitor: {e}"
            )
            await ctx.send(embed=embed)
    
    @killfeed.command(name="stop", description="Stop monitoring killfeed for a server")
    @app_commands.describe(server_id="The ID of the server to stop monitoring")
    async def stop(self, ctx, server_id: str):
        """Stop the killfeed monitor for a server"""
        try:
            # Check permissions
            if not await self._check_permission(ctx):
                return
            
            # Check if task is running
            task_name = f"killfeed_{ctx.guild.id}_{server_id}"
            if task_name not in self.bot.background_tasks:
                embed = EmbedBuilder.create_error_embed(
                    "Not Running",
                    f"Killfeed monitor for server {server_id} is not running."
                )
                await ctx.send(embed=embed)
                return
            
            # Cancel the task
            task = self.bot.background_tasks[task_name]
            task.cancel()
            
            # Remove the task
            self.bot.background_tasks.pop(task_name)
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Killfeed Monitor Stopped",
                f"Killfeed monitor for server {server_id} has been stopped successfully."
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error stopping killfeed monitor: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while stopping the killfeed monitor: {e}"
            )
            await ctx.send(embed=embed)
    
    @killfeed.command(name="status", description="Check killfeed monitor status")
    async def status(self, ctx):
        """Check the status of killfeed monitors for this guild"""
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
            
            # Check running tasks for this guild
            running_monitors = []
            for task_name, task in self.bot.background_tasks.items():
                if task_name.startswith(f"killfeed_{ctx.guild.id}_"):
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
                    "Killfeed Monitor Status",
                    f"Currently running killfeed monitors for {ctx.guild.name}"
                )
                
                for monitor in running_monitors:
                    embed.add_field(
                        name=f"{monitor['server_name']} ({monitor['server_id']})",
                        value=f"Status: {monitor['status']}",
                        inline=False
                    )
            else:
                embed = EmbedBuilder.create_base_embed(
                    "Killfeed Monitor Status",
                    f"No killfeed monitors are currently running for {ctx.guild.name}."
                )
                
                # Add instructions
                embed.add_field(
                    name="How to Start",
                    value="Use `/killfeed start <server_id>` to start monitoring a server.",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking killfeed status: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while checking killfeed status: {e}"
            )
            await ctx.send(embed=embed)
    
    async def _check_permission(self, ctx) -> bool:
        """Check if user has permission to use the command"""
        # Check if user has admin permission
        if has_admin_permission(ctx):
            return True
        
        # If not, send error message
        embed = EmbedBuilder.create_error_embed(
            "Permission Denied",
            "You need administrator permission or the designated admin role to use this command."
        )
        await ctx.send(embed=embed, ephemeral=True)
        return False
    
    async def _handle_task_completion(self, task, guild_id, server_id, message):
        """Handle completion of a background task"""
        try:
            # Check if task was cancelled
            if task.cancelled():
                logger.info(f"Killfeed monitor for server {server_id} was cancelled.")
                return
            
            # Check if task completed with an exception
            if task.exception():
                logger.error(
                    f"Killfeed monitor for server {server_id} failed: {task.exception()}", 
                    exc_info=task.exception()
                )
                
                # Update message if still exists
                try:
                    embed = EmbedBuilder.create_error_embed(
                        "Killfeed Monitor Failed",
                        f"The killfeed monitor for server {server_id} has failed: {task.exception()}"
                    )
                    await message.edit(embed=embed)
                except:
                    pass
                
                return
            
            # Task completed normally
            logger.info(f"Killfeed monitor for server {server_id} completed successfully.")
            
        except Exception as e:
            logger.error(f"Error handling task completion: {e}", exc_info=True)


async def start_killfeed_monitor(bot, guild_id: int, server_id: str):
    """Background task to monitor killfeed for a server"""
    from config import KILLFEED_REFRESH_INTERVAL
    
    logger.info(f"Starting killfeed monitor for server {server_id} in guild {guild_id}")
    
    try:
        # Get server data
        server = await Server.get_by_id(bot.db, server_id, guild_id)
        if not server:
            logger.error(f"Server {server_id} not found in guild {guild_id}")
            return
        
        # Create SFTP client connection
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
        bot.sftp_connections[f"{guild_id}_{server_id}"] = sftp_client
        
        # Get killfeed channel
        guild = bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Guild {guild_id} not found")
            await sftp_client.disconnect()
            return
        
        killfeed_channel_id = server.killfeed_channel_id
        killfeed_channel = guild.get_channel(killfeed_channel_id)
        if not killfeed_channel:
            logger.error(f"Killfeed channel {killfeed_channel_id} not found in guild {guild_id}")
            await sftp_client.disconnect()
            return
        
        # Main monitoring loop
        while True:
            try:
                # Get latest CSV file
                latest_csv = await sftp_client.get_latest_csv_file()
                if not latest_csv:
                    logger.warning(f"No CSV file found for server {server_id}")
                    await asyncio.sleep(KILLFEED_REFRESH_INTERVAL)
                    continue
                
                # Get last processed line number
                last_line = server.last_csv_line
                
                # Get total lines in the file
                total_lines = await sftp_client.get_file_size(latest_csv)
                
                # If no new lines, sleep and continue
                if total_lines <= last_line:
                    await asyncio.sleep(KILLFEED_REFRESH_INTERVAL)
                    continue
                
                # Read new lines
                new_lines = await sftp_client.read_file(
                    latest_csv, 
                    start_line=last_line,
                    max_lines=None  # Read all new lines
                )
                
                if not new_lines:
                    await asyncio.sleep(KILLFEED_REFRESH_INTERVAL)
                    continue
                
                # Parse new lines
                kill_events = CSVParser.parse_kill_lines(new_lines)
                
                # Process each kill event
                for kill_event in kill_events:
                    await process_kill_event(bot, server, kill_event, killfeed_channel)
                
                # Update last processed line
                await server.update_last_csv_line(last_line + len(new_lines))
                
            except asyncio.CancelledError:
                logger.info(f"Killfeed monitor for server {server_id} cancelled")
                break
                
            except Exception as e:
                logger.error(f"Error in killfeed monitor for server {server_id}: {e}", exc_info=True)
            
            # Sleep before next check
            await asyncio.sleep(KILLFEED_REFRESH_INTERVAL)
        
    except asyncio.CancelledError:
        logger.info(f"Killfeed monitor for server {server_id} cancelled")
        
    except Exception as e:
        logger.error(f"Error in killfeed monitor for server {server_id}: {e}", exc_info=True)
        
    finally:
        # Clean up resources
        if f"{guild_id}_{server_id}" in bot.sftp_connections:
            client = bot.sftp_connections.pop(f"{guild_id}_{server_id}")
            await client.disconnect()
        
        logger.info(f"Killfeed monitor for server {server_id} stopped")


async def process_kill_event(bot, server, kill_event, channel):
    """Process a kill event and update the database"""
    try:
        # Create timestamp object if it's a string
        if isinstance(kill_event["timestamp"], str):
            kill_event["timestamp"] = datetime.fromisoformat(kill_event["timestamp"])
        
        # Add server_id to the event
        kill_event["server_id"] = server.id
        
        # Store in database
        await bot.db.kills.insert_one(kill_event)
        
        # Create embed for the kill
        embed = EmbedBuilder.create_kill_embed(kill_event)
        
        # Send to channel
        await channel.send(embed=embed)
        
        # Update player stats
        await update_player_stats(bot, server.id, kill_event)
        
    except Exception as e:
        logger.error(f"Error processing kill event: {e}", exc_info=True)


async def update_player_stats(bot, server_id, kill_event):
    """Update player statistics based on a kill event"""
    try:
        # Get or create killer player
        killer_data = {
            "player_id": kill_event["killer_id"],
            "player_name": kill_event["killer_name"],
            "server_id": server_id,
            "active": True
        }
        killer = await Player.create_or_update(bot.db, killer_data)
        
        # Get or create victim player
        victim_data = {
            "player_id": kill_event["victim_id"],
            "player_name": kill_event["victim_name"],
            "server_id": server_id,
            "active": True
        }
        victim = await Player.create_or_update(bot.db, victim_data)
        
        # Handle suicide case
        if kill_event["is_suicide"]:
            await victim.record_suicide(kill_event["suicide_type"])
        else:
            # Record kill for killer
            await killer.record_kill(
                victim_id=victim.id,
                victim_name=victim.name,
                weapon=kill_event["weapon"],
                distance=kill_event["distance"]
            )
            
            # Record death for victim
            await victim.record_death(
                killer_id=killer.id,
                killer_name=killer.name
            )
        
    except Exception as e:
        logger.error(f"Error updating player stats: {e}", exc_info=True)


async def setup(bot):
    """Set up the Killfeed cog"""
    await bot.add_cog(Killfeed(bot))
