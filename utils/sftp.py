"""
SFTP utility functions for server connections and file operations
"""
import os
import re
import logging
import asyncio
import datetime
from io import StringIO

import paramiko
from paramiko.ssh_exception import SSHException, AuthenticationException

from config import SFTP_CONNECTION_SETTINGS, CSV_FILENAME_PATTERN, LOG_FILENAME

logger = logging.getLogger(__name__)

class SFTPClient:
    """SFTP client for connecting to game servers and retrieving files"""
    
    def __init__(self, host, port, username, password, server_id):
        """Initialize SFTP client with connection parameters"""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.server_id = server_id
        self.client = None
        self.sftp = None
        self.root_path = None
        self.connected = False
        self.last_error = None
    
    async def connect(self):
        """Establish SFTP connection"""
        try:
            # Create SSH client
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                **SFTP_CONNECTION_SETTINGS
            )
            
            # Open SFTP session
            self.sftp = self.client.open_sftp()
            logger.info(f"Connected to SFTP server: {self.host}:{self.port} for server {self.server_id}")
            
            # Try to find the appropriate root directory for this server
            logger.info(f"Searching for server directory for server ID: {self.server_id}")
            await self.find_root_path()
            
            self.connected = True
            self.last_error = None
            return True
            
        except AuthenticationException:
            self.last_error = "Authentication failed. Check username and password."
            logger.error(f"Authentication failed for SFTP server: {self.host}:{self.port}")
            self.connected = False
            return False
            
        except SSHException as e:
            self.last_error = f"SSH error: {str(e)}"
            logger.error(f"SSH error connecting to {self.host}:{self.port}: {e}")
            self.connected = False
            return False
            
        except Exception as e:
            self.last_error = f"Connection error: {str(e)}"
            logger.error(f"Error connecting to SFTP server {self.host}:{self.port}: {e}", exc_info=True)
            self.connected = False
            return False
    
    async def find_root_path(self):
        """Find the root path containing host_serverID or IP_serverID pattern"""
        try:
            # Start from current directory
            current_path = '.'
            self.root_path = None
            
            # Extract IP address from host (remove port if present)
            ip_address = self.host.split(':')[0]
            
            # Create patterns to try (both host_ pattern and IP_ pattern)
            patterns = [
                f"{ip_address}_{self.server_id}",   # IP_serverID format (e.g., "79.127.236.1_7020")
                f"host_{self.server_id}"            # Legacy host_serverID format
            ]
            
            logger.info(f"Searching for directory patterns: {patterns}")
            
            # Direct search in the root directory (no recursion)
            try:
                items = self.sftp.listdir(current_path)
                logger.info(f"Found {len(items)} items in root directory")
                
                for item in items:
                    # Check if the item name matches our patterns
                    for pattern in patterns:
                        if pattern in item:
                            self.root_path = os.path.join(current_path, item)
                            logger.info(f"Found matching directory: {self.root_path}")
                            return
            except Exception as dir_e:
                logger.error(f"Error listing root directory: {dir_e}")
            
            if not self.root_path:
                # If no match found, fall back to recursive search (limited depth)
                for pattern in patterns:
                    await self._find_path_recursive(current_path, pattern, max_depth=2)
                    if self.root_path:
                        logger.info(f"Found matching directory with recursive search: {self.root_path}")
                        return
            
            if not self.root_path:
                logger.warning(f"Could not find root path with any pattern {patterns}. Using current directory.")
                self.root_path = '.'
                
        except Exception as e:
            logger.error(f"Error finding root path: {e}", exc_info=True)
            self.root_path = '.'
    
    async def _find_path_recursive(self, path, pattern, max_depth=3, current_depth=0):
        """Recursively search for a directory matching the pattern"""
        if current_depth > max_depth:
            return
        
        try:
            # Check if current directory name matches pattern
            if pattern in os.path.basename(path):
                self.root_path = path
                logger.info(f"Found root path: {path}")
                return
            
            # List directory contents
            items = self.sftp.listdir(path)
            
            # Check subdirectories
            for item in items:
                item_path = os.path.join(path, item)
                try:
                    # Check if item is a directory
                    if self._is_dir(item_path):
                        # Check if directory name contains pattern
                        if pattern in item:
                            self.root_path = item_path
                            logger.info(f"Found root path: {item_path}")
                            return
                        
                        # Recursively check subdirectory
                        await self._find_path_recursive(
                            item_path, pattern, max_depth, current_depth + 1
                        )
                        
                        # If root path was found in recursive call, return
                        if self.root_path:
                            return
                except:
                    # Skip if can't check directory
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching directory {path}: {e}")
    
    def _is_dir(self, path):
        """Check if a path is a directory"""
        try:
            return self.sftp.stat(path).st_mode & 0o40000 != 0
        except:
            return False
    
    async def disconnect(self):
        """Close SFTP connection"""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
            self.connected = False
            logger.info(f"Disconnected from SFTP server: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error disconnecting from SFTP server: {e}")
    
    async def get_latest_csv_file(self):
        """Get the path to the latest CSV file by timestamp"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return None
        
        try:
            csv_files = []
            # Search for CSV files in the root directory
            for filename in self.sftp.listdir(self.root_path):
                if re.match(CSV_FILENAME_PATTERN, filename):
                    file_path = os.path.join(self.root_path, filename)
                    # Get file modification time
                    mtime = self.sftp.stat(file_path).st_mtime
                    csv_files.append((file_path, mtime, filename))
            
            # Sort by modification time (newest first)
            csv_files.sort(key=lambda x: x[1], reverse=True)
            
            if csv_files:
                # Return path to the latest file
                return csv_files[0][0]
            else:
                logger.warning(f"No CSV files found in {self.root_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest CSV file: {e}", exc_info=True)
            return None
    
    async def get_all_csv_files(self):
        """Get all CSV files sorted by timestamp (oldest first)"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return []
        
        try:
            csv_files = []
            
            # First check if the specified server directory exists
            target_directory = None
            
            # List root directory to search for our server directory
            logger.info("Searching for server directory in root...")
            root_files = self.sftp.listdir(".")
            logger.info(f"Found {len(root_files)} items in root directory")
            
            # Look for the server ID pattern (IP_serverID or host_serverID)
            for item in root_files:
                if (f"{self.host.split(':')[0]}_{self.server_id}" in item) or (f"host_{self.server_id}" in item):
                    # Found matching directory
                    target_directory = os.path.join(".", item)
                    logger.info(f"Found server directory: {target_directory}")
                    break
            
            if not target_directory:
                logger.error(f"Could not find server directory for server ID: {self.server_id}")
                self.last_error = f"Server directory for ID {self.server_id} not found"
                return []
            
            # Using the specified path structure: host_serverid/actual1/deathlogs
            # We'll first check for the 'actual1' directory, then 'deathlogs'
            logger.info(f"Looking for CSV files in the deathlogs directory structure")
            
            try:
                # Get server directory contents
                server_items = self.sftp.listdir(target_directory)
                logger.info(f"Server directory contains: {', '.join(server_items)}")
                
                # Look for 'actual1' directory
                actual_dir = None
                for item in server_items:
                    if item.lower() == "actual1":
                        actual_dir = os.path.join(target_directory, item)
                        logger.info(f"Found 'actual1' directory: {actual_dir}")
                        break
                
                if not actual_dir:
                    logger.warning("Could not find 'actual1' directory, will search all subdirectories")
                    # Fall back to general search
                    discovered_csv_paths = await self._find_csv_files_recursive(target_directory)
                else:
                    # Found actual1 directory, now look for 'deathlogs'
                    actual_items = self.sftp.listdir(actual_dir)
                    logger.info(f"'actual1' directory contains: {', '.join(actual_items)}")
                    
                    deathlogs_dir = None
                    for item in actual_items:
                        if item.lower() == "deathlogs":
                            deathlogs_dir = os.path.join(actual_dir, item)
                            logger.info(f"Found 'deathlogs' directory: {deathlogs_dir}")
                            break
                    
                    if not deathlogs_dir:
                        logger.warning("Could not find 'deathlogs' directory, will search in 'actual1' and its subdirectories")
                        discovered_csv_paths = await self._find_csv_files_recursive(actual_dir)
                    else:
                        # Found deathlogs directory, look for CSV files here and in subdirectories
                        logger.info(f"Searching for CSV files in deathlogs directory: {deathlogs_dir}")
                        discovered_csv_paths = await self._find_csv_files_recursive(deathlogs_dir)
                    
            except Exception as e:
                logger.error(f"Error exploring directory structure: {e}")
                # Fall back to searching the entire server directory
                logger.info("Falling back to general search in server directory")
                discovered_csv_paths = await self._find_csv_files_recursive(target_directory)
            
            # Process all discovered CSV files
            for file_path in discovered_csv_paths:
                try:
                    # Extract the filename from the path
                    filename = os.path.basename(file_path)
                    logger.info(f"Processing discovered CSV file: {filename} at {file_path}")
                    
                    # Try to parse timestamp from filename
                    timestamp_str = filename.split(".csv")[0]
                    timestamp = None
                    
                    # Try various timestamp formats
                    formats_to_try = [
                        "%Y.%m.%d-%H.%M.%S",
                        "%Y-%m-%d_%H-%M-%S",
                        "%Y%m%d_%H%M%S",
                        "%Y%m%d%H%M%S",
                        "%Y-%m-%d"
                    ]
                    
                    for fmt in formats_to_try:
                        try:
                            timestamp = datetime.datetime.strptime(timestamp_str, fmt)
                            logger.info(f"Parsed timestamp using format: {fmt}")
                            break
                        except ValueError:
                            continue
                    
                    # If we couldn't parse a timestamp, use current time
                    if not timestamp:
                        logger.warning(f"Could not parse timestamp from {filename}, using current time")
                        timestamp = datetime.datetime.now()
                    
                    csv_files.append((file_path, timestamp, filename))
                except Exception as ve:
                    logger.warning(f"Error processing CSV file {file_path}: {ve}")
                    # Still add with current timestamp
                    timestamp = datetime.datetime.now()
                    filename = os.path.basename(file_path)
                    csv_files.append((file_path, timestamp, filename))
            
            # Sort by timestamp (oldest first)
            csv_files.sort(key=lambda x: x[1])
            
            if not csv_files:
                logger.warning(f"No CSV files found in any directory or subdirectory")
                self.last_error = "No CSV files found"
            else:
                logger.info(f"Found {len(csv_files)} CSV files across all directories")
                for file_path, timestamp, filename in csv_files:
                    logger.info(f"CSV file: {file_path} (timestamp: {timestamp})")
            
            return [file_path for file_path, _, _ in csv_files]
                
        except Exception as e:
            logger.error(f"Error getting all CSV files: {e}", exc_info=True)
            self.last_error = f"Error searching for CSV files: {str(e)}"
            return []
    
    async def _find_csv_files_recursive(self, directory, max_depth=3, current_depth=0):
        """Recursively search for CSV files in all subdirectories"""
        if current_depth > max_depth:
            return []
            
        csv_files = []
        
        try:
            # Get directory contents
            items = self.sftp.listdir(directory)
            
            # Process each item
            for item in items:
                item_path = os.path.join(directory, item)
                
                try:
                    # Check if it's a CSV file
                    if item.lower().endswith('.csv'):
                        logger.info(f"Found CSV file: {item} in directory: {directory}")
                        csv_files.append(item_path)
                    
                    # Check if it's a directory and process recursively
                    elif self._is_dir(item_path):
                        logger.info(f"Exploring subdirectory: {item_path} (depth {current_depth})")
                        subdirectory_files = await self._find_csv_files_recursive(
                            item_path, max_depth, current_depth + 1
                        )
                        csv_files.extend(subdirectory_files)
                except Exception as item_e:
                    logger.warning(f"Error processing item {item_path}: {item_e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error listing directory {directory}: {e}")
            
        return csv_files
    
    async def get_log_file(self):
        """Get the path to the Deadside.log file"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return None
        
        try:
            # First find the server directory (same logic as in get_all_csv_files)
            target_directory = None
            
            # List root directory
            logger.info("Searching for server directory in root to find log file...")
            root_files = self.sftp.listdir(".")
            
            # Look for the server ID pattern
            for item in root_files:
                if (f"{self.host.split(':')[0]}_{self.server_id}" in item) or (f"host_{self.server_id}" in item):
                    # Found matching directory
                    target_directory = os.path.join(".", item)
                    logger.info(f"Found server directory for logs: {target_directory}")
                    break
            
            if not target_directory:
                logger.error(f"Could not find server directory for server ID: {self.server_id}")
                return None
            
            # Using the specified path: host_serverid/Logs
            # Look specifically for the 'Logs' directory
            try:
                server_items = self.sftp.listdir(target_directory)
                logger.info(f"Server directory contains: {', '.join(server_items)}")
                
                # Find the Logs directory
                logs_dir = None
                for item in server_items:
                    if item.lower() == "logs":
                        logs_dir = os.path.join(target_directory, item)
                        logger.info(f"Found 'Logs' directory: {logs_dir}")
                        break
                
                if not logs_dir:
                    logger.warning("Could not find 'Logs' directory, will search in server directory and its subdirectories")
                    # Fall back to general search if we can't find the Logs directory
                    return await self._find_specific_log_file(target_directory)
                
                # Check for Deadside.log in the Logs directory
                logs_items = self.sftp.listdir(logs_dir)
                logger.info(f"'Logs' directory contains: {', '.join(logs_items)}")
                
                if LOG_FILENAME in logs_items:
                    log_path = os.path.join(logs_dir, LOG_FILENAME)
                    logger.info(f"Found log file at: {log_path}")
                    return log_path
                else:
                    logger.warning(f"'{LOG_FILENAME}' not found in Logs directory, checking subdirectories")
                    return await self._find_specific_log_file(logs_dir)
                    
            except Exception as e:
                logger.error(f"Error searching for log file: {e}")
                # Fall back to general search
                return await self._find_specific_log_file(target_directory)
                
        except Exception as e:
            logger.error(f"Error getting log file: {e}", exc_info=True)
            return None
    
    async def _find_specific_log_file(self, directory, max_depth=2, current_depth=0):
        """Search specifically for Deadside.log in the directory structure"""
        if current_depth > max_depth:
            return None
        
        try:
            # First check if Deadside.log exists in this directory
            try:
                items = self.sftp.listdir(directory)
                
                if LOG_FILENAME in items:
                    log_path = os.path.join(directory, LOG_FILENAME)
                    logger.info(f"Found {LOG_FILENAME} in directory: {directory}")
                    return log_path
            except Exception as list_e:
                logger.warning(f"Error listing directory {directory}: {list_e}")
                return None
            
            # If not found, check subdirectories
            for item in items:
                # Only look for directories named 'Logs' or any directory if we're at depth 0
                if item.lower() == "logs" or current_depth == 0:
                    item_path = os.path.join(directory, item)
                    
                    try:
                        if self._is_dir(item_path):
                            # First check this directory for the log file
                            subdir_items = self.sftp.listdir(item_path)
                            
                            if LOG_FILENAME in subdir_items:
                                log_path = os.path.join(item_path, LOG_FILENAME)
                                logger.info(f"Found {LOG_FILENAME} in subdirectory: {item_path}")
                                return log_path
                            
                            # If not found, recurse deeper
                            log_path = await self._find_specific_log_file(
                                item_path, max_depth, current_depth + 1
                            )
                            if log_path:
                                return log_path
                    except Exception as e:
                        logger.warning(f"Error processing subdirectory {item_path}: {e}")
                        continue
            
            # Not found in this directory or its subdirectories
            return None
                
        except Exception as e:
            logger.error(f"Error searching for {LOG_FILENAME}: {e}")
            return None
    
    async def read_file(self, file_path, start_line=0, max_lines=None):
        """Read a file from the SFTP server"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return []
        
        try:
            with self.sftp.file(file_path, 'r') as f:
                # Skip lines if start_line > 0
                for _ in range(start_line):
                    next(f, None)
                
                # Read lines
                lines = []
                line_count = 0
                for line in f:
                    lines.append(line.strip())
                    line_count += 1
                    if max_lines and line_count >= max_lines:
                        break
                
                return lines
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            return []
    
    async def get_file_size(self, file_path):
        """Get the size of a file in lines"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return 0
        
        try:
            with self.sftp.file(file_path, 'r') as f:
                # Count lines
                line_count = sum(1 for _ in f)
                return line_count
                
        except Exception as e:
            logger.error(f"Error getting file size {file_path}: {e}", exc_info=True)
            return 0
    
    @staticmethod
    def run_in_executor(func, *args, **kwargs):
        """Run a blocking function in an executor"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))
