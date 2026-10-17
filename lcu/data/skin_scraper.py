#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LCU Skin Scraper - Scrape skins for a specific champion from LCU
"""

from typing import Optional, Dict, List, Tuple

from config import LCU_SKIN_SCRAPER_TIMEOUT_S, SKIN_NAME_MIN_SIMILARITY
from utils.core.logging import get_logger
from utils.core.utilities import get_champion_id_from_skin_id

from .skin_cache import ChampionSkinCache

log = get_logger()


class LCUSkinScraper:
    """Scrape skins for a specific champion from LCU API"""
    
    def __init__(self, lcu_client):
        """Initialize scraper with LCU client
        
        Args:
            lcu_client: LCU client instance
        """
        self.lcu = lcu_client
        self.cache = ChampionSkinCache()
    
    def scrape_champion_skins(self, champion_id: int, force_refresh: bool = False) -> bool:
        """Scrape all skins for a specific champion from LCU
        
        Args:
            champion_id: Champion ID to scrape skins for
            force_refresh: If True, force refresh even if already cached
            
        Returns:
            True if scraping succeeded, False otherwise
        """
        # Check if already cached
        if not force_refresh and self.cache.is_loaded_for_champion(champion_id):
            log.debug(f"[LCU-SCRAPER] Champion {champion_id} skins already cached ({len(self.cache.skins)} skins)")
            return True
        
        # Build the new cache before dropping the old one: clearing first meant a single
        # failed fetch also destroyed the previous champion's skins, and every
        # lookup afterwards degraded silently instead of using stale-but-good data
        new_cache = ChampionSkinCache()

        log.info(f"[LCU-SCRAPER] Scraping skins for champion ID {champion_id}...")
        
        # Try multiple endpoints to get champion skins
        endpoints = [
            f"/lol-game-data/assets/v1/champions/{champion_id}.json",
            f"/lol-champions/v1/inventories/scouting/champions/{champion_id}",
        ]
        
        champ_data = None
        for endpoint in endpoints:
            try:
                data = self.lcu.get(endpoint, timeout=LCU_SKIN_SCRAPER_TIMEOUT_S)
                if data and isinstance(data, dict) and 'skins' in data:
                    champ_data = data
                    log.debug(f"[LCU-SCRAPER] Successfully fetched data from {endpoint}")
                    break
            except Exception as e:
                log.debug(f"[LCU-SCRAPER] Failed to fetch from {endpoint}: {e}")
                continue
        
        if not champ_data:
            log.warning(f"[LCU-SCRAPER] Failed to scrape skins for champion {champion_id}")
            return False
        
        # Extract champion info
        new_cache.champion_id = champion_id
        new_cache.champion_name = champ_data.get('name', f'Champion{champion_id}')
        
        # Extract skins
        raw_skins = champ_data.get('skins', [])
        
        for skin in raw_skins:
            skin_id = skin.get('id')
            localized_skin_name = skin.get('name', '')
            
            if skin_id is None or not localized_skin_name:
                continue
            
            # Use localized skin name directly from LCU
            english_skin_name = localized_skin_name
            
            # Extract detailed chroma information
            raw_chromas = skin.get('chromas', [])
            chroma_details = []
            
            for chroma in raw_chromas:
                chroma_id = chroma.get('id')
                localized_chroma_name = chroma.get('name', '')
                
                if chroma_id is None:
                    continue
                
                # Use localized chroma name directly from LCU
                chroma_name = localized_chroma_name
                
                # Extract color palette from chroma
                colors = chroma.get('colors', [])
                chroma_path = chroma.get('chromaPath', '')
                
                chroma_info = {
                    'id': chroma_id,
                    'name': chroma_name,
                    'colors': colors,
                    'chromaPath': chroma_path,
                    'skinId': skin_id
                }
                
                chroma_details.append(chroma_info)
                new_cache.chroma_id_map[chroma_id] = chroma_info
            
            skin_data = {
                'skinId': skin_id,
                'championId': champion_id,
                'skinName': english_skin_name,
                'isBase': skin.get('isBase', False),
                'chromas': len(raw_chromas),
                'chromaDetails': chroma_details,
                'num': skin.get('num', 0)
            }
            
            new_cache.skins.append(skin_data)
            new_cache.skin_id_map[skin_id] = skin_data
            new_cache.skin_name_map[english_skin_name] = skin_data

        # Swap only now that the new cache is complete
        self.cache = new_cache

        log.info(f"[LCU-SCRAPER] Scraped {len(self.cache.skins)} skins for {self.cache.champion_name} (ID: {champion_id})")

        # Log first few skins for debugging
        if self.cache.skins:
            log.debug(f"[LCU-SCRAPER] Sample skins:")
            for skin in self.cache.skins[:3]:
                log.debug(f"  - {skin['skinName']} (ID: {skin['skinId']})")

        return True
    
    def find_skin_by_text(self, text: str, use_levenshtein: bool = True) -> Optional[Tuple[int, str, float]]:
        """Find best matching skin by text using Levenshtein distance

        Args:
            text: Text to match
            use_levenshtein: If True, use Levenshtein distance for fuzzy matching

        Returns:
            Tuple of (skinId, skinName, similarity_score) if found, None otherwise
        """
        if not text or not self.cache.skins:
            return None

        from utils.core.normalization import levenshtein_distance

        # Build candidate input strings.  The League client sometimes appends
        # a chroma colour as a suffix whose format varies by locale:
        #   - Portuguese: "SkinName (Renegado)"       → trailing parentheses
        #   - Russian:    "SkinName – ''Пылкость''"   → em-dash + quoted name
        # We cannot unconditionally strip these because some real skin names
        # use parentheses (e.g. prestige skins in Russian).  Instead, we try
        # both the original and a stripped variant and let the best similarity
        # score win.
        import re
        candidates = [text]
        stripped = re.sub(r"\s*(?:\([^)]*\)|–\s*'{0,2}[^']+'{0,2})\s*$", "", text)
        if stripped != text:
            candidates.append(stripped)

        # Try exact match first (both candidates)
        for candidate in candidates:
            exact_match = self.cache.get_skin_by_name(candidate)
            if exact_match:
                return (exact_match['skinId'], exact_match['skinName'], 1.0)

        # Fuzzy matching with Levenshtein distance
        if not use_levenshtein:
            return None

        best_match = None
        best_similarity = 0.0

        for skin in self.cache.skins:
            skin_name = skin['skinName']

            for candidate in candidates:
                distance = levenshtein_distance(candidate, skin_name)
                max_len = max(len(candidate), len(skin_name))
                similarity = 1.0 - (distance / max_len) if max_len > 0 else 0.0

                # Rank by similarity, not by raw distance: the two candidates have
                # different lengths (the stripped one is shorter), so the shortest
                # distance almost always belongs to the shorter candidate even when
                # it is the worse match, and the threshold below then judges it.
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = skin

        if best_match and best_similarity >= SKIN_NAME_MIN_SIMILARITY:
            return (best_match['skinId'], best_match['skinName'], best_similarity)

        if best_match:
            log.debug(
                "[LCU-SCRAPER] Rejected weak skin-name match '%s' -> '%s' "
                "(similarity=%.4f < %.4f)",
                text,
                best_match['skinName'],
                best_similarity,
                SKIN_NAME_MIN_SIMILARITY,
            )

        return None
    
    def get_chromas_for_skin(self, skin_id: int) -> Optional[list]:
        """Get chroma details for a specific skin
        
        Args:
            skin_id: Skin ID to get chromas for
            
        Returns:
            List of chroma dicts with 'id', 'name', 'colors', 'chromaPath', or None if not found
        """
        skin_data = self.cache.get_skin_by_id(skin_id)
        if skin_data:
            return skin_data.get('chromaDetails', [])
        return None

    def resolve_loading_name(self, skin_id) -> Tuple[int, Optional[str]]:
        """The id and the name the loading screen must show for a skin.

        A chroma is resolved to the skin it belongs to, because the loading
        screen prints the skin's name and a chroma id indexes a chroma row of
        the text table (and the chroma's own name over the skin's). The name is
        the one the client itself reported, so it is already localised; None
        when the champion is unknown, and the caller then reads the game's own
        language table.
        """
        try:
            skin_id = int(skin_id)
        except (TypeError, ValueError):
            return skin_id, None

        cache = self.cache
        try:
            champion_id = get_champion_id_from_skin_id(skin_id)
        except (TypeError, ValueError):
            champion_id = 0
        if champion_id and not cache.is_loaded_for_champion(champion_id):
            self.scrape_champion_skins(champion_id)
            # Scraping REPLACES the cache object. The one taken above now
            # belongs to the previous champion and answers nothing for this one,
            # so it is read again here instead of being trusted.
            cache = getattr(self, "cache", None) or cache

        base_skin_id = cache.get_base_skin_id(skin_id)
        return base_skin_id, cache.get_skin_display_name(base_skin_id)

