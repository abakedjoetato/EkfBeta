"""Fix weapon_name_autocomplete function

This script fixes the log message in the weapon_name_autocomplete function to correctly display 'weapon_name_autocomplete'
"""

import re

# Read the file
with open('cogs/stats.py', 'r') as file:
    content = file.read()

# Find and fix the log message specifically in the weapon_name_autocomplete function
pattern = r'(async def weapon_name_autocomplete.*?logger\.debug\(f")(player_name)(.*?)"\)'
replacement = r'\1weapon_name\3")'

# Use re.DOTALL to make the dot match newlines
modified_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write the modified content back to the file
with open('cogs/stats.py', 'w') as file:
    file.write(modified_content)

print("Fixed weapon_name_autocomplete log message!")
