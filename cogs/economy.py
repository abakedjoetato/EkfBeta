"""
Economy commands and gambling features
"""
import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import random
from datetime import datetime

from models.economy import Economy
from models.guild import Guild
from utils.embed_builder import EmbedBuilder
from utils.gambling import BlackjackGame, BlackjackView, SlotsView

logger = logging.getLogger(__name__)

# Autocomplete function for server IDs
async def server_id_autocomplete(interaction, current):
    """Autocomplete for server IDs"""
    try:
        # Get guild model for themed embed
        guild_data = None
        guild_model = None
        try:
            guild_data = await interaction.client.db.guilds.find_one({"guild_id": interaction.guild_id})
            if guild_data:
                guild_model = Guild(interaction.client.db, guild_data)
        except Exception as e:
            logger.warning(f"Error getting guild model: {e}")

        # Get user's guild ID
        guild_id = interaction.guild_id
        
        # Get cached server data or fetch it
        cog = interaction.client.get_cog("Economy")
        if not cog:
            cog = interaction.client.get_cog("Stats")  # Fallback to Stats cog cache
        
        if not cog or not hasattr(cog, "server_autocomplete_cache"):
            return [app_commands.Choice(name="Error loading servers", value="error")]
        
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

class Economy(commands.Cog):
    """Economy commands and gambling features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.server_autocomplete_cache = {}
        self.active_games = {}
    
    @commands.hybrid_group(name="economy", description="Economy commands")
    @commands.guild_only()
    async def economy(self, ctx):
        """Economy command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @economy.command(name="balance", description="Check your balance")
    @app_commands.describe(server_id="Select a server by name to check balance for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def balance(self, ctx, server_id: str):
        """Check your balance"""
        try:
            # Get guild data
            guild_data = await self.bot.db.guilds.find_one({"guild_id": ctx.guild.id})
            if not guild_data:
                embed = EmbedBuilder.create_error_embed(
                    "Error",
                    "This guild is not set up. Please use the setup commands first."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if the guild has access to economy feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("economy"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Economy features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get player data
            player_id = str(ctx.author.id)
            economy = await Economy.get_by_player(self.bot.db, player_id, server_id)
            
            if not economy:
                # Create new economy account
                economy = await Economy.create_or_update(self.bot.db, player_id, server_id)
            
            # Get player balance
            balance = await economy.get_balance()
            lifetime = economy.lifetime_earnings
            
            # Create embed
            embed = discord.Embed(
                title="💰 Your Balance",
                description=f"Server: {server_name}",
                color=discord.Color.gold()
            )
            
            embed.add_field(name="Balance", value=f"{balance} credits", inline=True)
            embed.add_field(name="Lifetime Earnings", value=f"{lifetime} credits", inline=True)
            
            # Get gambling stats
            gambling_stats = await economy.get_gambling_stats()
            if gambling_stats:
                blackjack_stats = gambling_stats.get("blackjack", {})
                slots_stats = gambling_stats.get("slots", {})
                
                blackjack_wins = blackjack_stats.get("wins", 0)
                blackjack_losses = blackjack_stats.get("losses", 0)
                blackjack_earnings = blackjack_stats.get("earnings", 0)
                
                slots_wins = slots_stats.get("wins", 0)
                slots_losses = slots_stats.get("losses", 0)
                slots_earnings = slots_stats.get("earnings", 0)
                
                # Add gambling stats to embed
                if blackjack_wins > 0 or blackjack_losses > 0:
                    embed.add_field(
                        name="Blackjack Stats",
                        value=f"Wins: {blackjack_wins}, Losses: {blackjack_losses}\nNet Earnings: {blackjack_earnings} credits",
                        inline=False
                    )
                
                if slots_wins > 0 or slots_losses > 0:
                    embed.add_field(
                        name="Slots Stats",
                        value=f"Wins: {slots_wins}, Losses: {slots_losses}\nNet Earnings: {slots_earnings} credits",
                        inline=False
                    )
            
            embed.set_footer(text=f"User ID: {player_id}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting your balance: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @economy.command(name="daily", description="Claim your daily reward")
    @app_commands.describe(server_id="Select a server by name to claim daily reward for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def daily(self, ctx, server_id: str):
        """Claim your daily reward"""
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
            
            # Check if the guild has access to economy feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("economy"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Economy features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get player data
            player_id = str(ctx.author.id)
            economy = await Economy.get_by_player(self.bot.db, player_id, server_id)
            
            if not economy:
                # Create new economy account
                economy = await Economy.create_or_update(self.bot.db, player_id, server_id)
            
            # Calculate daily reward based on premium tier
            daily_amount = 100
            premium_tier = guild_data.get("premium_tier", 0)
            if premium_tier >= 2:
                daily_amount = 150
            if premium_tier >= 3:
                daily_amount = 200
            
            # Claim daily reward
            success, message = await economy.claim_daily(daily_amount)
            
            if success:
                embed = discord.Embed(
                    title="💰 Daily Reward",
                    description=message,
                    color=discord.Color.green()
                )
                
                # Get new balance
                balance = await economy.get_balance()
                embed.add_field(name="New Balance", value=f"{balance} credits", inline=False)
            else:
                embed = discord.Embed(
                    title="❌ Daily Reward",
                    description=message,
                    color=discord.Color.red()
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error claiming daily reward: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while claiming your daily reward: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @economy.command(name="leaderboard", description="View the richest players")
    @app_commands.describe(server_id="Select a server by name to check leaderboard for")
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def leaderboard(self, ctx, server_id: str):
        """View the richest players"""
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
            
            # Check if the guild has access to economy feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("economy"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Economy features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get richest players
            richest_players = await Economy.get_richest_players(self.bot.db, server_id, 10)
            
            if not richest_players:
                embed = EmbedBuilder.create_error_embed(
                    "No Data",
                    f"No player economy data found for server {server_name}."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create embed
            embed = discord.Embed(
                title="💰 Richest Players",
                description=f"Server: {server_name}",
                color=discord.Color.gold()
            )
            
            # Add leaderboard entries
            leaderboard_str = ""
            for i, player in enumerate(richest_players):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                player_name = player.get("player_name", "Unknown Player")
                currency = player.get("currency", 0)
                lifetime = player.get("lifetime_earnings", 0)
                
                leaderboard_str += f"{medal} **{player_name}**: {currency} credits (Lifetime: {lifetime})\n"
            
            embed.description = leaderboard_str
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while getting the leaderboard: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @commands.hybrid_group(name="gambling", description="Gambling commands")
    @commands.guild_only()
    async def gambling(self, ctx):
        """Gambling command group"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")
    
    @gambling.command(name="blackjack", description="Play blackjack")
    @app_commands.describe(
        server_id="Select a server by name to play on",
        bet="The amount to bet (default: 10)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def blackjack(self, ctx, server_id: str, bet: int = 10):
        """Play blackjack"""
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
            
            # Check if the guild has access to gambling feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("gambling"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Gambling features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Validate bet
            if bet <= 0:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Bet",
                    "Bet must be greater than 0."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get player data
            player_id = str(ctx.author.id)
            economy = await Economy.get_by_player(self.bot.db, player_id, server_id)
            
            if not economy:
                # Create new economy account
                economy = await Economy.create_or_update(self.bot.db, player_id, server_id)
            
            # Check if player has enough credits
            balance = await economy.get_balance()
            if balance < bet:
                embed = EmbedBuilder.create_error_embed(
                    "Insufficient Funds",
                    f"You don't have enough credits. You need {bet} credits to play."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Remove the bet amount
            await economy.remove_currency(bet, "blackjack_bet")
            
            # Start blackjack game
            game = BlackjackGame(player_id)
            game_state = game.start_game(bet)
            
            # Create embed
            from utils.gambling import create_blackjack_embed
            embed = create_blackjack_embed(game_state)
            
            # Check for natural blackjack
            if game_state["game_over"]:
                payout = game.get_payout()
                
                # Update player economy
                if payout > 0:
                    await economy.add_currency(payout, "blackjack", {"game": "blackjack", "result": game.result})
                    await economy.update_gambling_stats("blackjack", True, payout)
                    embed.add_field(name="Payout", value=f"You won {payout} credits!", inline=False)
                elif payout < 0:
                    await economy.update_gambling_stats("blackjack", False, abs(payout))
                    embed.add_field(name="Loss", value=f"You lost {abs(payout)} credits.", inline=False)
                else:  # push
                    embed.add_field(name="Push", value=f"Your bet of {bet} credits has been returned.", inline=False)
                
                new_balance = await economy.get_balance()
                embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=False)
                
                await ctx.send(embed=embed)
            else:
                # Create view with buttons
                view = BlackjackView(game, economy)
                message = await ctx.send(embed=embed, view=view)
                
                # Store the game data
                game.message = message
                game_key = f"{ctx.guild.id}_{player_id}_blackjack"
                self.active_games[game_key] = game
            
        except Exception as e:
            logger.error(f"Error playing blackjack: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while playing blackjack: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @gambling.command(name="slots", description="Play slots")
    @app_commands.describe(
        server_id="Select a server by name to play on",
        bet="The amount to bet (default: 10)"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def slots(self, ctx, server_id: str, bet: int = 10):
        """Play slots"""
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
            
            # Check if the guild has access to gambling feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("gambling"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Gambling features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Validate bet
            if bet <= 0:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Bet",
                    "Bet must be greater than 0."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get player data
            player_id = str(ctx.author.id)
            economy = await Economy.get_by_player(self.bot.db, player_id, server_id)
            
            if not economy:
                # Create new economy account
                economy = await Economy.create_or_update(self.bot.db, player_id, server_id)
            
            # Check if player has enough credits
            balance = await economy.get_balance()
            if balance < bet:
                embed = EmbedBuilder.create_error_embed(
                    "Insufficient Funds",
                    f"You don't have enough credits. You need {bet} credits to play."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Create slots view
            view = SlotsView(player_id, economy, bet)
            
            # Create initial embed
            embed = discord.Embed(
                title="🎰 Slot Machine 🎰",
                description=f"Ready to play! Bet: {bet} credits",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Instructions", value="Click 'Spin' to start playing", inline=False)
            embed.add_field(name="Your Balance", value=f"{balance} credits", inline=False)
            
            await ctx.send(embed=embed, view=view)
            
            game_key = f"{ctx.guild.id}_{player_id}_slots"
            self.active_games[game_key] = view
            
        except Exception as e:
            logger.error(f"Error playing slots: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while playing slots: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)
    
    @economy.command(name="give", description="Give credits to another player")
    @app_commands.describe(
        server_id="Select a server by name",
        user="The user to give credits to",
        amount="The amount to give"
    )
    @app_commands.autocomplete(server_id=server_id_autocomplete)
    async def give(self, ctx, server_id: str, user: discord.Member, amount: int):
        """Give credits to another player"""
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
            
            # Check if the guild has access to economy feature
            guild = Guild(self.bot.db, guild_data)
            if not guild.check_feature_access("economy"):
                embed = EmbedBuilder.create_error_embed(
                    "Premium Feature",
                    "Economy features are premium features. Please upgrade to access this feature."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Find the server
            server = None
            server_name = server_id
            for s in guild_data.get("servers", []):
                if s.get("server_id") == server_id:
                    server = s
                    server_name = s.get("server_name", server_id)
                    break
            
            if not server:
                embed = EmbedBuilder.create_error_embed(
                    "Server Not Found",
                    f"Server with ID {server_id} not found in this guild."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Validate amount
            if amount <= 0:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Amount",
                    "Amount must be greater than 0."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Check if giving to self
            if ctx.author.id == user.id:
                embed = EmbedBuilder.create_error_embed(
                    "Invalid Recipient",
                    "You can't give credits to yourself."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get player data
            player_id = str(ctx.author.id)
            player_economy = await Economy.get_by_player(self.bot.db, player_id, server_id)
            
            if not player_economy:
                # Create new economy account
                player_economy = await Economy.create_or_update(self.bot.db, player_id, server_id)
            
            # Check if player has enough credits
            balance = await player_economy.get_balance()
            if balance < amount:
                embed = EmbedBuilder.create_error_embed(
                    "Insufficient Funds",
                    f"You don't have enough credits. You have {balance} credits."
                , guild=guild_model)
                await ctx.send(embed=embed)
                return
            
            # Get recipient data
            recipient_id = str(user.id)
            recipient_economy = await Economy.get_by_player(self.bot.db, recipient_id, server_id)
            
            if not recipient_economy:
                # Create new economy account for recipient
                recipient_economy = await Economy.create_or_update(self.bot.db, recipient_id, server_id)
            
            # Transfer credits
            await player_economy.remove_currency(amount, "transfer", {"recipient_id": recipient_id, "recipient_name": user.name})
            await recipient_economy.add_currency(amount, "received", {"sender_id": player_id, "sender_name": ctx.author.name})
            
            # Create embed
            embed = discord.Embed(
                title="💸 Credits Transfer",
                description=f"Successfully transferred {amount} credits to {user.mention}",
                color=discord.Color.green()
            )
            
            # Get new balances
            player_new_balance = await player_economy.get_balance()
            embed.add_field(name="Your New Balance", value=f"{player_new_balance} credits", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error giving credits: {e}", exc_info=True)
            embed = EmbedBuilder.create_error_embed(
                "Error",
                f"An error occurred while giving credits: {e}"
            , guild=guild_model)
            await ctx.send(embed=embed)

async def setup(bot):
    """Set up the Economy cog"""
    # Import here to avoid circular import
    from datetime import datetime
    await bot.add_cog(Economy(bot))