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
            
            # Set root path to current directory to avoid hanging on recursive search
            self.root_path = '.'
            logger.info(f"Using current directory as root path for server {self.server_id}")
            
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
        """Find the root path containing host_serverID pattern"""
        try:
            # Start from current directory
            current_path = '.'
            pattern = f"host_{self.server_id}"
            
            # Recursively search for the pattern in directory names
            await self._find_path_recursive(current_path, pattern, max_depth=3)
            
            if not self.root_path:
                logger.warning(f"Could not find root path with pattern '{pattern}'. Using current directory.")
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
            # Search for CSV files in the root directory
            logger.info(f"Looking for CSV files in {self.root_path} with pattern {CSV_FILENAME_PATTERN}")
            
            try:
                # Get directory listing
                files = self.sftp.listdir(self.root_path)
                logger.info(f"Found {len(files)} files in directory: {', '.join(files[:5])}{'...' if len(files) > 5 else ''}")
                
                # Be more flexible with the CSV pattern - check if any file ends with .csv
                for filename in files:
                    logger.info(f"Checking file: {filename}, ends with .csv: {filename.lower().endswith('.csv')}")
                    # First try the exact pattern
                    pattern_match = re.match(CSV_FILENAME_PATTERN, filename)
                    # If it doesn't match, just check if it ends with .csv
                    if pattern_match or filename.lower().endswith('.csv'):
                        file_path = os.path.join(self.root_path, filename)
                        logger.info(f"Found matching CSV file: {filename}")
                        # Parse timestamp from filename
                        timestamp_str = filename.split(".csv")[0]
                        try:
                            # Try the standard format first
                            timestamp = None
                            try:
                                timestamp = datetime.datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
                            except ValueError:
                                # Try alternative formats (be more flexible)
                                formats_to_try = [
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
                            
                            # If we couldn't parse a timestamp, use file creation time instead
                            if not timestamp:
                                # Use current time as fallback
                                logger.warning(f"Could not parse any timestamp format from {filename}, using current time")
                                timestamp = datetime.datetime.now()
                                
                            csv_files.append((file_path, timestamp, filename))
                        except Exception as ve:
                            logger.warning(f"Error processing CSV file {filename}: {ve}")
                            # Still add it with current timestamp so we don't miss any files
                            timestamp = datetime.datetime.now()
                            csv_files.append((file_path, timestamp, filename))
            except Exception as inner_e:
                logger.error(f"Error listing directory {self.root_path}: {inner_e}", exc_info=True)
                self.last_error = f"Could not list directory: {str(inner_e)}"
                return []
            
            # Sort by timestamp (oldest first)
            csv_files.sort(key=lambda x: x[1])
            
            if not csv_files:
                logger.warning(f"No CSV files found matching pattern {CSV_FILENAME_PATTERN}")
                self.last_error = "No CSV files found with correct naming pattern"
            
            return [file_path for file_path, _, _ in csv_files]
                
        except Exception as e:
            logger.error(f"Error getting all CSV files: {e}", exc_info=True)
            self.last_error = f"Error searching for CSV files: {str(e)}"
            return []
    
    async def get_log_file(self):
        """Get the path to the Deadside.log file"""
        if not self.connected:
            await self.connect()
        if not self.connected:
            return None
        
        try:
            log_path = os.path.join(self.root_path, LOG_FILENAME)
            # Check if file exists
            try:
                self.sftp.stat(log_path)
                return log_path
            except FileNotFoundError:
                logger.warning(f"Log file not found at {log_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting log file: {e}", exc_info=True)
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
