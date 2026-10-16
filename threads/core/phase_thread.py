#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase monitoring thread
"""

import threading
import time

from config import INTERESTING_PHASES, PHASE_POLL_INTERVAL_DEFAULT, PHASE_POLL_INTERVAL_INGAME
from lcu import LCU
from lcu.features.lcu_properties import CLIENT_HOME_PHASE
from state import SharedState
from utils.core.logging import get_logger, log_status

from ..handlers.swiftplay_handler import SwiftplayHandler
from ..handlers.phase_handler import PhaseHandler
from ..handlers.lobby_processor import LobbyProcessor

log = get_logger()

# Consecutive polls with no phase at all before the session is treated as gone.
# Roughly 1.5-2.5 s at the shipped poll rate.
_NULL_PHASE_TOLERANCE = 3


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
        self._last_raw_phase = None
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
                sleep_s = self._poll_once()
            except Exception as exc:
                log.debug("[phase] poll failed: %s", exc, exc_info=True)
                sleep_s = self.interval
            time.sleep(max(0.0, sleep_s))

    def _poll_once(self) -> float:
        """One poll of the client phase; returns how long to wait before the next.

        Split out of run() so it can be exercised without the thread loop.
        """
        try:
            self.lcu.refresh_if_needed()
        except (OSError, ConnectionError) as e:
            log.debug(f"LCU refresh failed in phase thread: {e}")
        
        ph = self.lcu.phase if self.lcu.ok else None

        # A client restart Rose's loader deferred (the client wasn't ready,
        # or a champ select was on) happens once the client is readable in
        # a safe phase: home ("None"), lobby or end of game
        if ph != self._last_raw_phase:
            self._last_raw_phase = ph
            if ph in ("None", "Lobby", "EndOfGame"):
                from utils.integration import pengu_loader
                pengu_loader.retry_deferred_restart()

        # The LCU's "None" (CLIENT_HOME_PHASE) is the client home screen, a
        # real phase, and deliberately stays the string. Folding it into
        # Python None made "no phase data" and "the player is on the home
        # screen" the same state, so the poller disagreed with the WebSocket
        # handler (which stores the raw string), had no usable phase after a
        # practice-tool game, and logged a growing "no phase" streak once a
        # second until the user entered a lobby.
        #
        # Only a genuinely absent answer is unknown. A grace period keeps a
        # transient hiccup from wiping Swiftplay state.
        if ph is None:
            self._null_phase_streak += 1
            if self._null_phase_streak == 1:
                log.info(
                    "[phase] The client stopped reporting a phase; holding %s",
                    self.state.phase,
                )
            elif self._null_phase_streak == _NULL_PHASE_TOLERANCE:
                log.warning(
                    "[phase] No phase for %d polls - treating the session as gone",
                    self._null_phase_streak,
                )

            # Only after several consecutive empty polls (~1.5-2.5 s) is the
            # phase really unknown. Publishing it immediately ended the loadout
            # ticker, whose loop requires a known phase: a single hiccup during
            # FINALIZATION threw away the rest of the countdown and the skin.
            # The cleanup runs once, on the crossing, not on every poll after.
            if self._null_phase_streak == _NULL_PHASE_TOLERANCE:
                from threads.handlers.champ_select_reset import note_phase_for_reset
                note_phase_for_reset(self.state, None)
                if self.state.is_swiftplay_mode:
                    # Swiftplay flag is still set but the phase is gone, so the
                    # session ended without EndOfGame. Full cleanup.
                    log.info("[phase] Lost phase in Swiftplay mode - cleaning up")
                    self.swiftplay_handler.cleanup_swiftplay_exit()
                elif self.state.swiftplay_extracted_mods:
                    # Flag already cleared but orphaned mods remain
                    self.state.swiftplay_extracted_mods = []

            # Unknown phase: nothing to dispatch, wait for the next poll
            return self.interval

        self._null_phase_streak = 0
        phase_changed = (ph != self.last_phase)

        if ph == "Lobby":
            self.lobby_processor.process_lobby_state(force=phase_changed)

        if phase_changed:
            # ph is always a real phase here: an absent answer was handled above
            try:
                ui_thread = getattr(self.state, "ui_skin_thread", None)
                if ui_thread:
                    ui_thread._broadcast_phase_change(ph)
            except Exception as e:
                log.debug(f"[phase] Failed to broadcast phase change to JavaScript: {e}")

            # Log phase transition
            if self.log_transitions and ph in self.INTERESTING:
                log_status(log, "Phase", ph, "")

            self.state.phase = ph

            # Handle phase change
            self.phase_handler.handle_phase_change(ph, self.last_phase)

            # Reset lobby tracking when leaving lobby
            if self.last_phase == "Lobby" and ph != "Lobby":
                self.lobby_processor.reset_lobby_tracking()

            self.last_phase = ph
        elif ph == "Lobby":
            # Phase unchanged but still in lobby – continue monitoring
            self.lobby_processor.process_lobby_state(force=False)
        elif ph == "Matchmaking":
            # СТРАХОВКА: Если мы в поиске, но инжект еще не сработал
            if self.state.is_swiftplay_mode and self.swiftplay_handler and not self.swiftplay_handler._injection_triggered:
                log.info("[phase] Periodic check: Matchmaking phase active - triggering injection")
                self.swiftplay_handler.trigger_swiftplay_injection()
                self.swiftplay_handler._injection_triggered = True

        if ph == "InProgress":
            return max(self.interval, PHASE_POLL_INTERVAL_INGAME)
        return self.interval
