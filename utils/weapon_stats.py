"""
Weapon categorization and statistics utilities for Deadside weapons
"""
from typing import Dict, List, Any, Optional

# Weapon categories based on Deadside game
WEAPON_CATEGORIES = {
    # Assault Rifles
    "assault_rifles": [
        "AK-SU", "AK-SM", "AR4", "AR4-M", "Skar", "MG-36", "NK417"
    ],
    
    # Shotguns
    "shotguns": [
        "IZH-43", "Sawed-Off Shotgun", "M133", "MS590"
    ],
    
    # Pistols
    "pistols": [
        "IZH-70", "TTk", "Berta M9", "Scorp", "C1911", "P900", "F-57", "R-5"
    ],
    
    # SMGs
    "smgs": [
        "BB-19", "PP-3000", "F-10", "Fasam", "UMR45", "UAG"
    ],
    
    # Sniper Rifles
    "sniper_rifles": [
        "Mosin", "Mosin-K", "VSD", "Grom", "MR5", "S85"
    ],
    
    # Melee
    "melee": [
        "Folding Knife", "Combat Knife", "Woodcutter's Axe", "Fire Axe"
    ],
    
    # Special
    "special": [
        "Dynamite", "land_vehicle"
    ],
    
    # Death types (not weapons)
    "death_types": [
        "falling", "suicide_by_relocation"
    ]
}

# Mapping of weapons to their categories
WEAPON_TO_CATEGORY = {}
for category, weapons in WEAPON_CATEGORIES.items():
    for weapon in weapons:
        WEAPON_TO_CATEGORY[weapon] = category

def get_weapon_category(weapon_name: str) -> str:
    """
    Get the category for a given weapon name
    
    Args:
        weapon_name: The name of the weapon
        
    Returns:
        The category name, or 'unknown' if not found
    """
    if not weapon_name:
        return 'unknown'
        
    if isinstance(weapon_name, str) and weapon_name.strip() == '':
        return 'unknown'
        
    return WEAPON_TO_CATEGORY.get(weapon_name, 'unknown')
    
def is_actual_weapon(weapon_name: str) -> bool:
    """
    Check if a weapon name is an actual weapon (not a death type)
    
    Args:
        weapon_name: The name of the weapon
        
    Returns:
        True if it's an actual weapon, False otherwise
    """
    if not weapon_name:
        return False
    
    return (weapon_name not in WEAPON_CATEGORIES['death_types'] and
            weapon_name != 'land_vehicle')
    
def get_weapon_accuracy(kills: int, shots_fired: Optional[int] = None) -> Optional[float]:
    """
    Calculate weapon accuracy if shots_fired data available
    
    Args:
        kills: Number of kills with the weapon
        shots_fired: Number of shots fired with the weapon, if available
        
    Returns:
        Accuracy as a percentage or None if data unavailable
    """
    if not shots_fired:
        return None
        
    return round((kills / max(shots_fired, 1)) * 100, 1)
    
def analyze_player_weapon_stats(weapon_data: Dict[str, int]) -> Dict[str, Any]:
    """
    Analyze a player's weapon usage and provide categorized statistics
    
    Args:
        weapon_data: Dictionary of weapon names to kill counts
        
    Returns:
        Dictionary of weapon analysis data
    """
    if not weapon_data:
        return {}
        
    # Initialize category counts
    category_counts = {
        category: 0 for category in WEAPON_CATEGORIES.keys()
    }
    
    # Count kills by category
    for weapon, count in weapon_data.items():
        category = get_weapon_category(weapon)
        category_counts[category] = category_counts.get(category, 0) + count
    
    # Get most used weapon and category
    most_used_weapon = max(weapon_data.items(), key=lambda x: x[1]) if weapon_data else None
    most_used_category = max(
        [(cat, count) for cat, count in category_counts.items() 
         if cat not in ['death_types', 'special', 'unknown']],
        key=lambda x: x[1], 
        default=None
    )
    
    # Calculate total kills with actual weapons
    combat_kills = sum(count for weapon, count in weapon_data.items() 
                     if is_actual_weapon(weapon))
    
    return {
        "most_used_weapon": {
            "name": most_used_weapon[0],
            "kills": most_used_weapon[1]
        } if most_used_weapon else None,
        "most_used_category": {
            "name": most_used_category[0],
            "kills": most_used_category[1]
        } if most_used_category else None,
        "category_breakdown": {
            category: count for category, count in category_counts.items()
            if count > 0 and category not in ['death_types', 'unknown']
        },
        "combat_kills": combat_kills,
        "melee_percentage": round(
            (category_counts.get("melee", 0) / max(combat_kills, 1)) * 100, 1
        )
    }

def get_average_kill_distance(weapon: str, kills_data: List[Dict[str, Any]]) -> Optional[float]:
    """
    Calculate the average kill distance for a specific weapon
    
    Args:
        weapon: Weapon name
        kills_data: List of kill data dictionaries
        
    Returns:
        Average kill distance or None if no data
    """
    if not kills_data:
        return None
        
    # Filter kills for the specific weapon
    weapon_kills = [kill for kill in kills_data if kill.get("weapon") == weapon]
    
    if not weapon_kills:
        return None
        
    # Calculate average distance
    total_distance = sum(kill.get("distance", 0) for kill in weapon_kills)
    return round(total_distance / len(weapon_kills), 1)


# Detailed weapon information from Deadside Wiki
WEAPON_DETAILS = {
    # Assault Rifles
    "AK-SU": {
        "type": "Assault Rifle",
        "ammo": "5.45x39mm",
        "damage": 38,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Medium",
        "description": "Compact assault rifle with moderate damage and controllable recoil."
    },
    "AK-SM": {
        "type": "Assault Rifle",
        "ammo": "7.62x39mm",
        "damage": 45,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Medium",
        "description": "Reliable assault rifle with higher damage but more recoil."
    },
    "AR4": {
        "type": "Assault Rifle",
        "ammo": "5.56x45mm",
        "damage": 40,
        "fire_rate": "Full-Auto/Burst/Single",
        "effective_range": "Medium-Long",
        "description": "Versatile assault rifle with good accuracy and moderate damage."
    },
    "AR4-M": {
        "type": "Assault Rifle",
        "ammo": "5.56x45mm",
        "damage": 38,
        "fire_rate": "Full-Auto/Burst/Single",
        "effective_range": "Medium",
        "description": "Compact version of the AR4 with slightly reduced range but improved handling."
    },
    "Skar": {
        "type": "Assault Rifle",
        "ammo": "7.62x51mm",
        "damage": 52,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Medium-Long",
        "description": "High-powered battle rifle with significant damage and good range."
    },
    "MG-36": {
        "type": "Assault Rifle",
        "ammo": "5.56x45mm",
        "damage": 38,
        "fire_rate": "Full-Auto/Burst",
        "effective_range": "Medium-Long",
        "description": "Versatile assault rifle with large magazine capacity and steady fire rate."
    },
    "NK417": {
        "type": "Assault Rifle",
        "ammo": "7.62x51mm",
        "damage": 55,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Long",
        "description": "Powerful battle rifle with high damage per shot and excellent accuracy."
    },
    
    # Sniper Rifles
    "Mosin": {
        "type": "Sniper Rifle",
        "ammo": "7.62x54mmR",
        "damage": 75,
        "fire_rate": "Bolt-Action",
        "effective_range": "Long",
        "description": "Classic bolt-action rifle with high damage and accuracy."
    },
    "Mosin-K": {
        "type": "Sniper Rifle",
        "ammo": "7.62x54mmR",
        "damage": 70,
        "fire_rate": "Bolt-Action",
        "effective_range": "Medium-Long",
        "description": "Shortened variant of the Mosin with slightly reduced range but improved handling."
    },
    "VSD": {
        "type": "Sniper Rifle",
        "ammo": "7.62x54mmR",
        "damage": 85,
        "fire_rate": "Semi-Auto",
        "effective_range": "Very Long",
        "description": "Semi-automatic sniper rifle with excellent damage and range."
    },
    "Grom": {
        "type": "Sniper Rifle",
        "ammo": "7.62x54mmR",
        "damage": 95,
        "fire_rate": "Bolt-Action",
        "effective_range": "Very Long",
        "description": "High-powered bolt-action sniper rifle with extreme damage and precision."
    },
    "MR5": {
        "type": "Sniper Rifle",
        "ammo": "7.62x51mm",
        "damage": 80,
        "fire_rate": "Semi-Auto",
        "effective_range": "Long",
        "description": "Semi-automatic marksman rifle with high damage and rapid follow-up shots."
    },
    "S85": {
        "type": "Sniper Rifle",
        "ammo": "8.5x70mm",
        "damage": 105,
        "fire_rate": "Bolt-Action",
        "effective_range": "Extreme",
        "description": "Heavy sniper rifle with devastating damage and exceptional range."
    },
    
    # Shotguns
    "IZH-43": {
        "type": "Shotgun",
        "ammo": "12 Gauge",
        "damage": 95,
        "fire_rate": "Break-Action",
        "effective_range": "Close",
        "description": "Double-barrel shotgun with devastating close-range damage."
    },
    "Sawed-Off Shotgun": {
        "type": "Shotgun",
        "ammo": "12 Gauge",
        "damage": 90,
        "fire_rate": "Break-Action",
        "effective_range": "Very Close",
        "description": "Shortened shotgun with wide spread pattern but limited range."
    },
    "M133": {
        "type": "Shotgun",
        "ammo": "12 Gauge",
        "damage": 85,
        "fire_rate": "Pump-Action",
        "effective_range": "Close",
        "description": "Reliable pump-action shotgun with good capacity and solid damage."
    },
    "MS590": {
        "type": "Shotgun",
        "ammo": "12 Gauge",
        "damage": 87,
        "fire_rate": "Pump-Action",
        "effective_range": "Close",
        "description": "Tactical pump-action shotgun with improved ergonomics and reliability."
    },
    
    # Pistols
    "IZH-70": {
        "type": "Pistol",
        "ammo": "9x18mm",
        "damage": 25,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Common pistol with low damage but quick firing rate."
    },
    "TTk": {
        "type": "Pistol",
        "ammo": "7.62x25mm",
        "damage": 35,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Russian military pistol with good penetration and moderate damage."
    },
    "Berta M9": {
        "type": "Pistol",
        "ammo": "9x19mm",
        "damage": 30,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Standard military sidearm with balanced performance and good reliability."
    },
    "Scorp": {
        "type": "Pistol",
        "ammo": "9x19mm",
        "damage": 28,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Compact pistol with good capacity and moderate stopping power."
    },
    "C1911": {
        "type": "Pistol",
        "ammo": ".45 ACP",
        "damage": 45,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Classic heavy pistol with high stopping power but limited capacity."
    },
    "P900": {
        "type": "Pistol",
        "ammo": "9x19mm",
        "damage": 32,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close",
        "description": "Modern tactical pistol with polymer frame and good ergonomics."
    },
    "F-57": {
        "type": "Pistol",
        "ammo": "5.7x28mm",
        "damage": 28,
        "fire_rate": "Semi-Auto",
        "effective_range": "Close-Medium",
        "description": "High-capacity pistol with armor-penetrating rounds and low recoil."
    },
    "R-5": {
        "type": "Pistol",
        "ammo": ".357 Magnum",
        "damage": 55,
        "fire_rate": "Double-Action",
        "effective_range": "Close-Medium",
        "description": "Powerful revolver with high damage per shot but limited capacity."
    },
    
    # SMGs
    "BB-19": {
        "type": "SMG",
        "ammo": "9x19mm",
        "damage": 28,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Close-Medium",
        "description": "Compact submachine gun with high rate of fire and controllable recoil."
    },
    "PP-3000": {
        "type": "SMG",
        "ammo": "9x19mm",
        "damage": 30,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Close-Medium",
        "description": "Modern SMG with good ergonomics and reliable performance."
    },
    "F-10": {
        "type": "SMG",
        "ammo": "10mm Auto",
        "damage": 35,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Close-Medium",
        "description": "Hard-hitting SMG with larger caliber rounds for improved stopping power."
    },
    "Fasam": {
        "type": "SMG",
        "ammo": "9x19mm",
        "damage": 27,
        "fire_rate": "Full-Auto/Burst/Single",
        "effective_range": "Close-Medium",
        "description": "Versatile SMG with multiple fire modes and good handling characteristics."
    },
    "UMR45": {
        "type": "SMG",
        "ammo": ".45 ACP",
        "damage": 40,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Close-Medium",
        "description": "Powerful SMG chambered in .45 with excellent stopping power."
    },
    "UAG": {
        "type": "SMG",
        "ammo": "9x19mm",
        "damage": 32,
        "fire_rate": "Full-Auto/Single",
        "effective_range": "Close-Medium",
        "description": "Compact SMG with folding stock and good mobility."
    },
    
    # Melee
    "Folding Knife": {
        "type": "Melee",
        "damage": 35,
        "effective_range": "Melee",
        "description": "Common folding knife for stealth kills and close combat."
    },
    "Combat Knife": {
        "type": "Melee",
        "damage": 45,
        "effective_range": "Melee",
        "description": "Military-grade knife with improved lethality and durability."
    },
    "Woodcutter's Axe": {
        "type": "Melee",
        "damage": 65,
        "effective_range": "Melee",
        "description": "Heavy axe with devastating damage but slow swing speed."
    },
    "Fire Axe": {
        "type": "Melee",
        "damage": 70,
        "effective_range": "Melee",
        "description": "Large, two-handed axe with maximum melee damage potential."
    },
    
    # Special
    "Dynamite": {
        "type": "Explosive",
        "damage": 150,
        "effective_range": "Area Effect",
        "description": "Throwable explosive with large area damage and structure damage."
    },
    "land_vehicle": {
        "type": "Vehicle",
        "damage": 100,
        "effective_range": "Contact",
        "description": "Death by vehicle impact, either by accident or intentional ramming."
    },
    
    # Death types
    "falling": {
        "type": "Environmental Death",
        "description": "Death caused by falling from height."
    },
    "suicide_by_relocation": {
        "type": "System",
        "description": "Player death caused by server teleportation or manual respawn."
    }
}


def get_weapon_details(weapon_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific weapon
    
    Args:
        weapon_name: The name of the weapon
        
    Returns:
        Dictionary with weapon details or empty dict if not found
    """
    if not weapon_name:
        return {}
        
    # Return detailed info if available
    if weapon_name in WEAPON_DETAILS:
        details = WEAPON_DETAILS[weapon_name].copy()
        details["name"] = weapon_name
        details["category"] = get_weapon_category(weapon_name)
        return details
        
    # Return basic info if not in detailed database
    return {
        "name": weapon_name,
        "category": get_weapon_category(weapon_name),
        "type": get_weapon_category(weapon_name).replace("_", " ").title(),
        "description": "No detailed information available."
    }
