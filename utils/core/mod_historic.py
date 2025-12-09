#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mod Historic utilities: persist and read last selected mods (map, font, announcer, other).
File format: mod_historic.json with shape:
{
  "map": "<relative_path>",
  "font": "<relative_path>",
  "announcer": "<relative_path>",
  "other": "<relative_path>" | ["<relative_path>", ...]  // string for backward compat, array for multiple
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Union, List

from utils.core.paths import get_user_data_dir


def _mod_historic_file_path() -> Path:
    data_dir = get_user_data_dir()
    return data_dir / "mod_historic.json"


def load_mod_historic() -> Dict[str, Union[str, List[str]]]:
    """Load the mod historic mapping. Returns empty dict if missing or invalid.
    
    Returns:
        Dict with mod types as keys. For "other", value can be string (legacy) or list (new).
        For other types, value is always a string.
    """
    try:
        p = _mod_historic_file_path()
        if not p.exists():
            return {}
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            result: Dict[str, Union[str, List[str]]] = {}
            for k, v in data.items():
                if isinstance(k, str):
                    if k == "other":
                        # "other" can be string (legacy) or list (new)
                        if isinstance(v, str):
                            result[k] = v
                        elif isinstance(v, list):
                            # Validate list contains only strings
                            if all(isinstance(item, str) for item in v):
                                result[k] = v
                    else:
                        # Other types are always strings
                        if isinstance(v, str):
                            result[k] = v
            return result
        return {}
    except Exception:
        return {}


def get_historic_mod(mod_type: str) -> Union[Optional[str], Optional[List[str]]]:
    """Get historic mod for a specific type (map, font, announcer, other).
    
    Args:
        mod_type: One of "map", "font", "announcer", "other"
    
    Returns:
        For "other": List of relative paths, or None if not found. For backward compat,
        if stored as string, returns a list with single item.
        For other types: Relative path string or None
    """
    m = load_mod_historic()
    value = m.get(mod_type)
    if mod_type == "other":
        if value is None:
            return None
        # Convert legacy string format to list
        if isinstance(value, str):
            return [value]
        # Already a list
        return value
    # Other types return string or None
    return value if isinstance(value, str) else None


def write_historic_mod(mod_type: str, relative_path: Union[str, List[str]]) -> None:
    """Write or overwrite the entry for the mod type.
    
    Args:
        mod_type: One of "map", "font", "announcer", "other"
        relative_path: For "other", can be a list of relative paths. For other types, must be a string.
    """
    p = _mod_historic_file_path()
    m = load_mod_historic()
    
    if mod_type == "other":
        # "other" supports multiple mods (list)
        if isinstance(relative_path, list):
            m[mod_type] = [str(p) for p in relative_path]
        else:
            # Single mod - convert to list for consistency
            m[mod_type] = [str(relative_path)]
    else:
        # Other types are single mods (string)
        if isinstance(relative_path, list):
            # If list provided for non-other type, use first item
            m[mod_type] = str(relative_path[0]) if relative_path else ""
        else:
            m[mod_type] = str(relative_path)
    
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
    except Exception:
        # Silently ignore write errors; feature is best-effort
        pass


def clear_historic_mod(mod_type: str) -> None:
    """Clear the historic entry for a specific mod type.
    
    Args:
        mod_type: One of "map", "font", "announcer", "other"
    """
    p = _mod_historic_file_path()
    m = load_mod_historic()
    if mod_type in m:
        del m[mod_type]
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
        except Exception:
            # Silently ignore write errors; feature is best-effort
            pass

