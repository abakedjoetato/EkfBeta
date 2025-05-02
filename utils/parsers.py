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
    def normalize_weapon_name(weapon: str) -> str:
        """Normalize weapon names to ensure consistency
        
        This function standardizes weapon names by correcting common variations,
        typos, and ensuring consistent capitalization and formatting.
        
        Args:
            weapon: The weapon name from the CSV
            
        Returns:
            Normalized weapon name
        """
        if not weapon or not weapon.strip():
            return "Unknown"
            
        # Convert to lowercase for easier matching
        weapon_lower = weapon.lower().strip()
        
        # Define weapon name corrections and aliases
        weapon_corrections = {
            # Rifles
            "akm": "AKM",
            "ak-47": "AKM",
            "ak47": "AKM",
            "ak74": "AK-74",
            "ak-74": "AK-74",
            "m4": "M4",
            "m4a1": "M4",
            "m16": "M16",
            "m16a4": "M16",
            "fal": "FAL",
            "sks": "SKS",
            
            # SMGs
            "bizon": "PP-19 Bizon",
            "pp-19": "PP-19 Bizon",
            "pp19": "PP-19 Bizon",
            "pp_19": "PP-19 Bizon",
            "pp-19bizon": "PP-19 Bizon",
            "mp5": "MP5",
            "mp-5": "MP5",
            "mp_5": "MP5",
            "ump": "UMP-45",
            "ump45": "UMP-45",
            "ump-45": "UMP-45",
            "vector": "Vector",
            
            # Shotguns
            "shotgun": "Shotgun",
            "saiga": "Saiga-12",
            "saiga12": "Saiga-12",
            "saiga-12": "Saiga-12",
            "pump": "Pump Shotgun",
            "pump shotgun": "Pump Shotgun",
            
            # Pistols
            "pm": "PM",
            "makarov": "PM",
            "1911": "1911",
            "colt": "1911",
            "colt1911": "1911",
            "desert eagle": "Desert Eagle",
            "deserteagle": "Desert Eagle",
            "deagle": "Desert Eagle",
            "glock": "Glock",
            "glock19": "Glock",
            
            # Snipers
            "svd": "SVD",
            "dragunov": "SVD",
            "m24": "M24",
            "mosin": "Mosin",
            "mosin-nagant": "Mosin",
            
            # Special
            "falling": "Falling",
            "suicide_by_relocation": "Suicide (Menu)",
            "suicide": "Suicide",
            "vehicle": "Vehicle",
            "grenade": "Grenade",
            "explosion": "Explosion",
            "fire": "Fire",
            "bleeding": "Bleeding",
            "starvation": "Starvation",
            "dehydration": "Dehydration",
            "cold": "Cold",
            "zombie": "Zombie",
            "fists": "Fists",
            "melee": "Melee",
            "knife": "Knife",
        }
        
        # Check for exact matches in our corrections dictionary
        if weapon_lower in weapon_corrections:
            return weapon_corrections[weapon_lower]
            
        # Check for partial matches
        for partial, normalized in weapon_corrections.items():
            if partial in weapon_lower:
                return normalized
                
        # If no match found, just capitalize the first letter of each word
        # and remove any extra spaces
        return " ".join(w.capitalize() for w in weapon.split())
    
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
            
            # The CSV format has been updated to include console information directly:
            # Timestamp;Killer name;Killer ID;Victim name;Victim ID;Weapon;Distance;Killer console;Victim console;Blank
            
            # However, we still need to check for the special case of console connection lines
            # These have a format with empty killer fields and non-empty victim console field
            raw_parts = line.strip().split(';')
            
            # Check if this is a connection event (has empty killer fields)
            if (len(raw_parts) >= 8 and 
                (raw_parts[1] == "" or raw_parts[1].isspace()) and 
                (raw_parts[2] == "" or raw_parts[2].isspace())):
                # This might be a connection event - check for console indicators
                # in either the traditional position or in the new console fields
                console_indicators = ["XSX", "PS5", "PC"]
                
                has_console_indicator = False
                for indicator in console_indicators:
                    # Check anywhere in raw parts for console indicators
                    if any(indicator in part for part in raw_parts if part.strip()):
                        has_console_indicator = True
                        break
                        
                if has_console_indicator:
                    logger.debug(f"Detected console connection line: {line}")
                    return None  # Skip these lines as they're not actual kill events
            
            # Extract fields with validation
            try:
                # Get timestamp which should always be present
                timestamp_str = parts[CSV_FIELDS["timestamp"]]
                
                # For the rest of the fields, use defaults if they might be missing
                killer_name = parts[CSV_FIELDS["killer_name"]] if len(parts) > CSV_FIELDS["killer_name"] else ""
                killer_id = parts[CSV_FIELDS["killer_id"]] if len(parts) > CSV_FIELDS["killer_id"] else ""
                victim_name = parts[CSV_FIELDS["victim_name"]] if len(parts) > CSV_FIELDS["victim_name"] else ""
                victim_id = parts[CSV_FIELDS["victim_id"]] if len(parts) > CSV_FIELDS["victim_id"] else ""
                
                # Handle weapon field - this is where we might have unrecognized weapons
                weapon = ""
                if len(parts) > CSV_FIELDS["weapon"]:
                    weapon = CSVParser.normalize_weapon_name(parts[CSV_FIELDS["weapon"]])
                
                # Additional validation - we need at least timestamp, victim ID and either weapon or killer ID
                if not timestamp_str or not victim_id or (not weapon and not killer_id):
                    logger.warning(f"Missing critical field values in line: {line}")
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
            
            # Get console information if available
            killer_console = ""
            victim_console = ""
            
            # Check if console fields are present in raw parts (new format)
            if len(raw_parts) > CSV_FIELDS["killer_console"]:
                killer_console = raw_parts[CSV_FIELDS["killer_console"]].strip()
            
            if len(raw_parts) > CSV_FIELDS["victim_console"]:
                victim_console = raw_parts[CSV_FIELDS["victim_console"]].strip()
            
            # Create kill event with console information
            kill_event = {
                "timestamp": timestamp,
                "killer_name": killer_name,
                "killer_id": killer_id,
                "victim_name": victim_name,
                "victim_id": victim_id,
                "weapon": weapon,
                "distance": distance,
                "killer_console": killer_console,
                "victim_console": victim_console,
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
