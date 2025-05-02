"""
Premium features and management commands
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional

from models.guild import Guild
from utils.embed_builder import EmbedBuilder
from utils.helpers import is_home_guild_admin, has_admin_permission
from config import PREMIUM_TIERS, EMBED_THEMES

logger = logging.getLogger(__name__)

class Premium(commands.Cog):
    """Premium features and management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_group(name="premium", description="Premium management commands")
    @commands.guild_only()
    async def premium(self, ctx):
        """Premium command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @premium.command(name="status", description="Check premium status of this guild")
    async def status(self, ctx):
        """Check the premium status of this guild"""
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
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get guild object
            guild = Guild(self.bot.db, guild_data)
            
            # Create embed using guild model
            embed = EmbedBuilder.create_base_embed(
                f"Premium Status for {ctx.guild.name}",
                f"Current tier: **Tier {guild.premium_tier}**", 
                guild=guild)
            
            # Add tier information
            tier_info = PREMIUM_TIERS.get(guild.premium_tier, {})
            
            # Server slots
            max_servers = tier_info.get("max_servers", 1)
            current_servers = len(guild.servers)
            
            embed.add_field(
                name="Server Slots",
                value=f"{current_servers}/{max_servers} used",
                inline=True
            )
            
            # Features
            features = tier_info.get("features", [])
            feature_display = {
                "killfeed": "Killfeed",
                "events": "Events & Missions",
                "connections": "Player Connections",
                "stats": "Statistics & Leaderboards",
                "custom_embeds": "Custom Embeds"
            }
            
            feature_list = []
            for feature, display_name in feature_display.items():
                if feature in features:
                    feature_list.append(f"✅ {display_name}")
                else:
                    feature_list.append(f"❌ {display_name}")
            
            embed.add_field(
                name="Features",
                value="\n".join(feature_list),
                inline=False
            )
            
            # Add upgrade info
            if guild.premium_tier < 3:
                embed.add_field(
                    name="Upgrade",
                    value="To upgrade to a higher tier, please contact a bot administrator.",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking premium status: {e}", exc_info=True)
            # Get guild model for themed embed if possible
            try:
                guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while checking premium status: {e}",
                    guild=guild_model)
            except:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while checking premium status: {e}")
            await ctx.send(embed=embed)
    
    @premium.command(name="upgrade", description="Request a premium upgrade")
    async def upgrade(self, ctx):
        """Request a premium upgrade"""
        
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
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get guild object
            guild = Guild(self.bot.db, guild_data)
            
            # Check if already at max tier
            if guild.premium_tier >= 3:
                embed = EmbedBuilder.create_error_embed(
                    "Maximum Tier",
                    "This guild is already at the maximum premium tier."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get home guild
            home_guild = self.bot.get_guild(self.bot.home_guild_id)
            if not home_guild:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Could not find the home guild. Please contact the bot owner."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get admin channel in home guild
            admin_channel = None
            for channel in home_guild.text_channels:
                if channel.name.lower() in ["admin", "bot-admin", "premium-requests"]:
                    admin_channel = channel
                    break
            
            if not admin_channel:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Could not find an admin channel in the home guild. Please contact the bot owner directly."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create request embed
            request_embed = discord.Embed(
                title="Premium Upgrade Request",
                description=f"A guild has requested a premium upgrade.",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            request_embed.add_field(name="Guild Name", value=ctx.guild.name, inline=True)
            request_embed.add_field(name="Guild ID", value=str(ctx.guild.id), inline=True)
            request_embed.add_field(name="Current Tier", value=str(guild.premium_tier), inline=True)
            request_embed.add_field(name="Requested By", value=f"{ctx.author} ({ctx.author.id})", inline=True)
            
            # Add server count
            request_embed.add_field(name="Current Servers", value=str(len(guild.servers)), inline=True)
            
            # Add a way to contact the requester
            request_embed.add_field(
                name="Approve Command",
                value=f"`!admin premium {ctx.guild.id} {guild.premium_tier + 1}`",
                inline=False
            )
            
            # Send request to admin channel
            await admin_channel.send(embed=request_embed)
            
            # Send confirmation to user
            embed = EmbedBuilder.create_success_embed(
                "Request Sent",
                "Your premium upgrade request has been sent to the administrators. "
                "You will be notified once your request has been processed."
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error requesting premium upgrade: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while requesting a premium upgrade: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @premium.command(name="features", description="View available premium features")
    async def features(self, ctx):
        """View available premium features"""
        
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

            # Create embed
            embed = EmbedBuilder.create_base_embed(
                "Premium Features",
                "Overview of premium features by tier"
            , guild=guild_model)
            
            # Add tier information
            for tier, info in PREMIUM_TIERS.items():
                # Format features
                features = info.get("features", [])
                max_servers = info.get("max_servers", 0)
                
                feature_display = {
                    "killfeed": "Killfeed",
                    "events": "Events & Missions",
                    "connections": "Player Connections",
                    "stats": "Statistics & Leaderboards",
                    "custom_embeds": "Custom Embeds"
                }
                
                feature_list = []
                for feature, display_name in feature_display.items():
                    if feature in features:
                        feature_list.append(f"✅ {display_name}")
                    else:
                        feature_list.append(f"❌ {display_name}")
                
                # Add tier field
                tier_name = "Free" if tier == 0 else f"Premium Tier {tier}"
                embed.add_field(
                    name=f"{tier_name} ({max_servers} server slots)",
                    value="\n".join(feature_list),
                    inline=False
                )
            
            # Add upgrade info
            embed.add_field(
                name="How to Upgrade",
                value="Use `/premium upgrade` to request a premium upgrade.",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing premium features: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while showing premium features: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @premium.command(name="set", description="Set premium tier for a guild (admin only)")
    @app_commands.describe(
        guild_id="The ID of the guild to set premium for",
        tier="The premium tier to set (0-3)"
    )
    # Note: This command uses guild_id, not server_id, as it operates on guilds not servers
    async def set_premium(self, ctx, guild_id: str, tier: int):
        """Set premium tier for a guild (admin only)"""
        
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
            
            # Get admin guild model for themed embed
            admin_guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            admin_guild_model = None
            if admin_guild_data:
                admin_guild_model = Guild(self.bot.db, admin_guild_data)
            
            # Send success message
            embed = EmbedBuilder.create_success_embed(
                "Premium Tier Set",
                f"The premium tier for {guild_name} has been set to **Tier {tier}**.",
                guild=admin_guild_model)
            await ctx.send(embed=embed)
            
            # Try to notify the guild if possible
            if bot_guild:
                try:
                    # Find a suitable channel to send notification
                    channel = None
                    for ch in bot_guild.text_channels:
                        if ch.permissions_for(bot_guild.me).send_messages:
                            if ch.name.lower() in ["general", "bot", "bot-commands", "announcements"]:
                                channel = ch
                                break
                    
                    # If no preferred channel found, use the first one the bot can send to
                    if not channel:
                        for ch in bot_guild.text_channels:
                            if ch.permissions_for(bot_guild.me).send_messages:
                                channel = ch
                                break
                    
                    if channel:
                        # Use the target guild model for the notification embed
                        notify_embed = EmbedBuilder.create_success_embed(
                            "Premium Tier Updated",
                            f"Your guild's premium tier has been updated to **Tier {tier}**.",
                            guild=guild)
                        
                        # Add features info
                        features = PREMIUM_TIERS.get(tier, {}).get("features", [])
                        max_servers = PREMIUM_TIERS.get(tier, {}).get("max_servers", 0)
                        
                        feature_display = {
                            "killfeed": "Killfeed",
                            "events": "Events & Missions",
                            "connections": "Player Connections",
                            "stats": "Statistics & Leaderboards",
                            "custom_embeds": "Custom Embeds"
                        }
                        
                        feature_list = [f"✅ {feature_display[f]}" for f in features if f in feature_display]
                        
                        notify_embed.add_field(
                            name="Available Features",
                            value="\n".join(feature_list),
                            inline=False
                        )
                        
                        notify_embed.add_field(
                            name="Server Slots",
                            value=f"{len(guild.servers)}/{max_servers} used",
                            inline=True
                        )
                        
                        await channel.send(embed=notify_embed)
                
                except Exception as e:
                    logger.error(f"Error notifying guild about premium update: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error setting premium tier: {e}", exc_info=True)
            # Get guild model for themed embed if possible
            try:
                admin_guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while setting the premium tier: {e}",
                    guild=admin_guild_model)
            except:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while setting the premium tier: {e}")
            await ctx.send(embed=embed)


    @premium.command(name="theme", description="Set the theme for embed displays (Premium Tier 3+ only)")
    @app_commands.describe(
        theme="The theme to use for embeds"
    )
    @app_commands.choices(theme=[
        app_commands.Choice(name="Default", value="default"),
        app_commands.Choice(name="Midnight", value="midnight"),
        app_commands.Choice(name="Blood", value="blood"),
        app_commands.Choice(name="Gold", value="gold"),
        app_commands.Choice(name="Toxic", value="toxic"),
        app_commands.Choice(name="Ghost", value="ghost")
    ])
    async def set_theme(self, ctx, theme: str):
        """Set the theme for embed displays (Premium Tier 3+ only)"""
        try:
            # Check if user has admin permission
            if not has_admin_permission(ctx):
                # Get guild model for themed embed
                guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
                embed = EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "You need administrator permission or the designated admin role to use this command.",
                    guild=guild_model)
                await ctx.send(embed=embed, ephemeral=True)
                return
            
            # Get guild data
            guild = await Guild.get_by_id(self.bot.db, ctx.guild.id)
            if not guild:
                # No guild model, so we use default
                embed = EmbedBuilder.create_error_embed(
                    "Guild Not Set Up",
                    "This guild is not set up. Please add a server first.")
                await ctx.send(embed=embed)
                return
            
            # Check premium tier
            if not guild.check_feature_access("custom_embeds"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Custom themes are only available for Premium Tier 3 guilds.",
                    guild=guild)
                await ctx.send(embed=embed)
                return
            
            # Check if theme exists
            from config import EMBED_THEMES
            if theme != "default" and theme not in EMBED_THEMES:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Theme",
                    f"The theme '{theme}' does not exist.",
                    guild=guild)
                await ctx.send(embed=embed)
                return
            
            # Set theme
            success = await guild.set_theme(theme)
            if not success:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "Failed to set theme. Please try again later.",
                    guild=guild)
                await ctx.send(embed=embed)
                return
            
            # Create preview embed with new theme
            embed = EmbedBuilder.create_base_embed(
                "Theme Set Successfully",
                f"Your guild's theme has been set to **{EMBED_THEMES[theme]['name']}**. All embeds will now use this theme.",
                guild=guild
            )
            
            embed.add_field(
                name="Preview",
                value="This is a preview of your new theme.",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting theme: {e}", exc_info=True)
            # Get guild model for themed embed
            try:
                guild_model = await Guild.get_by_id(self.bot.db, ctx.guild.id)
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while setting the theme: {e}",
                    guild=guild_model)
            except:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    f"An error occurred while setting the theme: {e}")
            await ctx.send(embed=embed)

async def setup(bot):
    """Set up the Premium cog"""
    await bot.add_cog(Premium(bot))
