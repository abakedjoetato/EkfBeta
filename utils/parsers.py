"""
Parsers for CSV and log files
"""
import re
import logging
import datetime
from typing import List, Dict, Any, Tuple, Optional

from config import CSV_FIELDS, EVENT_PATTERNS

logger = logging.getLogger(__name__)

class CSVParser:
    """Parser for CSV kill data files"""
    
    @staticmethod
    def parse_kill_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line from a CSV file into a kill event"""
        try:
            parts = line.strip().split(';')
            
            # Debug info
            logger.debug(f"Parsing CSV line with {len(parts)} parts: {line}")
            
            # Ensure we have all required fields
            if len(parts) < 7:
                logger.warning(f"Invalid CSV line format (missing fields): {line}")
                return None
                
            # Note: Some CSV lines may have a trailing delimiter creating an 8th empty field
            # We'll ignore that extra field and remove any empty strings
            parts = [p for p in parts if p.strip()]
            
            # Extract fields (with more validation)
            try:
                timestamp_str = parts[CSV_FIELDS["timestamp"]]
                killer_name = parts[CSV_FIELDS["killer_name"]]
                killer_id = parts[CSV_FIELDS["killer_id"]]
                victim_name = parts[CSV_FIELDS["victim_name"]]
                victim_id = parts[CSV_FIELDS["victim_id"]]
                weapon = parts[CSV_FIELDS["weapon"]]
                
                # Additional validation
                if not timestamp_str or not killer_id or not victim_id:
                    logger.warning(f"Missing required field values in line: {line}")
                    return None
                
                # Try to parse distance as int, default to 0 if fails
                try:
                    if CSV_FIELDS["distance"] < len(parts):
                        distance = int(parts[CSV_FIELDS["distance"]])
                    else:
                        distance = 0
                except (ValueError, IndexError):
                    distance = 0
            except IndexError:
                logger.warning(f"Index error while parsing CSV line: {line}")
                return None
            
            # Parse timestamp
            try:
                timestamp = datetime.datetime.strptime(
                    timestamp_str, "%Y.%m.%d-%H.%M.%S"
                )
            except ValueError:
                logger.warning(f"Invalid timestamp format: {timestamp_str}")
                # Use current time as fallback
                timestamp = datetime.datetime.utcnow()
            
            # Determine if this is a suicide
            is_suicide = killer_id == victim_id
            suicide_type = None
            
            if is_suicide:
                if weapon == "suicide_by_relocation":
                    suicide_type = "menu"
                elif weapon == "falling":
                    suicide_type = "fall"
                else:
                    suicide_type = "other"
            
            # Create kill event
            kill_event = {
                "timestamp": timestamp,
                "killer_name": killer_name,
                "killer_id": killer_id,
                "victim_name": victim_name,
                "victim_id": victim_id,
                "weapon": weapon,
                "distance": distance,
                "is_suicide": is_suicide,
                "suicide_type": suicide_type
            }
            
            return kill_event
            
        except Exception as e:
            logger.error(f"Error parsing CSV line: {e} - Line: {line}")
            return None
    
    @staticmethod
    def parse_kill_lines(lines: List[str]) -> List[Dict[str, Any]]:
        """Parse multiple CSV lines into kill events"""
        kill_events = []
        
        for line in lines:
            if not line.strip():
                continue
                
            kill_event = CSVParser.parse_kill_line(line)
            if kill_event:
                kill_events.append(kill_event)
        
        return kill_events


class LogParser:
    """Parser for log files"""
    
    @staticmethod
    def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line from a log file into an event or connection"""
        try:
            # Check if line has a timestamp prefix
            timestamp_match = re.match(r'\[([\d\.\-]+)-([\d:]+)\]', line)
            if not timestamp_match:
                return None
            
            # Extract timestamp parts
            date_str, time_str = timestamp_match.groups()
            
            try:
                # Parse timestamp
                timestamp = datetime.datetime.strptime(
                    f"{date_str} {time_str}", "%Y.%m.%d %H.%M.%S"
                )
            except ValueError:
                # Use current time as fallback
                timestamp = datetime.datetime.utcnow()
            
            # Check for player connection events
            connection_match = re.search(r'Player (\w+) \(([0-9a-f]+)\) (connected|disconnected)', line)
            if connection_match:
                player_name, player_id, action = connection_match.groups()
                return {
                    "type": "connection",
                    "timestamp": timestamp,
                    "player_name": player_name,
                    "player_id": player_id,
                    "action": action,
                    "platform": "PC" if "through Steam" in line else "Console"
                }
            
            # Check for game events
            for event_type, pattern in EVENT_PATTERNS.items():
                event_match = re.search(pattern, line)
                if event_match:
                    return {
                        "type": "event",
                        "timestamp": timestamp,
                        "event_type": event_type,
                        "details": event_match.groups()
                    }
            
            # Check for server restart
            if "Log file open" in line:
                return {
                    "type": "server_restart",
                    "timestamp": timestamp
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing log line: {e} - Line: {line}")
            return None
    
    @staticmethod
    def parse_log_lines(lines: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Parse multiple log lines into events and connections"""
        events = []
        connections = []
        
        for line in lines:
            if not line.strip():
                continue
                
            parsed = LogParser.parse_log_line(line)
            if not parsed:
                continue
                
            if parsed["type"] == "connection":
                connections.append(parsed)
            elif parsed["type"] == "event" or parsed["type"] == "server_restart":
                events.append(parsed)
        
        return events, connections
    
    @staticmethod
    def count_players(connections: List[Dict[str, Any]]) -> Tuple[int, Dict[str, str]]:
        """Count online players from connection events"""
        online_players = {}
        
        # Process connections in chronological order
        for conn in sorted(connections, key=lambda x: x["timestamp"]):
            player_id = conn["player_id"]
            
            if conn["action"] == "connected":
                online_players[player_id] = conn["player_name"]
            elif conn["action"] == "disconnected" and player_id in online_players:
                del online_players[player_id]
        
        return len(online_players), online_players
