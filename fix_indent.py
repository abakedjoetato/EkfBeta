"""Fix indentation in stats.py

This script fixes indentation issues in the stats.py file.
"""

def fix_indentation():
    # Read the file
    with open('cogs/stats.py', 'r') as file:
        lines = file.readlines()
    
    # Fix indentation for specific lines
    for i in range(len(lines)):
        if 'server_id = str(raw_id)' in lines[i] and lines[i].startswith('                        '):
            lines[i] = lines[i].replace('                        ', '                    ')
        if 'logger.debug' in lines[i] and '(subcommand)' in lines[i] and lines[i].startswith('                        '):
            lines[i] = lines[i].replace('                        ', '                    ')
    
    # Write the file back
    with open('cogs/stats.py', 'w') as file:
        file.writelines(lines)
    
    print("Fixed indentation in stats.py")

if __name__ == "__main__":
    fix_indentation()
