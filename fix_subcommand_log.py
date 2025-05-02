"""Fix weapon_name_autocomplete subcommand log message

This script fixes the subcommand log message in the weapon_name_autocomplete function
"""

import re

# Read the file
with open('cogs/stats.py', 'r') as file:
    content = file.read()

# Get the relevant section of the file
start_idx = content.find("async def weapon_name_autocomplete")
end_idx = content.find("async def", start_idx + 1)
if end_idx == -1:  # If it's the last function in the file
    weapon_section = content[start_idx:]
else:
    weapon_section = content[start_idx:end_idx]

# Find the subcommand log line in this section
subcommand_log_idx = weapon_section.find('logger.debug(f"player_name_autocomplete (subcommand) converting')
if subcommand_log_idx != -1:
    # Replace just in this section
    fixed_section = weapon_section.replace(
        'logger.debug(f"player_name_autocomplete (subcommand) converting', 
        'logger.debug(f"weapon_name_autocomplete (subcommand) converting'
    )
    
    # Replace the section in the full content
    content = content.replace(weapon_section, fixed_section)
    
    # Write the modified content back to the file
    with open('cogs/stats.py', 'w') as file:
        file.write(content)
    
    print("Fixed weapon_name_autocomplete subcommand log message!")
else:
    print("Subcommand log message not found in weapon_name_autocomplete function.")
