#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chroma Selection Integration - New Workflow
Shows chroma wheel immediately when skin is detected (not during injection)
"""

# Standard library imports
import threading
from typing import TYPE_CHECKING, Optional

# Local imports
from ui.chroma.panel import get_chroma_panel
from ui.chroma.special_cases import ChromaSpecialCases
from ui.chroma.selection_handler import ChromaSelectionHandler
from utils.core.logging import get_logger
from utils.core.utilities import is_owned
from utils.core.validation import validate_skin_id, validate_skin_name

log = get_logger()


def _resolve_base_skin(skin_id: int, chroma_id_map) -> int:
    """The base skin behind a chroma or a special form, or the ID itself."""
    from utils.core.utilities import get_base_skin_id_for_chroma
    return get_base_skin_id_for_chroma(skin_id, chroma_id_map) or skin_id


class ChromaSelector:
    """
    Manages chroma selection with new workflow:
    - Show wheel immediately when UI detection finds skin with chromas
    - Clicking chroma instantly updates state.last_hovered_skin_id
    - No confirmation needed
    - Injection later uses the selected chroma ID
    """
    
    def __init__(self, skin_scraper, state):
        """
        Initialize chroma selector
        
        Args:
            skin_scraper: LCUSkinScraper instance to get chroma data
            state: SharedState instance to track selection
        """
        self.skin_scraper = skin_scraper
        self.state = state
        self.lock = threading.Lock()
        self.current_skin_id = None  # Track which skin we're showing chromas for
        
        # Get global panel manager
        lcu = skin_scraper.lcu if skin_scraper and hasattr(skin_scraper, 'lcu') else None
        self.panel = get_chroma_panel(state=state, lcu=lcu)
        
        # Initialize selection handler
        self.selection_handler = ChromaSelectionHandler(state, skin_scraper, self.panel, self.current_skin_id)
        
        # Set callback
        self.panel.on_chroma_selected = self._on_chroma_selected
    
    def _on_chroma_selected(self, chroma_id, chroma_name: str):
        """Callback when user clicks a chroma - update state immediately"""
        # Update current skin ID in handler
        self.selection_handler.current_skin_id = self.current_skin_id
        # Delegate to selection handler
        self.selection_handler.handle_selection(chroma_id, chroma_name)
    
    def show_button_for_skin(self, skin_id: int, skin_name: str, champion_name: str = None, champion_id: int = None):
        """
        Show button for a skin (called when UI detection finds any unowned skin or owned skin with chromas)
        
        The button displays:
        - Unowned skins with chromas: clickable chroma wheel + golden border + lock
        - Unowned skins without chromas: golden border + lock only (no wheel)
        - Owned skins with chromas: clickable chroma wheel (no golden border/lock)
        
        Args:
            skin_id: Skin ID to show button for
            skin_name: Display name of the skin
            champion_name: Champion name for direct path to chromas folder
            champion_id: Champion ID for direct path
            
        Raises:
            TypeError: If skin_id is not an integer or skin_name is not a string
            ValueError: If skin_id is negative or skin_name is empty
        """
        # Validate inputs
        validate_skin_id(skin_id)
        validate_skin_name(skin_name)
        
        with self.lock:
            # Check if this is a chroma ID - if so, get the base skin ID for chroma data
            base_skin_id = skin_id

            # Skins whose extra forms carry real skin IDs (Elementalist Lux,
            # Mordekaiser, Morgana, Sett, Seraphine, Viego, Miss Fortune, HoL
            # Kai'Sa/Ahri). One shared table; it used to be an if/elif chain here
            # that had fallen behind the copy the injection path used.
            special_base = ChromaSpecialCases.get_base_skin_id_for_special(skin_id)
            if special_base is not None:
                base_skin_id = special_base
                log.debug(f"[CHROMA] Special form {skin_id}, using base skin {base_skin_id} for chroma data")
            elif self.skin_scraper and self.skin_scraper.cache:
                if skin_id in self.skin_scraper.cache.chroma_id_map:
                    # This is a chroma, get its base skin ID
                    chroma_data = self.skin_scraper.cache.chroma_id_map[skin_id]
                    base_skin_id = chroma_data.get('skinId')
                    log.debug(f"[CHROMA] Detected chroma {skin_id}, using base skin {base_skin_id} for chroma data")
            
            # Get chromas for special skins or regular skins
            chromas = ChromaSpecialCases.get_chromas_for_special_skin(base_skin_id)
            if chromas is None:
                chromas = self.skin_scraper.get_chromas_for_skin(base_skin_id)
            
            # Mark ownership status on each chroma for the injection system (if chromas exist)
            owned_count = 0
            if chromas:
                for chroma in chromas:
                    chroma_id = chroma.get('id')
                    is_owned_var = is_owned(chroma_id, self.state.owned_skin_ids)
                    chroma['is_owned'] = is_owned_var  # Add ownership flag
                    if is_owned_var:
                        owned_count += 1
            
            # Show button regardless of whether chromas exist
            if chromas:
                log.debug(f"[CHROMA] Updating button for {skin_name} ({len(chromas)} total chromas, {owned_count} owned, {len(chromas) - owned_count} unowned)")
            else:
                log.debug(f"[CHROMA] Showing button for {skin_name} (no chromas)")
            
            # Check if this is a chroma selection for the same base skin
            is_chroma_selection = self._check_chroma_selection(skin_id)
            
            self.current_skin_id = skin_id
            # Update selection handler's current skin ID
            self.selection_handler.current_skin_id = skin_id
            
            # Show the button with chromas (or empty list if no chromas)
            try:
                self.panel.show_button_for_skin(skin_id, skin_name, chromas or [], champion_name, is_chroma_selection, champion_id)
            except Exception as e:
                log.error(f"[CHROMA] Failed to show button: {e}")
    
    def _check_chroma_selection(self, skin_id: int) -> bool:
        """Check if this is a chroma selection for the same base skin"""
        if self.current_skin_id is None or self.current_skin_id == skin_id:
            return False
        
        log.debug(f"[CHROMA] Checking chroma selection: current={self.current_skin_id} -> new={skin_id}")
        
        # Check if both IDs are chromas of the same base skin
        current_base_id = self.current_skin_id
        new_base_id = skin_id

        # One shared resolver for both sides: the two if/elif chains this
        # replaces had drifted apart (only one of them knew about Viego), so a
        # form switch cleared the chroma selection instead of keeping it.
        chroma_map = self.skin_scraper.cache.chroma_id_map if (self.skin_scraper and self.skin_scraper.cache) else None
        current_base_id = _resolve_base_skin(current_base_id, chroma_map)
        new_base_id = _resolve_base_skin(new_base_id, chroma_map)

        log.debug(
            "[CHROMA] Base skin of %s is %s, of %s is %s",
            self.current_skin_id, current_base_id, skin_id, new_base_id,
        )
        
        # A base-skin hover must clear a previous chroma selection. Only
        # preserve the selection when the newly detected ID is itself a
        # chroma/form of the same base skin.
        is_new_chroma = new_base_id != skin_id
        is_chroma_selection = (
            current_base_id == new_base_id and is_new_chroma
        )
        log.debug(f"[CHROMA] Base skin comparison: {current_base_id} == {new_base_id} -> is_chroma_selection={is_chroma_selection}")
        
        return is_chroma_selection
    
    def hide(self):
        """Hide the chroma panel (JavaScript plugin handles button)"""
        with self.lock:
            self.panel.hide()
            self.state.pending_chroma_selection = False
            self.current_skin_id = None
            self.selection_handler.current_skin_id = None
    
    def cleanup(self):
        """Clean up resources"""
        with self.lock:
            if self.panel:
                try:
                    self.panel.cleanup()
                except Exception as e:
                    log.debug(f"[CHROMA] Error cleaning up panel: {e}")


# Global chroma selector instance (will be initialized in main.py)
_chroma_selector = None


def init_chroma_selector(skin_scraper, state):
    """Initialize global chroma selector"""
    global _chroma_selector
    _chroma_selector = ChromaSelector(skin_scraper, state)
    log.debug("[CHROMA] Chroma selector initialized")
    return _chroma_selector


def get_chroma_selector() -> Optional[ChromaSelector]:
    """Get global chroma selector instance"""
    return _chroma_selector
