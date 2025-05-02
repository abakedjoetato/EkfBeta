"""Fix server ID type handling in autocomplete functions

This script updates all autocomplete functions in stats.py to ensure consistent 
type handling of server IDs. It modifies the code to ensure server_id is always 
treated as a string, which fixes issues with autocomplete functionality.

Usage: python fix_autocomplete.py
"""

import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def process_file(file_path):
    """Process the stats.py file to fix server_id type handling."""
    logger.info(f"Processing file: {file_path}")
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Fix player_name_autocomplete - first server_id extraction
    pattern1 = r'(if option\.get\("name"\) == "server_id":\s+)server_id = option\.get\("value"\)(\s+break)'
    replacement1 = r'\1raw_id = option.get("value")\n                server_id = str(raw_id) if raw_id is not None else None\n                logger.debug(f"player_name_autocomplete converting server_id from {type(raw_id).__name__} to string: {server_id}")\2'
    content = re.sub(pattern1, replacement1, content)
    
    # Fix player_name_autocomplete - second server_id extraction (subcommand)
    pattern2 = r'(if suboption\.get\("name"\) == "server_id":\s+)server_id = suboption\.get\("value"\)(\s+break)'
    replacement2 = r'\1raw_id = suboption.get("value")\n                        server_id = str(raw_id) if raw_id is not None else None\n                        logger.debug(f"player_name_autocomplete (subcommand) converting server_id from {type(raw_id).__name__} to string: {server_id}")\2'
    content = re.sub(pattern2, replacement2, content)
    
    # Fix weapon_name_autocomplete - first server_id extraction
    pattern3 = r'(if option\.get\("name"\) == "server_id":\s+)server_id = option\.get\("value"\)(\s+break)'
    replacement3 = r'\1raw_id = option.get("value")\n                server_id = str(raw_id) if raw_id is not None else None\n                logger.debug(f"weapon_name_autocomplete converting server_id from {type(raw_id).__name__} to string: {server_id}")\2'
    content = re.sub(pattern3, replacement3, content)
    
    # Fix weapon_name_autocomplete - second server_id extraction (subcommand)
    pattern4 = r'(if suboption\.get\("name"\) == "server_id":\s+)server_id = suboption\.get\("value"\)(\s+break)'
    replacement4 = r'\1raw_id = suboption.get("value")\n                        server_id = str(raw_id) if raw_id is not None else None\n                        logger.debug(f"weapon_name_autocomplete (subcommand) converting server_id from {type(raw_id).__name__} to string: {server_id}")\2'
    content = re.sub(pattern4, replacement4, content)
    
    # Check database query for server_id in player_name_autocomplete
    pattern5 = r'("server_id": )server_id(, "active": True)'
    replacement5 = r'\1str(server_id)\2'
    content = re.sub(pattern5, replacement5, content)
    
    # Write the updated content back to the file
    with open(file_path, 'w') as file:
        file.write(content)
    
    logger.info(f"Successfully updated {file_path}")

def main():
    """Main function to run the script."""
    try:
        process_file('cogs/stats.py')
        logger.info("Server ID type handling fix completed successfully!")
    except Exception as e:
        logger.error(f"Error fixing server ID type handling: {e}")

if __name__ == "__main__":
    main()
