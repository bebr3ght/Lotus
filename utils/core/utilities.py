#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utilities - Shared utility functions used throughout the application
Contains common functions that are used across multiple modules
"""

# Standard library imports
import socket
from pathlib import Path
from typing import Optional

# Local imports
from utils.core.logging import get_logger

log = get_logger()


def get_champion_id_from_skin_id(skin_id: int) -> int:
    """Get champion ID from a skin ID
    
    Args:
        skin_id: The skin ID
        
    Returns:
        The champion ID (skin_id // 1000)
    """
    return skin_id // 1000


def is_default_skin(skin_id: int) -> bool:
    """Check if a skin ID is the champion's default skin
    
    Args:
        skin_id: The skin ID to check
        
    Returns:
        True if the skin ID is the champion's default skin (skin_id % 1000 == 0), False otherwise
    """
    return skin_id % 1000 == 0


def is_owned(skin_id: int, owned_skin_ids: set) -> bool:
    """Check if a skin is owned (either default skin or in owned_skin_ids)
    
    Args:
        skin_id: The skin ID to check
        owned_skin_ids: Set of owned skin IDs from LCU
        
    Returns:
        True if the skin is owned (default skin or in owned_skin_ids), False otherwise
    """
    return is_default_skin(skin_id) or (skin_id in owned_skin_ids)


def is_chroma_id(skin_id: int, chroma_id_map: Optional[dict]) -> bool:
    """Check if a skin ID is a chroma using the chroma_id_map
    
    Args:
        skin_id: The skin ID to check
        chroma_id_map: Dictionary mapping chroma IDs to chroma data (can be None)
        
    Returns:
        True if the skin ID is a chroma, False otherwise
    """
    # Special forms always count as chromas, even with no chroma map loaded
    if is_special_form_id(skin_id):
        return True

    # Check chroma_id_map if it's not None and not empty
    if chroma_id_map is not None:
        return skin_id in chroma_id_map
    
    return False


# ---------------------------------------------------------------------------
# Skins whose extra "chroma" IDs are not chromas at all
# ---------------------------------------------------------------------------
# Elementalist Lux, Sahn Uzal Mordekaiser, Spirit Blossom Morgana, Radiant Sett,
# KDA Seraphine, Viego and Gun Goddess Miss Fortune ship extra forms whose IDs are
# not in the LCU chroma list, and the Hall of Legends Kai'Sa and Ahri get a second
# ID each. Riot issues them real skin IDs, so without this table a form looks like
# an ordinary skin: the overlay puts the wrong assets on skin0 and the chroma
# wheel treats a form change as a different skin.
#
# This table is the single source of truth. It used to be spelled out in seven
# places, and they had already drifted: Viego was missing from the two copies in
# this module, so a Viego form was reported as an unowned skin and got the carrier
# injection path. Ranges are inclusive (start, stop, base).
_SPECIAL_FORM_RANGES: tuple[tuple[int, int, int], ...] = (
    (99991, 99999, 99007),     # Elementalist Lux forms
    (82998, 82999, 82054),     # Sahn Uzal Mordekaiser forms
    (25999, 25999, 25080),     # Spirit Blossom Morgana form
    (875998, 875999, 875066),  # Radiant Sett forms
    (147002, 147003, 147001),  # KDA Seraphine forms
    (234994, 234999, 234043),  # Viego forms
    (21997, 21999, 21016),     # Gun Goddess Miss Fortune forms
    (145071, 145071, 145070),  # Immortalized Legend Kai'Sa
    (103086, 103087, 103085),  # Immortalized Legend Ahri, Form 2 Ahri
)

# Base skins that look like chromas because a form of theirs shares the prefix
_SPECIAL_FORM_BASES: frozenset[int] = frozenset({
    99007,   # Elementalist Lux
    82054,   # Sahn Uzal Mordekaiser
    25080,   # Spirit Blossom Morgana
    875066,  # Radiant Sett
    147001,  # KDA Seraphine
    234043,  # Viego
    21016,   # Gun Goddess Miss Fortune
    145070,  # Risen Legend Kai'Sa
    103085,  # Risen Legend Ahri
})


def get_base_skin_id_for_special_form(chroma_id: int) -> Optional[int]:
    """The base skin a special-form ID belongs to, or None if it is ordinary.

    The one place that knows these IDs; everything else asks here.
    """
    try:
        value = int(chroma_id)
    except (TypeError, ValueError):
        return None
    for start, stop, base in _SPECIAL_FORM_RANGES:
        if start <= value <= stop:
            return base
    if value in _SPECIAL_FORM_BASES:
        return value
    return None


def is_special_form_id(chroma_id: int) -> bool:
    """Whether this ID is one of the special forms rather than a real chroma."""
    try:
        value = int(chroma_id)
    except (TypeError, ValueError):
        return False
    return any(start <= value <= stop for start, stop, _base in _SPECIAL_FORM_RANGES)


def get_base_skin_id_for_chroma(chroma_id: int, chroma_id_map: Optional[dict]) -> Optional[int]:
    """Get the base skin ID for a given chroma ID
    
    Args:
        chroma_id: The chroma ID
        chroma_id_map: Dictionary mapping chroma IDs to chroma data
        
    Returns:
        Base skin ID if found, None otherwise
    """
    try:
        # Skins whose extra forms carry real skin IDs (see the table above)
        special = get_base_skin_id_for_special_form(chroma_id)
        if special is not None:
            return special

        # Check if this chroma ID exists in the cache
        if chroma_id_map is not None:
            chroma_data = chroma_id_map.get(chroma_id)
            if chroma_data:
                return chroma_data.get('skinId')

        return None
    except Exception as e:
        log.debug(f"[UTILITIES] Error getting base skin ID for chroma {chroma_id}: {e}")
        return None
        # Check if this chroma ID exists in the cache
        if chroma_id_map is not None:
            chroma_data = chroma_id_map.get(chroma_id)
            if chroma_data:
                return chroma_data.get('skinId')
        
        return None
        
    except Exception as e:
        log.debug(f"[UTILITIES] Error getting base skin ID for chroma {chroma_id}: {e}")
        return None


def is_base_skin(skin_id: int, chroma_id_map: Optional[dict]) -> bool:
    """Check if a skin ID is a base skin (not a chroma)
    
    Args:
        skin_id: The skin ID to check
        chroma_id_map: Dictionary mapping chroma IDs to chroma data
        
    Returns:
        True if the skin is a base skin, False if it's a chroma
    """
    return not is_chroma_id(skin_id, chroma_id_map)


def is_base_skin_owned(skin_id: int, owned_skin_ids: set, chroma_id_map: Optional[dict]) -> bool:
    """Check if the base skin of a given skin is owned
    
    Args:
        skin_id: The skin ID (can be base skin or chroma)
        owned_skin_ids: Set of owned skin IDs from LCU
        chroma_id_map: Dictionary mapping chroma IDs to chroma data
        
    Returns:
        True if the base skin is owned, False otherwise
    """
    # Check if this is a base skin or a chroma
    if is_base_skin(skin_id, chroma_id_map):
        # This is a base skin, check if it's owned
        return is_owned(skin_id, owned_skin_ids)
    else:
        # This is a chroma, get its base skin and check if that's owned
        base_skin_id = get_base_skin_id_for_chroma(skin_id, chroma_id_map)
        return is_owned(base_skin_id, owned_skin_ids) if base_skin_id is not None else False


def is_selectable_owned(skin_id: int, owned_skin_ids: set, chroma_id_map: Optional[dict]) -> bool:
    """Check if an owned skin or chroma can be picked in the client

    A chroma bought without its skin (Mythic Shop) is in the inventory, but
    the client refuses it until the skin is owned too

    Args:
        skin_id: The skin or chroma ID
        owned_skin_ids: Set of owned skin IDs from LCU
        chroma_id_map: Dictionary mapping chroma IDs to chroma data

    Returns:
        True if the skin is owned and, for a chroma, its skin is owned too
    """
    if skin_id not in owned_skin_ids:
        return False
    base_skin_id = get_base_skin_id_for_chroma(skin_id, chroma_id_map)
    return base_skin_id is None or is_owned(base_skin_id, owned_skin_ids)


# No longer converting to English - using LCU localized names directly


def find_free_port(start_port: int = 50000, max_attempts: int = 100) -> Optional[int]:
    """
    Find a free port starting from start_port.
    Uses high port range (50000+) by default to avoid conflicts with common dev ports.
    
    Args:
        start_port: The starting port number to check (default: 50000)
        max_attempts: Maximum number of ports to try (default: 100)
        
    Returns:
        A free port number, or None if no free port found
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                # Port is free, return it
                log.debug(f"[UTILITIES] Found free port: {port}")
                return port
        except OSError:
            # Port is in use, try next one
            continue
    
    log.warning(f"[UTILITIES] No free port found in range {start_port}-{start_port + max_attempts - 1}")
    return None


def get_bridge_port_file() -> Path:
    """
    Get the path to the bridge port file.
    
    Returns:
        Path to bridge_port.txt in state directory
    """
    from utils.core.paths import get_state_dir
    return get_state_dir() / "bridge_port.txt"


def write_bridge_port(port: int) -> bool:
    """
    Write the bridge port to a file for plugin discovery.
    
    Args:
        port: The port number to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        port_file = get_bridge_port_file()
        port_file.write_text(str(port), encoding='utf-8')
        log.debug(f"[UTILITIES] Wrote bridge port {port} to {port_file}")
        return True
    except Exception as e:
        log.warning(f"[UTILITIES] Failed to write bridge port: {e}")
        return False


def delete_bridge_port_file() -> bool:
    """
    Delete the bridge port file (e.g., on shutdown).
    
    Returns:
        True if successful, False otherwise
    """
    try:
        port_file = get_bridge_port_file()
        if port_file.exists():
            port_file.unlink()
            log.debug(f"[UTILITIES] Deleted bridge port file {port_file}")
        return True
    except Exception as e:
        log.warning(f"[UTILITIES] Failed to delete bridge port file: {e}")
        return False
