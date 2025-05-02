"""Help commands for displaying bot documentation and command usage"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.embed_builder import EmbedBuilder
from models.guild import Guild
from utils.helpers import is_feature_enabled, get_guild_premium_tier, has_admin_permission


class CommandSelect(discord.ui.Select):
    """Dropdown select for command categories"""
    
    def __init__(self, bot, author_id: int, guild_id: int):
        self.bot = bot
        self.author_id = author_id
        self.guild_id = guild_id
        
        # Define command categories
        options = [
            discord.SelectOption(label="Admin", description="Server administration commands", emoji="🛡️"),
            discord.SelectOption(label="Setup", description="Server setup and configuration", emoji="⚙️"),
            discord.SelectOption(label="Killfeed", description="Killfeed monitoring commands", emoji="☠️"),
            discord.SelectOption(label="Events", description="Server events monitoring", emoji="🔔"),
            discord.SelectOption(label="Stats", description="Player and server statistics", emoji="📊"),
            discord.SelectOption(label="Economy", description="Economy and gambling features", emoji="💰"),
            discord.SelectOption(label="Premium", description="Premium features and upgrades", emoji="✨"),
        ]
        
        super().__init__(placeholder="Select a category", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        # Only allow the original command user to use the dropdown
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
            
        # Get the guild model for theme
        guild_model = await Guild.get_by_id(self.bot.db, self.guild_id)
        
        # Create help embed based on selection
        category = self.values[0]
        embed = await self.create_category_embed(category, guild_model)
        
        await interaction.response.edit_message(embed=embed, view=self.view)
    
    async def create_category_embed(self, category: str, guild_model):
        """Create help embed for the selected category"""
        
        if category == "Admin":
            title = "🛡️ Admin Commands"
            description = "Server administration commands"
            fields = [
                {"name": "/admin setrole", "value": "Set the admin role for server management", "inline": False},
                {"name": "/admin premium", "value": "Set premium tier for a guild (Home Guild Admins only)", "inline": False},
                {"name": "/admin status", "value": "View bot status information", "inline": False},
                {"name": "/admin sethomeguild", "value": "Set the current guild as the home guild (Bot Owner only)", "inline": False},
                {"name": "/admin help", "value": "Show help for admin commands", "inline": False},
            ]
        
        elif category == "Setup":
            title = "⚙️ Setup Commands"
            description = "Server setup and configuration commands"
            fields = [
                {"name": "/setup add_server <name> <host> <port> <user> <pass> <id>", "value": "Add a new server to track", "inline": False},
                {"name": "/setup remove_server <server>", "value": "Remove a server from tracking", "inline": False},
                {"name": "/setup channels <server> [channels...]", "value": "Configure notification channels for a server", "inline": False},
                {"name": "/setup list_servers", "value": "List all configured servers for this guild", "inline": False},
                {"name": "/setup historical_parse <server>", "value": "Parse all historical data for a server", "inline": False},
            ]
        
        elif category == "Killfeed":
            title = "☠️ Killfeed Commands"
            description = "Killfeed monitoring commands"
            fields = [
                {"name": "/killfeed start <server>", "value": "Start the killfeed monitor for a server", "inline": False},
                {"name": "/killfeed stop <server>", "value": "Stop the killfeed monitor for a server", "inline": False},
                {"name": "/killfeed status", "value": "Check the status of killfeed monitors for this guild", "inline": False},
            ]
            
        elif category == "Events":
            title = "🔔 Events Commands"
            description = "Server events monitoring commands"
            fields = [
                {"name": "/events start <server>", "value": "Start the events monitor for a server", "inline": False},
                {"name": "/events stop <server>", "value": "Stop the events monitor for a server", "inline": False},
                {"name": "/events status", "value": "Check the status of events monitors for this guild", "inline": False},
                {"name": "/events list_events <server> [type] [limit]", "value": "List recent events for a server", "inline": False},
                {"name": "/events online_players <server>", "value": "List online players for a server", "inline": False},
                {"name": "/events configure_events <server> [options]", "value": "Configure which event notifications are enabled", "inline": False},
                {"name": "/events configure_connections <server> [options]", "value": "Configure which connection notifications are enabled", "inline": False},
                {"name": "/events configure_suicides <server> [options]", "value": "Configure which suicide notifications are enabled", "inline": False},
            ]
            
        elif category == "Stats":
            title = "📊 Stats Commands"
            description = "Player and server statistics commands"
            premium_note = "\n\n**Note:** Requires Premium Tier 2 or higher"
            description += premium_note
            fields = [
                {"name": "/stats player <server> <player>", "value": "View statistics for a player", "inline": False},
                {"name": "/stats server <server>", "value": "View statistics for a server", "inline": False},
                {"name": "/stats leaderboard <server> <stat>", "value": "View leaderboards for a specific stat", "inline": False},
                {"name": "/stats weapon_categories <server>", "value": "View statistics by weapon category", "inline": False},
                {"name": "/stats weapon <server> <weapon>", "value": "View statistics for a specific weapon", "inline": False},
            ]
            
        elif category == "Economy":
            title = "💰 Economy Commands"
            description = "Economy and gambling features"
            premium_note = "\n\n**Note:** Basic economy requires Premium Tier 1, gambling requires Premium Tier 2"
            description += premium_note
            fields = [
                {"name": "/economy balance <server>", "value": "Check your balance", "inline": False},
                {"name": "/economy daily <server>", "value": "Claim your daily reward", "inline": False},
                {"name": "/economy leaderboard <server>", "value": "View the richest players", "inline": False},
                {"name": "/economy give <server> <user> <amount>", "value": "Give credits to another player", "inline": False},
                {"name": "/gambling blackjack <server> [bet]", "value": "Play blackjack (Premium Tier 2+)", "inline": False},
                {"name": "/gambling slots <server> [bet]", "value": "Play slots (Premium Tier 2+)", "inline": False},
            ]
            
        elif category == "Premium":
            title = "✨ Premium Commands"
            description = "Premium features and management commands"
            fields = [
                {"name": "/premium status", "value": "Check the premium status of this guild", "inline": False},
                {"name": "/premium upgrade", "value": "Request a premium upgrade", "inline": False},
                {"name": "/premium features", "value": "View available premium features", "inline": False},
                {"name": "/premium set_theme", "value": "Set the theme for embed displays (Premium Tier 3+ only)", "inline": False},
            ]
            # Add premium tiers information
            fields.append({"name": "Premium Tiers", "value": "**Free**: Basic commands\n**Tier 1 ($)**: Economy, Events\n**Tier 2 ($$)**: Statistics, Gambling\n**Tier 3 ($$$)**: Custom Themes", "inline": False})
        
        else:
            # Default fallback
            title = "Bot Commands"
            description = "Use the dropdown to view different command categories"
            fields = []
        
        # Create embed
        embed = EmbedBuilder.create_base_embed(
            title=title,
            description=description,
            guild=guild_model
        )
        
        # Add fields
        for field in fields:
            embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))
        
        # Add footer
        embed.set_footer(text="Use /commands to see this help menu again")
        
        return embed


class CommandsView(discord.ui.View):
    """View with select dropdown for command categories"""
    
    def __init__(self, bot, author_id: int, guild_id: int):
        super().__init__(timeout=600)  # 10 minute timeout
        
        # Add the select menu
        self.add_item(CommandSelect(bot, author_id, guild_id))


class Help(commands.Cog):
    """Help commands for displaying bot documentation and command usage"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="commands", description="View comprehensive help for all bot commands")
    async def commands(self, interaction: discord.Interaction):
        """Displays a comprehensive help system with all available commands"""
        
        # Defer the response to avoid timeout
        await interaction.response.defer(ephemeral=False, thinking=True)
        
        # Get the guild model for theme
        guild_model = await Guild.get_by_id(self.bot.db, interaction.guild.id)
        
        # Create initial embed
        embed = EmbedBuilder.create_base_embed(
            title="Tower of Temptation Commands",
            description="Use the dropdown menu below to navigate through different command categories.",
            guild=guild_model
        )
        
        # Add general info fields
        embed.add_field(
            name="Getting Started",
            value="1️⃣ Use `/setup add_server <name> <host> <port> <user> <pass> <id>` to add a server\n2️⃣ Configure channels with `/setup channels <server>`\n3️⃣ Start monitoring with `/killfeed start <server>` and `/events start <server>`",
            inline=False
        )
        
        # Add premium tip
        embed.add_field(
            name="Premium Features",
            value="Upgrade to premium for advanced statistics, economy features, and custom themes. Use `/premium features` to learn more.",
            inline=False
        )
        
        # Add footer
        embed.set_footer(text="Select a category to see detailed command information")
        
        # Create and send view with dropdown
        view = CommandsView(self.bot, interaction.user.id, interaction.guild.id)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    """Set up the Help cog"""
    await bot.add_cog(Help(bot))
