#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skin Cache
Cache for champion skins scraped from LCU
"""

from typing import Dict, List, Optional


class ChampionSkinCache:
    """Cache for champion skins scraped from LCU"""
    
    def __init__(self):
        self.champion_id = None
        self.champion_name = None
        self.skins = []  # List of {skinId, skinName, isBase, chromas, chromaDetails}
        self.skin_id_map = {}  # skinId -> skin data
        self.skin_name_map = {}  # skinName -> skin data
        self.chroma_id_map = {}  # chromaId -> chroma data (for quick lookup)
    
    def clear(self):
        """Clear the cache"""
        self.champion_id = None
        self.champion_name = None
        self.skins = []
        self.skin_id_map = {}
        self.skin_name_map = {}
        self.chroma_id_map = {}
    
    def is_loaded_for_champion(self, champion_id: int) -> bool:
        """Check if cache is loaded for a specific champion"""
        return self.champion_id == champion_id and bool(self.skins)
    
    def get_skin_by_id(self, skin_id: int) -> Optional[Dict]:
        """Get skin data by skin ID"""
        return self.skin_id_map.get(skin_id)
    
    def get_skin_by_name(self, skin_name: str) -> Optional[Dict]:
        """Get skin data by skin name (exact match)"""
        return self.skin_name_map.get(skin_name)
    
    # ------------------------------------------------------------------
    # Chroma -> skin
    # ------------------------------------------------------------------

    def find_chroma(self, chroma_id) -> Optional[Dict]:
        """The chroma with that id, wherever this cache still knows it."""
        try:
            entry = self.chroma_id_map.get(chroma_id)
        except TypeError:  # an id that cannot even be looked up
            return None
        if entry:
            return entry
        # chroma_id_map is rebuilt on every scrape, and the same id was observed
        # both in and out of it between two runs of the same queue. The chroma
        # lists hanging off the skins are the fallback.
        for skin in self.skins:
            for chroma in (skin.get("chromaDetails") or ()):
                if chroma.get("id") == chroma_id:
                    return chroma
        return None

    def find_skin(self, skin_id) -> Optional[Dict]:
        """The skin with that id, wherever this cache still knows it."""
        try:
            entry = self.skin_id_map.get(skin_id)
        except TypeError:
            return None
        if entry:
            return entry
        for skin in self.skins:
            if skin.get("skinId") == skin_id:
                return skin
        return None

    def get_base_skin_id(self, skin_id):
        """The skin's id behind a chroma id; the id itself when it is a skin.

        Anything that cannot be resolved comes back unchanged: a wrong id is
        better than a wrong champion.
        """
        chroma = self.find_chroma(skin_id)
        if not chroma:
            return skin_id
        base_skin_id = chroma.get("skinId")
        return base_skin_id if base_skin_id is not None else skin_id

    def get_skin_display_name(self, skin_id) -> Optional[str]:
        """The name of the SKIN, never the chroma's own name.

        The loading screen prints this, so answering with a chroma's name is how
        "Obsidian" ended up there instead of the skin it belongs to.
        """
        base_skin_id = self.get_base_skin_id(skin_id)
        skin = self.find_skin(base_skin_id)
        name = str((skin or {}).get("skinName") or "").strip()
        if name:
            return name
        if base_skin_id == skin_id:
            return None
        # The skin itself is not in this cache (usually a stale one, see
        # find_chroma). The client's chroma name sometimes carries the skin's
        # name behind the chroma's own ("Obsidian Psy-Commander Vladimir"), so
        # the chroma's part can be cut off the front. Nothing is guessed: what is
        # left has to be the name of a skin this champion really has, otherwise
        # the caller reads the game's own language table instead.
        return self._skin_name_behind_chroma_name(skin_id)

    def _skin_name_behind_chroma_name(self, chroma_id) -> Optional[str]:
        """The skin's name inside a chroma name that carries it."""
        text = str((self.find_chroma(chroma_id) or {}).get("name") or "").strip()
        if not text:
            return None
        lowered = text.casefold()
        for skin in self.skins:
            name = str(skin.get("skinName") or "").strip()
            if not name:
                continue
            at = lowered.find(name.casefold())
            if at < 0:
                continue
            if at == 0:
                return text  # the chroma entry carries the skin's name verbatim
            if at + len(name) == len(text):
                return text[at:]  # only the chroma's own part is in front
        return None
    
    @property
    def all_skins(self) -> List[Dict]:
        """Get all skins for the cached champion"""
        return self.skins.copy()

