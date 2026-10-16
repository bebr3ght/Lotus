#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skin ID Mapping
Handles loading and finding skin IDs by name
"""

import json
import logging
import threading
from typing import Optional
from pathlib import Path

from utils.core.paths import get_user_data_dir

log = logging.getLogger(__name__)


class SkinMapping:
    """Manages skin ID to name mappings"""
    
    def __init__(self, shared_state):
        """Initialize skin mapping
        
        Args:
            shared_state: Shared application state
        """
        self.shared_state = shared_state
        # load_mapping/clear run from the champ-select and phase threads while
        # the websocket loop looks names up, so every access is guarded. The
        # lookups iterate the mapping, which a concurrent clear() turns into a
        # "dictionary changed size during iteration" RuntimeError.
        self._lock = threading.RLock()
        self.skin_id_mapping: dict[str, int] = {}
        self.skin_id_name_mapping: dict[int, str] = {}  # Normalized (lowercase) names for backward compatibility
        self.skin_id_original_name_mapping: dict[int, str] = {}  # Original names with proper case
        self.skin_mapping_loaded = False
    
    def load_mapping(self) -> bool:
        """Load skin ID mapping from file
        
        Returns:
            True if loaded successfully, False otherwise
        """
        language = getattr(self.shared_state, "current_language", None)
        if not language:
            log.warning("[SkinMonitor] No language detected; cannot load mapping")
            return False
        
        mapping_path = (
            get_user_data_dir()
            / "resources"
            / language
            / "skin_ids.json"
        )
        
        if not mapping_path.exists():
            log.warning(
                "[SkinMonitor] Skin mapping file missing: %s", mapping_path
            )
            return False
        
        try:
            with open(mapping_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "[SkinMonitor] Failed to load skin mapping %s: %s",
                mapping_path,
                exc,
            )
            return False
        
        with self._lock:
            self.skin_id_mapping.clear()
            self.skin_id_original_name_mapping.clear()
            self.skin_id_name_mapping.clear()
            for skin_id_str, name in data.items():
                try:
                    skin_id = int(skin_id_str)
                except (TypeError, ValueError):
                    continue
                original_name = (name or "").strip()
                normalized = original_name.lower()
                if normalized and normalized not in self.skin_id_mapping:
                    self.skin_id_mapping[normalized] = skin_id
                    self.skin_id_name_mapping[skin_id] = normalized
                    self.skin_id_original_name_mapping[skin_id] = original_name  # Store original case

            loaded = len(self.skin_id_mapping)
            self.skin_mapping_loaded = True
        log.info(
            "[SkinMonitor] Loaded %s skin mappings for '%s'",
            loaded,
            language,
        )
        return True
    
    def find_skin_id_by_name(self, skin_name: str) -> Optional[int]:
        """Find skin ID by name using mapping
        
        Args:
            skin_name: Skin name to look up
            
        Returns:
            Skin ID if found, None otherwise
        """
        if not self.skin_mapping_loaded:
            if not self.load_mapping():
                return None
        
        normalized = skin_name.strip().lower()
        with self._lock:
            if normalized in self.skin_id_mapping:
                return self.skin_id_mapping[normalized]

            # Try partial matching
            for mapped_name, skin_id in self.skin_id_mapping.items():
                if normalized in mapped_name or mapped_name in normalized:
                    return skin_id

        return None
    def find_skin_name_by_skin_id(self, skin_id: int) -> Optional[str]:
        """Find skin name by id using mapping

        Args:
            skin_id: Skin id to look up

        Returns:
            Skin name with original case if found, None otherwise
        """
        if not self.skin_mapping_loaded:
            if not self.load_mapping():
                return None

        # Return original name with proper case
        with self._lock:
            if skin_id in self.skin_id_original_name_mapping:
                return self.skin_id_original_name_mapping[skin_id]
            # Fallback to normalized name if original not available (for backward compatibility)
            if skin_id in self.skin_id_name_mapping:
                return self.skin_id_name_mapping[skin_id]
        return None

    def clear(self) -> None:
        """Clear mapping cache"""
        with self._lock:
            self.skin_mapping_loaded = False
            self.skin_id_mapping.clear()
            # This one was missed, so a reloaded mapping kept answering lookups
            # from the previous champion's names.
            self.skin_id_name_mapping.clear()
            self.skin_id_original_name_mapping.clear()

