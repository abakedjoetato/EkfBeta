import re
import os

def process_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Count the number of replacements
    replacements = 0
    
    # Pattern for error and success embeds without guild parameter, with proper indentation
    embed_pattern = r'(EmbedBuilder\.create_(?:error|success)_embed\(\s*(?:"[^"]*"|\'[^\']*\')\s*,\s*(?:"[^"]*"|\'[^\']*\'|f"[^"]*"|f\'[^\']*\')\s*)(\))'
    updated_content, count = re.subn(embed_pattern, r'\1, guild=ctx.guild\2', content)
    replacements += count
    
    # Pattern for create_base_embed
    base_pattern = r'(EmbedBuilder\.create_base_embed\(\s*(?:title=)?(?:"[^"]*"|\'[^\']*\'|f"[^"]*"|f\'[^\']*\')\s*,\s*(?:description=)?(?:"[^"]*"|\'[^\']*\'|f"[^"]*"|f\'[^\']*\')\s*)(\))'
    updated_content, count = re.subn(base_pattern, r'\1, guild=ctx.guild\2', updated_content)
    replacements += count
    
    # Only update if we made changes
    if replacements > 0:
        with open(file_path, 'w') as file:
            file.write(updated_content)
    
    return replacements

# Process all cog files
cog_files = [f for f in os.listdir('cogs') if f.endswith('.py')]
total_replacements = 0

for cog_file in cog_files:
    file_path = os.path.join('cogs', cog_file)
    replacements = process_file(file_path)
    if replacements > 0:
        print(f"Updated {replacements} embed calls in {file_path}")
        total_replacements += replacements

print(f"Total replacements: {total_replacements}")
