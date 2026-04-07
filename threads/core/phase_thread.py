#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase monitoring thread
"""

import threading
import time

from config import INTERESTING_PHASES, PHASE_POLL_INTERVAL_DEFAULT
from lcu import LCU
from state import SharedState
from utils.core.logging import get_logger, log_status

from ..handlers.swiftplay_handler import SwiftplayHandler
from ..handlers.phase_handler import PhaseHandler
from ..handlers.lobby_processor import LobbyProcessor

log = get_logger()


class PhaseThread(threading.Thread):
    """Thread for monitoring game phase changes"""
    
    INTERESTING = INTERESTING_PHASES
    
    def __init__(
        self,
        lcu: LCU,
        state: SharedState,
        interval: float = PHASE_POLL_INTERVAL_DEFAULT,
        log_transitions: bool = True,
        injection_manager=None,
        skin_scraper=None,
        db=None,
    ):
        super().__init__(daemon=True)
        self.lcu = lcu
        self.state = state
        self.interval = interval
        self.log_transitions = log_transitions
        self.injection_manager = injection_manager
        self.skin_scraper = skin_scraper
        self.db = db
        self.last_phase = None
        self._null_phase_streak = 0

        # Initialize handlers
        self.swiftplay_handler = SwiftplayHandler(lcu, state, injection_manager, skin_scraper)
        self.phase_handler = PhaseHandler(lcu, state, injection_manager, skin_scraper, self.swiftplay_handler)
        self.lobby_processor = LobbyProcessor(lcu, state, injection_manager, skin_scraper, self.swiftplay_handler)

        # Expose callback so the message handler can trigger base skin forcing directly
        state.force_base_skins_callback = self.swiftplay_handler.force_base_skins_if_needed
        state.swiftplay_handler = self.swiftplay_handler

    def run(self):
        """Main thread loop"""
        while not self.state.stop:
            try:
                # --- ГЛОБАЛЬНАЯ ЗАЩИТА: ПОТОК НИКОГДА НЕ УМРЕТ ---
                try:
                    self.lcu.refresh_if_needed()
                except (OSError, ConnectionError) as e:
                    log.debug(f"LCU refresh failed in phase thread: {e}")
                
                ph = self.lcu.phase if self.lcu.ok else None
                if ph == "None":
                    ph = None
                
                if ph is None:
                    self.state.phase = None
                    self._null_phase_streak += 1

                    if self._null_phase_streak >= 3:
                        if not self.state.is_swiftplay_mode and self.state.swiftplay_extracted_mods:
                            log.debug("[phase] Null-phase streak: clearing extracted mods (non-swiftplay)")
                            self.state.swiftplay_extracted_mods = []
                    time.sleep(self.interval)
                    continue

                self._null_phase_streak = 0
                phase_changed = (ph != self.last_phase)

                if ph == "Lobby":
                    self.lobby_processor.process_lobby_state(force=phase_changed)
                    if phase_changed:
                        try:
                            ui_thread = getattr(self.state, "ui_skin_thread", None)
                            if ui_thread:
                                ui_thread._broadcast_phase_change("Lobby")
                        except Exception as e:
                            log.debug(f"[phase] Failed to broadcast phase change to JavaScript: {e}")

                if phase_changed:
                    if ph in["ChampSelect", "FINALIZATION", "Lobby"]:
                        try:
                            ui_thread = getattr(self.state, "ui_skin_thread", None)
                            if ui_thread:
                                ui_thread._broadcast_phase_change(ph)
                        except Exception as e:
                            log.debug(f"[phase] Failed to broadcast phase change to JavaScript: {e}")
                    
                    if ph is not None and self.log_transitions and ph in self.INTERESTING:
                        log_status(log, "Phase", ph, "")
                    
                    if ph is not None:
                        self.state.phase = ph
                    
                    self.phase_handler.handle_phase_change(ph, self.last_phase)
                    
                    if self.last_phase == "Lobby" and ph != "Lobby":
                        self.lobby_processor.reset_lobby_tracking()

                    self.last_phase = ph
                elif ph == "Lobby":
                    self.lobby_processor.process_lobby_state(force=False)
                elif ph == "Matchmaking":
                    # СТРАХОВКА: Если мы в поиске, но инжект еще не сработал
                    if self.state.is_swiftplay_mode and self.swiftplay_handler and not self.swiftplay_handler._injection_triggered:
                        log.info("[phase] Periodic check: Matchmaking phase active - triggering injection")
                        self.swiftplay_handler.trigger_swiftplay_injection()
                        self.swiftplay_handler._injection_triggered = True

            except Exception as e:
                log.error(f"[phase] CRITICAL ERROR IN PHASE THREAD: {e}")
                import traceback
                log.error(traceback.format_exc())
            # --------------------------------------------------
            
            time.sleep(self.interval)