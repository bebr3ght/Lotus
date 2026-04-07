#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase Handler
Handles phase-specific logic and UI management
"""

import logging
from lcu import LCU
from lcu.core.lockfile import SWIFTPLAY_QUEUE_ID
from state import SharedState
from ui.chroma.selector import get_chroma_selector
from utils.core.logging import get_logger, log_action

log = get_logger()

_SWIFTPLAY_ACTIVE_PHASES = {"Matchmaking", "ReadyCheck", "ChampSelect", "FINALIZATION", "GameStart"}


class PhaseHandler:
    """Handles phase-specific logic"""
    
    def __init__(
        self,
        lcu: LCU,
        state: SharedState,
        injection_manager=None,
        skin_scraper=None,
        swiftplay_handler=None,
    ):
        """Initialize phase handler
        
        Args:
            lcu: LCU client instance
            state: Shared application state
            injection_manager: Injection manager instance
            skin_scraper: Skin scraper instance
            swiftplay_handler: Swiftplay handler instance
        """
        self.lcu = lcu
        self.state = state
        self.injection_manager = injection_manager
        self.skin_scraper = skin_scraper
        self.swiftplay_handler = swiftplay_handler
    
    def handle_phase_change(self, phase: str, previous_phase: str):
        """Handle phase change"""
        log.info(f"[phase] Phase transition: {previous_phase} → {phase} (swiftplay={self.state.is_swiftplay_mode}, extracted={len(self.state.swiftplay_extracted_mods)}, queue={self.state.current_queue_id})")
        
        if phase == "Matchmaking":
            if self.state.is_swiftplay_mode:
                log.info("[phase] Matchmaking phase detected in Swiftplay mode - triggering injection")
                if self.swiftplay_handler:
                    self.swiftplay_handler.monitor_swiftplay_matchmaking()
                    if not self.swiftplay_handler._injection_triggered:
                        self.swiftplay_handler.trigger_swiftplay_injection()
                        self.swiftplay_handler._injection_triggered = True
        
        elif phase == "ChampSelect":
            # Queue ID 480 fallback - handles race condition where game_mode_detector
            # hasn't set is_swiftplay_mode yet when we enter ChampSelect
            if not self.state.is_swiftplay_mode and self.state.current_queue_id == SWIFTPLAY_QUEUE_ID:
                log.info("[phase] ChampSelect - queue ID 480 detected, setting Swiftplay mode")
                self.state.is_swiftplay_mode = True
                # Ensure handler state is initialized
                if self.swiftplay_handler:
                    self.swiftplay_handler._injection_triggered = False
                    self.swiftplay_handler._last_matchmaking_state = None

            log.debug(f"[phase] ChampSelect detected - is_swiftplay_mode={self.state.is_swiftplay_mode}, extracted_mods={len(self.state.swiftplay_extracted_mods)}")
            if self.state.is_swiftplay_mode:
                # Fallback: if Matchmaking phase was missed by the poller, extraction
                # never happened.  Trigger it now before attempting the overlay.
                # Guard: skip if extraction already happened (_injection_triggered)
                # or if the overlay is already running (WS handler got there first).
                if not self.state.swiftplay_extracted_mods and self.swiftplay_handler:
                    is_overlay_running = self.swiftplay_handler._overlay_lock.locked()
                    if is_overlay_running:
                        log.debug("[phase] ChampSelect in Swiftplay mode - overlay already running, skipping extraction")
                    elif self.state.swiftplay_skin_tracking:
                        log.info("=" * 80)
                        log.info("[phase] LATE INJECTION TRIGGERED! Matchmaking phase was skipped or failed.")
                        log.info("[phase] Forcing extraction of tracked skins now!")
                        log.info("=" * 80)
                        self.swiftplay_handler.trigger_swiftplay_injection()
                        self.swiftplay_handler._injection_triggered = True
                    else:
                        log.warning("[phase] ChampSelect in Swiftplay mode - no tracked skins available for injection")

                if self.state.swiftplay_extracted_mods:
                    log.info("[phase] ChampSelect in Swiftplay mode - running overlay injection")
                    # Also ensure UI is initialized for Swiftplay mode (needed for overlay detection)
                    try:
                        from ui.core.user_interface import get_user_interface
                        user_interface = get_user_interface(self.state, self.skin_scraper)
                        if not user_interface.is_ui_initialized() and not user_interface._pending_ui_initialization:
                            user_interface.request_ui_initialization()
                    except Exception as e:
                        log.warning(f"[phase] Failed to request UI init: {e}")
                    
                    if self.swiftplay_handler:
                        import threading
                        threading.Thread(
                            target=self.swiftplay_handler.run_swiftplay_overlay,
                            daemon=True,
                            name="SwiftplayOverlay-PhaseCS"
                        ).start()
                else:
                    if self.swiftplay_handler and self.swiftplay_handler._overlay_lock.locked():
                        log.debug("[phase] ChampSelect in Swiftplay mode - overlay already running from WS handler")
                    else:
                        log.warning("[phase] ChampSelect in Swiftplay mode - no mods to inject")
            else:
                # Normal ChampSelect handling
                self.state.locked_champ_id = None
                self.state.locked_champ_timestamp = 0.0
                self.state.champion_exchange_triggered = False
                self.state.own_champion_locked = False

                # Backup UI initialization
                try:
                    from ui.core.user_interface import get_user_interface
                    user_interface = get_user_interface(self.state, self.skin_scraper)
                    if not user_interface.is_ui_initialized() and not user_interface._pending_ui_initialization:
                        user_interface.request_ui_initialization()
                except Exception as e:
                    log.warning(f"[phase] Failed to request UI initialization in ChampSelect: {e}")
        
        elif phase == "GameStart":
            if self.state.is_swiftplay_mode and self.state.swiftplay_extracted_mods:
                if self.swiftplay_handler:
                    log.info("[phase] GameStart in Swiftplay mode - running overlay injection")
                    import threading
                    threading.Thread(
                        target=self.swiftplay_handler.run_swiftplay_overlay,
                        daemon=True,
                        name="SwiftplayOverlay-GameStart"
                    ).start()
            log_action(log, "GameStart detected - UI will be destroyed after injection", "🚀")
        
        elif phase == "InProgress":
            self._handle_in_progress()
        
        elif phase == "EndOfGame":
            self._handle_end_of_game()
        
        elif phase == "ReadyCheck":
            if not self.state.is_swiftplay_mode:
                self._request_ui_destruction()
        
        else:
            # Exit champ select or other phases
            if not self.state.is_swiftplay_mode and phase is not None:
                self._request_ui_destruction()
                self._reset_state()

        if phase == "Lobby" and previous_phase != "Lobby":
            if self.state.is_swiftplay_mode and self.swiftplay_handler:
                if self.state.current_queue_id == SWIFTPLAY_QUEUE_ID:
                    log.info(f"[phase] Returned to Lobby from {previous_phase} - preserving skin tracking, resetting injection flags")
                    self.swiftplay_handler._injection_triggered = False
                    self.swiftplay_handler._overlay_done = False
                    self.swiftplay_handler._last_matchmaking_state = None
                else:
                    log.info(f"[phase] Returned to Lobby from {previous_phase} - queue changed, cleaning up Swiftplay state")
                    self.swiftplay_handler.cleanup_swiftplay_exit()
    
    def _handle_in_progress(self):
        """Handle InProgress phase"""
        # If Swiftplay overlay is still running, wait for it to finish before
        # destroying the UI — otherwise the overlay build may be interrupted.
        if self.state.is_swiftplay_mode and self.swiftplay_handler:
            overlay_lock = self.swiftplay_handler._overlay_lock
            if overlay_lock.locked():
                log.info("[phase] InProgress - waiting for Swiftplay overlay to finish before UI destruction")
            if overlay_lock.acquire(timeout=10):
                overlay_lock.release()

        self._request_ui_destruction()

        # Destroy chroma panel
        chroma_selector = get_chroma_selector()
        if chroma_selector:
            try:
                chroma_selector.panel.request_destroy()
                log.debug("[phase] Chroma panel destroy requested for InProgress")
            except Exception as e:
                log.debug(f"[phase] Error destroying chroma panel: {e}")
    
    def _handle_end_of_game(self):
        self._request_ui_destruction()

        if self.injection_manager:
            try:
                self.injection_manager.stop_overlay_process()
                log_action(log, "Stopped overlay process for EndOfGame", "🛑")
            except Exception as e:
                log.warning(f"[phase] Failed to stop overlay process: {e}")

        if self.state.is_swiftplay_mode:
            log.info("[phase] EndOfGame in Swiftplay - preserving state for next match")
    
    def _request_ui_destruction(self):
        """Request UI destruction"""
        try:
            from ui.core.user_interface import get_user_interface
            user_interface = get_user_interface(self.state, self.skin_scraper)
            user_interface.request_ui_destruction()
            log_action(log, "UI destruction requested", "")
        except Exception as e:
            log.warning(f"[phase] Failed to request UI destruction: {e}")
    
    def _reset_state(self):
        """Reset state for phase exit"""
        self.state.hovered_champ_id = None
        self.state.locked_champ_id = None
        self.state.locked_champ_timestamp = 0.0
        self.state.players_visible = 0
        self.state.locks_by_cell.clear()
        self.state.all_locked_announced = False
        self.state.loadout_countdown_active = False
        self.state.last_hover_written = False
        # Note: is_swiftplay_mode is NOT cleared here.  It is only cleared
        # via cleanup_swiftplay_exit() which also handles the associated
        # tracking/mods state atomically.  Clearing the flag alone would
        # leave orphaned swiftplay_extracted_mods / swiftplay_skin_tracking.

