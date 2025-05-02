"""Fix Guild model usage"""
import glob
import re

# Find all cog files
cog_files = glob.glob('cogs/*.py')

for file_path in cog_files:
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Fix indentation issues
    # Find try: followed by # Get guild model with wrong indentation
    pattern = r'(\s+try:\s*\n\s+# Get guild model for themed embed)'
    matches = list(re.finditer(pattern, content))
    
    if matches:
        print(f"Fixing indentation in {file_path}")
        for match in reversed(matches):
            # Get correct indentation
            indentation = re.search(r'(\s+)try:', content[0:match.start()])
            if indentation:
                indent = indentation.group(1)
                # Get the whole block that needs fixing
                block_pattern = r'try:\s*\n\s+# Get guild model for themed embed\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n[^\n]*\n'
                block_match = re.search(block_pattern, content[match.start()-10:])
                if block_match:
                    block = block_match.group(0)
                    # Fix the indentation
                    fixed_block = f"{indent}try:\n"
                    for line in block.split('\n')[1:]:  # Skip the try: line
                        if line.strip():
                            fixed_block += f"{indent}    {line.strip()}\n"
                    # Replace the block
                    start = match.start()-10 + block_match.start()
                    end = match.start()-10 + block_match.end()
                    content = content[:start] + fixed_block + content[end:]
    
    # Replace ctx.guild with guild_model
    pattern2 = r'guild=ctx\.guild'
    content = re.sub(pattern2, 'guild=guild_model', content)
    
    # Write back
    with open(file_path, 'w') as file:
        file.write(content)

print("All files processed")
