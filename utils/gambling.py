"""
Gambling utilities for blackjack and slots games
"""
import random
import asyncio
from enum import Enum, auto
from typing import List, Dict, Any, Tuple, Optional
import discord
from discord.ui import View, Button
from discord import ButtonStyle

class CardSuit(Enum):
    HEARTS = auto()
    DIAMONDS = auto()
    CLUBS = auto()
    SPADES = auto()

class Card:
    def __init__(self, suit: CardSuit, value: int):
        self.suit = suit
        self.value = value
    
    @property
    def display_value(self) -> str:
        if self.value == 1:
            return "A"
        elif self.value == 11:
            return "J"
        elif self.value == 12:
            return "Q"
        elif self.value == 13:
            return "K"
        else:
            return str(self.value)
    
    @property
    def blackjack_value(self) -> int:
        if self.value == 1:
            return 11  # Ace is 11 by default, can be 1 if needed
        elif self.value >= 10:
            return 10  # Face cards are worth 10
        else:
            return self.value
    
    @property
    def emoji(self) -> str:
        """Return the card emoji"""
        suits = {
            CardSuit.HEARTS: "♥️",
            CardSuit.DIAMONDS: "♦️",
            CardSuit.CLUBS: "♣️",
            CardSuit.SPADES: "♠️"
        }
        return f"{suits[self.suit]}{self.display_value}"

class Deck:
    def __init__(self):
        self.cards = []
        self.reset()
    
    def reset(self):
        """Reset the deck with all 52 cards"""
        self.cards = []
        for suit in CardSuit:
            for value in range(1, 14):
                self.cards.append(Card(suit, value))
        self.shuffle()
    
    def shuffle(self):
        """Shuffle the deck"""
        random.shuffle(self.cards)
    
    def deal(self) -> Card:
        """Deal a card from the deck"""
        if not self.cards:
            self.reset()
        return self.cards.pop()

class BlackjackGame:
    def __init__(self, player_id: str):
        self.player_id = player_id
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.bet = 0
        self.result = ""
        self.message = None
    
    def start_game(self, bet: int):
        """Start a new game of blackjack"""
        self.bet = bet
        self.player_hand = [self.deck.deal(), self.deck.deal()]
        self.dealer_hand = [self.deck.deal(), self.deck.deal()]
        self.game_over = False
        self.result = ""
        return self.get_game_state()
    
    def get_game_state(self, reveal_dealer: bool = False) -> Dict[str, Any]:
        """Get the current game state"""
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        # Check if player has blackjack
        player_blackjack = len(self.player_hand) == 2 and player_value == 21
        dealer_blackjack = len(self.dealer_hand) == 2 and dealer_value == 21
        
        # Determine if game is over (natural blackjack)
        if player_blackjack or dealer_blackjack:
            self.game_over = True
            if player_blackjack and dealer_blackjack:
                self.result = "push"
            elif player_blackjack:
                self.result = "blackjack"
            elif dealer_blackjack:
                self.result = "dealer_blackjack"
        
        return {
            "player_hand": self.player_hand,
            "dealer_hand": self.dealer_hand if reveal_dealer else [self.dealer_hand[0]],
            "player_value": player_value,
            "dealer_value": dealer_value if reveal_dealer else self.dealer_hand[0].blackjack_value,
            "game_over": self.game_over,
            "result": self.result,
            "bet": self.bet,
            "reveal_dealer": reveal_dealer,
            "player_blackjack": player_blackjack,
            "dealer_blackjack": dealer_blackjack
        }
    
    def calculate_hand_value(self, hand: List[Card]) -> int:
        """Calculate the value of a hand, accounting for aces"""
        value = 0
        aces = 0
        
        for card in hand:
            if card.value == 1:  # Ace
                aces += 1
                value += 11
            else:
                value += card.blackjack_value
        
        # Adjust for aces if over 21
        while value > 21 and aces > 0:
            value -= 10  # Convert an ace from 11 to 1
            aces -= 1
        
        return value
    
    def hit(self) -> Dict[str, Any]:
        """Player takes another card"""
        if self.game_over:
            return self.get_game_state(True)
        
        self.player_hand.append(self.deck.deal())
        player_value = self.calculate_hand_value(self.player_hand)
        
        if player_value > 21:
            self.game_over = True
            self.result = "bust"
        
        return self.get_game_state()
    
    def stand(self) -> Dict[str, Any]:
        """Player stands, dealer plays"""
        if self.game_over:
            return self.get_game_state(True)
        
        self.game_over = True
        
        # Dealer draws until 17 or higher
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        while dealer_value < 17:
            self.dealer_hand.append(self.deck.deal())
            dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        player_value = self.calculate_hand_value(self.player_hand)
        
        if dealer_value > 21:
            self.result = "dealer_bust"
        elif dealer_value > player_value:
            self.result = "dealer_wins"
        elif dealer_value < player_value:
            self.result = "player_wins"
        else:
            self.result = "push"
        
        return self.get_game_state(True)
    
    def get_payout(self) -> int:
        """Calculate payout based on game result"""
        if self.result == "blackjack":
            return int(self.bet * 1.5)  # Blackjack pays 3:2
        elif self.result in ["player_wins", "dealer_bust"]:
            return self.bet  # Even money
        elif self.result == "push":
            return 0  # Return bet
        else:  # All losses
            return -self.bet

class BlackjackView(View):
    def __init__(self, game: BlackjackGame, economy):
        super().__init__(timeout=60)
        self.game = game
        self.economy = economy
    
    @discord.ui.button(label="Hit", style=ButtonStyle.primary)
    async def hit_button(self, button: Button, interaction: discord.Interaction):
        # Check if it's the player's game
        if str(interaction.user.id) != self.game.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        game_state = self.game.hit()
        embed = create_blackjack_embed(game_state)
        
        if game_state["game_over"]:
            self.disable_all_buttons()
            payout = self.game.get_payout()
            
            # Update player economy
            if payout > 0:
                await self.economy.add_currency(payout, "blackjack", {"game": "blackjack", "result": self.game.result})
                await self.economy.update_gambling_stats("blackjack", True, payout)
                embed.add_field(name="Payout", value=f"You won {payout} credits!", inline=False)
            elif payout < 0:
                await self.economy.update_gambling_stats("blackjack", False, abs(payout))
                embed.add_field(name="Loss", value=f"You lost {abs(payout)} credits.", inline=False)
            else:  # push
                embed.add_field(name="Push", value=f"Your bet of {self.game.bet} credits has been returned.", inline=False)
            
            new_balance = await self.economy.get_balance()
            embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self if not game_state["game_over"] else None)
    
    @discord.ui.button(label="Stand", style=ButtonStyle.secondary)
    async def stand_button(self, button: Button, interaction: discord.Interaction):
        # Check if it's the player's game
        if str(interaction.user.id) != self.game.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        game_state = self.game.stand()
        embed = create_blackjack_embed(game_state)
        
        self.disable_all_buttons()
        payout = self.game.get_payout()
        
        # Update player economy
        if payout > 0:
            await self.economy.add_currency(payout, "blackjack", {"game": "blackjack", "result": self.game.result})
            await self.economy.update_gambling_stats("blackjack", True, payout)
            embed.add_field(name="Payout", value=f"You won {payout} credits!", inline=False)
        elif payout < 0:
            await self.economy.update_gambling_stats("blackjack", False, abs(payout))
            embed.add_field(name="Loss", value=f"You lost {abs(payout)} credits.", inline=False)
        else:  # push
            embed.add_field(name="Push", value=f"Your bet of {self.game.bet} credits has been returned.", inline=False)
        
        new_balance = await self.economy.get_balance()
        embed.add_field(name="New Balance", value=f"{new_balance} credits", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

def create_blackjack_embed(game_state: Dict[str, Any]) -> discord.Embed:
    """Create an embed for a blackjack game"""
    embed = discord.Embed(
        title="Blackjack",
        description=f"Bet: {game_state['bet']} credits",
        color=discord.Color.green()
    )
    
    # Player hand
    player_cards = " ".join([card.emoji for card in game_state["player_hand"]])
    embed.add_field(
        name=f"Your Hand ({game_state['player_value']})",
        value=player_cards,
        inline=False
    )
    
    # Dealer hand
    dealer_cards = " ".join([card.emoji for card in game_state["dealer_hand"]])
    dealer_value = game_state["dealer_value"]
    
    if not game_state["reveal_dealer"]:
        dealer_name = f"Dealer's Hand (showing {dealer_value})"
    else:
        dealer_name = f"Dealer's Hand ({dealer_value})"
    
    embed.add_field(name=dealer_name, value=dealer_cards, inline=False)
    
    # Game result
    if game_state["game_over"]:
        result_text = ""
        if game_state["result"] == "blackjack":
            result_text = "Blackjack! You win!"
        elif game_state["result"] == "dealer_blackjack":
            result_text = "Dealer has Blackjack. You lose."
        elif game_state["result"] == "bust":
            result_text = "Bust! You went over 21."
        elif game_state["result"] == "dealer_bust":
            result_text = "Dealer busts! You win!"
        elif game_state["result"] == "player_wins":
            result_text = "You win!"
        elif game_state["result"] == "dealer_wins":
            result_text = "Dealer wins."
        elif game_state["result"] == "push":
            result_text = "Push! It's a tie."
        
        embed.add_field(name="Result", value=result_text, inline=False)
    
    return embed

class SlotMachine:
    def __init__(self):
        self.symbols = ["🍒", "🍋", "🍊", "🍇", "🍉", "💎", "7️⃣", "🎰"]
        self.weights = [20, 15, 15, 15, 10, 10, 10, 5]  # Weights for each symbol
        self.payouts = {
            "🍒": 2,   # Any 3 cherries
            "🍋": 3,   # Any 3 lemons
            "🍊": 4,   # Any 3 oranges
            "🍇": 5,   # Any 3 grapes
            "🍉": 8,   # Any 3 watermelons
            "💎": 10,  # Any 3 diamonds
            "7️⃣": 15,  # Any 3 sevens
            "🎰": 25   # Any 3 slot machines (jackpot)
        }
        self.special_combos = {
            ("7️⃣", "7️⃣", "7️⃣"): 20,  # Triple 7s (higher payout)
            ("🎰", "🎰", "🎰"): 50   # Triple slots (jackpot)
        }
    
    def spin(self) -> Tuple[List[str], int, int]:
        """Spin the slot machine and return results"""
        # Select symbols based on weights
        results = random.choices(self.symbols, weights=self.weights, k=3)
        
        # Check for special combinations
        tuple_result = tuple(results)
        if tuple_result in self.special_combos:
            multiplier = self.special_combos[tuple_result]
        # Check if all symbols are the same
        elif results[0] == results[1] == results[2]:
            multiplier = self.payouts[results[0]]
        # Check if two symbols are the same
        elif results[0] == results[1] or results[0] == results[2] or results[1] == results[2]:
            # Find the duplicated symbol
            if results[0] == results[1]:
                symbol = results[0]
            elif results[0] == results[2]:
                symbol = results[0]
            else:
                symbol = results[1]
            multiplier = self.payouts[symbol] // 2  # Half payout for two matching
        else:
            multiplier = 0
        
        return results, multiplier

class SlotsView(View):
    def __init__(self, player_id: str, economy, bet: int = 10):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.economy = economy
        self.slot_machine = SlotMachine()
        self.bet = bet
    
    @discord.ui.button(label="Spin", style=ButtonStyle.primary)
    async def spin_button(self, button: Button, interaction: discord.Interaction):
        # Check if it's the player's game
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Check if player has enough credits
        balance = await self.economy.get_balance()
        if balance < self.bet:
            await interaction.response.send_message(f"You don't have enough credits! You need {self.bet} credits to play.", ephemeral=True)
            return
        
        # Remove the bet amount
        await self.economy.remove_currency(self.bet, "slots_bet")
        
        # Spin the slots
        symbols, multiplier = self.slot_machine.spin()
        
        # Calculate winnings
        winnings = self.bet * multiplier
        won = winnings > 0
        
        # Update player economy and gambling stats
        if won:
            await self.economy.add_currency(winnings, "slots_win", {"game": "slots", "multiplier": multiplier})
            await self.economy.update_gambling_stats("slots", True, winnings)
        else:
            await self.economy.update_gambling_stats("slots", False, self.bet)
        
        # Create the embed
        embed = discord.Embed(
            title="🎰 Slot Machine 🎰",
            description=f"Bet: {self.bet} credits",
            color=discord.Color.gold() if won else discord.Color.dark_gray()
        )
        
        # Add the spin animation effect with a loading message
        await interaction.response.defer()
        
        # Simulate spinning animation
        loading_embed = discord.Embed(
            title="🎰 Slot Machine 🎰",
            description="Spinning...",
            color=discord.Color.blue()
        )
        loading_embed.add_field(name="Bet", value=f"{self.bet} credits", inline=False)
        loading_message = await interaction.followup.send(embed=loading_embed)
        
        # Simulate spinning with random symbols
        for _ in range(3):
            temp_symbols = random.choices(self.slot_machine.symbols, k=3)
            temp_embed = discord.Embed(
                title="🎰 Slot Machine 🎰",
                description="Spinning...",
                color=discord.Color.blue()
            )
            temp_embed.add_field(name="Reels", value=" | ".join(temp_symbols), inline=False)
            await loading_message.edit(embed=temp_embed)
            await asyncio.sleep(0.7)
        
        # Show final result
        embed.add_field(name="Reels", value=" | ".join(symbols), inline=False)
        
        if won:
            embed.add_field(name="Result", value=f"🎉 You won {winnings} credits! 🎉", inline=False)
        else:
            embed.add_field(name="Result", value=f"Better luck next time!", inline=False)
        
        # Add new balance
        new_balance = await self.economy.get_balance()
        embed.add_field(name="Your Balance", value=f"{new_balance} credits", inline=False)
        
        # Update the message
        await loading_message.edit(embed=embed, view=self)
    
    @discord.ui.button(label="Change Bet", style=ButtonStyle.secondary)
    async def change_bet_button(self, button: Button, interaction: discord.Interaction):
        # Check if it's the player's game
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Create a modal for bet input
        modal = BetModal(title="Change Your Bet", current_bet=self.bet)
        await interaction.response.send_modal(modal)
        
        # Wait for the modal to be submitted
        timed_out = await modal.wait()
        
        if not timed_out and modal.value is not None:
            try:
                new_bet = int(modal.value)
                if new_bet <= 0:
                    await interaction.followup.send("Bet must be greater than 0!", ephemeral=True)
                else:
                    self.bet = new_bet
                    embed = discord.Embed(
                        title="🎰 Slot Machine 🎰",
                        description=f"Bet changed to {self.bet} credits",
                        color=discord.Color.blue()
                    )
                    
                    # Add current balance
                    balance = await self.economy.get_balance()
                    embed.add_field(name="Your Balance", value=f"{balance} credits", inline=False)
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except ValueError:
                await interaction.followup.send("Please enter a valid number!", ephemeral=True)
    
    @discord.ui.button(label="Quit", style=ButtonStyle.danger)
    async def quit_button(self, button: Button, interaction: discord.Interaction):
        # Check if it's the player's game
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.disable_all_buttons()
        
        embed = discord.Embed(
            title="🎰 Slot Machine 🎰",
            description="Thanks for playing!",
            color=discord.Color.dark_gray()
        )
        
        # Add current balance
        balance = await self.economy.get_balance()
        embed.add_field(name="Your Balance", value=f"{balance} credits", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

class BetModal(discord.ui.Modal):
    def __init__(self, title: str, current_bet: int):
        super().__init__(title=title)
        self.value = None
        
        self.bet_input = discord.ui.TextInput(
            label="Enter your bet",
            placeholder=f"Current bet: {current_bet}",
            default=str(current_bet),
            required=True,
            min_length=1,
            max_length=6
        )
        self.add_item(self.bet_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.bet_input.value
        await interaction.response.defer()