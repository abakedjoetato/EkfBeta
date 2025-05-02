"""
Admin commands for bot management
"""
import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from models.guild import Guild
from utils.embed_builder import EmbedBuilder
from utils.helpers import is_home_guild_admin

logger = logging.getLogger(__name__)

class Admin(commands.Cog):
    """Admin commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="admin", description="Admin commands")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def admin(self, ctx):
        """Admin command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @admin.command(name="setrole", description="Set the admin role for server management")
    @app_commands.describe(role="The role to set as admin")
    async def setrole(self, ctx, role: discord.Role):
        """Set the admin role for server management"""
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
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                guild = await Guild.create(self.bot.db, ctx.guild.id, ctx.guild.name)
            
            # Set admin role
            await guild.set_admin_role(role.id)
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Admin Role Set",
                f"The {role.mention} role has been set as the admin role for server management."
            , guild=guild_model)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting admin role: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while setting the admin role: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @admin.command(name="premium", description="Set the premium tier for a guild")
    @app_commands.describe(
        guild_id="The ID of the guild to set premium for",
        tier="The premium tier to set (0-3)"
    )
    # Note: This command uses guild_id, not server_id, as it operates on guilds not servers
    async def premium(self, ctx, guild_id: str, tier: int):
        """Set the premium tier for a guild (Home Guild Admins only)"""
        
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

            # Check if user is a home guild admin
            if not is_home_guild_admin(self.bot, ctx.author.id):
                embed = EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only home guild administrators can use this command."
                , guild=guild_model)
                await ctx.send(embed=embed, ephemeral=True)
                return
            
            # Validate tier
            if tier < 0 or tier > 3:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Tier",
                    "Premium tier must be between 0 and 3."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Convert guild ID to int
            try:
                guild_id_int = int(guild_id)
            except ValueError:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Guild ID",
                    "Guild ID must be a valid integer."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get guild data
            guild = await Guild.get_by_id(self.bot.db, guild_id_int)
            if not guild:
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Found",
                    f"Could not find a guild with ID {guild_id}."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Set premium tier
            await guild.set_premium_tier(tier)
            
            # Get guild name from bot
            bot_guild = self.bot.get_guild(guild_id_int)
            guild_name = bot_guild.name if bot_guild else f"Guild {guild_id}"
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Premium Tier Set",
                f"The premium tier for {guild_name} has been set to **Tier {tier}**."
            , guild=guild_model)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting premium tier: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while setting the premium tier: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @admin.command(name="status", description="View bot status information")
    async def status(self, ctx):
        """View bot status information"""
        
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

            # Get basic statistics
            guild_count = len(self.bot.guilds)
            
            # Count servers across all guilds
            server_count = 0
            player_count = 0
            kill_count = 0
            
            pipeline = [
                {"$unwind": "$servers"},
                {"$count": "server_count"}
            ]
            server_result = await self.bot.db.guilds.aggregate(pipeline).to_list(length=1)
            if server_result:
                server_count = server_result[0].get("server_count", 0)
            
            player_count = await self.bot.db.players.count_documents({})
            kill_count = await self.bot.db.kills.count_documents({})
            
            # Create embed
            embed = EmbedBuilder.create_base_embed(
                "Bot Status",
                "Current statistics and performance information"
            , guild=guild_model)
            
            # Add statistics fields
            embed.add_field(name="Guilds", value=str(guild_count), inline=True)
            embed.add_field(name="Servers", value=str(server_count), inline=True)
            embed.add_field(name="Players", value=str(player_count), inline=True)
            embed.add_field(name="Kills Tracked", value=str(kill_count), inline=True)
            
            # Add uptime if available
            import time
            if hasattr(self.bot, "start_time"):
                uptime = time.time() - self.bot.start_time
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                embed.add_field(
                    name="Uptime",
                    value=f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
                    inline=True
                )
            
            # Add background tasks info
            task_count = len(self.bot.background_tasks)
            embed.add_field(name="Background Tasks", value=str(task_count), inline=True)
            
            # Send embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting status: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting bot status: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @admin.command(name="sethomeguild", description="Set the home guild for the bot")
    async def sethomeguild(self, ctx):
        """Set the current guild as the home guild (Bot Owner only)"""
        
        # First, defer the response to avoid timeouts
        if hasattr(ctx, 'interaction') and ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=False)
            is_deferred = True
        else:
            is_deferred = False
            
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

            # Check if user is the bot owner
            if ctx.author.id != self.bot.owner_id:
                embed = EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the bot owner can use this command."
                , guild=guild_model)
                
                if is_deferred and hasattr(ctx.interaction, 'followup'):
                    await ctx.interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed, ephemeral=True)
                return
            
            # Set home guild
            self.bot.home_guild_id = ctx.guild.id
            
            # Store in environment variable for current session
            os.environ["HOME_GUILD_ID"] = str(ctx.guild.id)
            
            # Update the .env file for persistence across restarts
            try:
                with open(".env", "r") as f:
                    lines = f.readlines()
                
                with open(".env", "w") as f:
                    for line in lines:
                        if line.startswith("HOME_GUILD_ID="):
                            f.write(f"HOME_GUILD_ID={str(ctx.guild.id)}\n")
                        else:
                            f.write(line)
                            
                logger.info(f"Updated .env file with new home guild ID: {ctx.guild.id}")
            except Exception as env_error:
                logger.error(f"Failed to update .env file: {env_error}", exc_info=True)
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Home Guild Set",
                f"This guild ({ctx.guild.name}) has been set as the home guild for the bot."
            , guild=guild_model)
            
            if is_deferred and hasattr(ctx.interaction, 'followup'):
                await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.send(embed=embed)
                
            logger.info(f"Home guild set to {ctx.guild.name} (ID: {ctx.guild.id}) by owner")
            
        except Exception as e:
            logger.error(f"Error setting home guild: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while setting the home guild: {e}"
            , guild=guild_model)
            
            if is_deferred and hasattr(ctx.interaction, 'followup'):
                await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.send(embed=embed)
            

    
    @admin.command(name="help", description="Show help for admin commands")
    async def admin_help(self, ctx):
        """Show help for admin commands"""
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
            "Admin Commands Help",
            "List of available admin commands and their usage"
        , guild=guild_model)
        
        # Add command descriptions
        embed.add_field(
            name="`/admin setrole <role>`",
            value="Set the admin role for server management",
            inline=False
        )
        
        embed.add_field(
            name="`/admin premium <guild_id> <tier>`",
            value="Set the premium tier for a guild (Home Guild Admins only)",
            inline=False
        )
        
        embed.add_field(
            name="`/admin sethomeguild`",
            value="Set the current guild as the home guild (Bot Owner only)",
            inline=False
        )
        
        embed.add_field(
            name="`/admin status`",
            value="View bot status information",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    """Set up the Admin cog"""
    await bot.add_cog(Admin(bot))
