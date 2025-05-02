"""Update embed creation to use Guild models instead of Discord Guild objects"""
import re
import os

def process_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Track original content to check if changes were made
    original_content = content
    
    # Pattern 1: Replace ctx.guild with guild_model in embed creation
    # Look for embed = EmbedBuilder... guild=ctx.guild)
    pattern1 = r'(embed\s*=\s*EmbedBuilder\.create_(?:error|success|base)_embed\([^)]*?)guild=ctx\.guild(\))(\s*)'  
    replacement1 = r'\1guild=guild_model\2\3'
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: Add guild=guild_model parameter to create_error_embed where missing
    pattern2 = r'(embed\s*=\s*EmbedBuilder\.create_error_embed\(\s*"[^"]*",\s*[^,]*?,)(\))(\s*)'
    replacement2 = r'\1 guild=guild_model\2\3'
    content = re.sub(pattern2, replacement2, content)
    
    # Pattern 3: Add guild=guild_model parameter to create_success_embed where missing
    pattern3 = r'(embed\s*=\s*EmbedBuilder\.create_success_embed\(\s*"[^"]*",\s*[^,]*?,)(\))(\s*)'
    replacement3 = r'\1 guild=guild_model\2\3'
    content = re.sub(pattern3, replacement3, content)
    
    # Pattern 4: Add guild=guild_model parameter to create_base_embed where missing
    pattern4 = r'(embed\s*=\s*EmbedBuilder\.create_base_embed\(\s*"[^"]*",\s*[^,]*?,)(\))(\s*)'
    replacement4 = r'\1 guild=guild_model\2\3'
    content = re.sub(pattern4, replacement4, content)
    
    # Pattern 5: Add Guild model initialization where it doesn't exist
    # Find functions that use EmbedBuilder but don't create a guild_model
    function_pattern = r'(async\s+def\s+[^\(]+\([^\)]*\)\s*:\s*[^"]*?"""[^"]*"""\s*try\s*:\s*.*?)(EmbedBuilder\.create_(?:error|success|base)_embed)'
    
    def add_guild_model(match):
        function_code = match.group(1)
        embed_creation = match.group(2)
        
        # Check if guild_model is already defined or used
        if 'guild_model' not in function_code:
            # Get proper indentation
            indentation = re.search(r'\n(\s+)', function_code)
            if indentation:
                indent = indentation.group(1)
                # Add guild model initialization before embed creation
                guild_model_code = f"\n{indent}# Get guild model for themed embed\n{indent}guild_data = None\n{indent}guild_model = None\n{indent}try:\n{indent}    guild_data = await self.bot.db.guilds.find_one({{\"guild_id\": ctx.guild.id}})\n{indent}    if guild_data:\n{indent}        guild_model = Guild(self.bot.db, guild_data)\n{indent}except Exception as e:\n{indent}    logger.warning(f\"Error getting guild model: {{e}}\")\n"
                return function_code.replace('try:', 'try:' + guild_model_code, 1) + embed_creation
        
        return function_code + embed_creation
    
    content = re.sub(function_pattern, add_guild_model, content, flags=re.DOTALL)
    
    # Only write the file if changes were made
    if content != original_content:
        with open(file_path, 'w') as file:
            file.write(content)
        return True
    
    return False

# Process all cog files
cog_files = [f for f in os.listdir('cogs') if f.endswith('.py')]
updated_files = 0

for cog_file in cog_files:
    file_path = os.path.join('cogs', cog_file)
    if process_file(file_path):
        print(f"Updated Guild model usage in {file_path}")
        updated_files += 1

print(f"\nTotal updated files: {updated_files}")
