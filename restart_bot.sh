#!/bin/bash

# Script to restart the Discord bot workflow
echo "Restarting Discord bot workflow..."

# This script will be executed manually to restart the bot
# It stops the current bot process and lets the Replit workflow system restart it

# Kill any existing python processes
pkill -f "python main.py"

echo "Bot process terminated. Workflow will automatically restart the bot."
echo "If the bot doesn't restart automatically, please use the 'run' button in the Replit interface."
