#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restart a game the LTK patcher missed: kill it, then reconnect to the match.

LTK Manager's patcher only overlays a game the client creates after its scan
started, and it cannot hook a frozen game: holding the game while heavy mods
build no longer helps. A game created too early is killed instead, and the
client launches it again through a reconnect, under the patcher's scan.
"""

from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional

from utils.core.logging import get_logger

try:
    import psutil
except ImportError:  # pragma: no cover - psutil ships with Rose
    psutil = None

log = get_logger()

PHASE_URI = "/lol-gameflow/v1/gameflow-phase"
RECONNECT_URI = "/lol-gameflow/v1/reconnect"
# How long the client gets to notice the game is gone (phase Reconnect), and
# how often it is asked
RECONNECT_WAIT_S = 30.0
RECONNECT_POLL_S = 0.5
# Phases in which the client is waiting for the player to return to the match:
# Reconnect is the reconnect screen, FailedToLaunch is what a game killed while
# it was still launching leaves behind (same match, same reconnect endpoint)
RECONNECT_PHASES = frozenset({"Reconnect", "FailedToLaunch"})
# Phases in which the match is still on: the client has not noticed the exit yet
MATCH_PHASES = frozenset({"InProgress", "GameStart"})
KILL_WAIT_S = 10.0


def kill_game(game) -> bool:
    """Kill the game process (frozen or running) and wait until it is gone."""
    if game is None:
        return False
    # A game Rose suspended for the hold does not always terminate while frozen:
    # the kernel queues the kill, but the suspended threads never run to their
    # end, so wait() times out. Letting it run for a moment first makes the kill
    # land; the game is closed right after, so it never reaches the match.
    try:
        if psutil is not None and game.status() == psutil.STATUS_STOPPED:
            game.resume()
    except Exception as e:  # noqa: BLE001 - a resume is best effort
        log.debug(f"[RECONNECT] Could not resume the game before killing it: {e}")
    try:
        game.kill()
        game.wait(timeout=KILL_WAIT_S)
        return True
    except Exception as e:  # psutil.NoSuchProcess: already gone, which is the goal
        if psutil is not None and isinstance(e, psutil.NoSuchProcess):
            return True
        log.warning(f"[RECONNECT] Could not kill the game process: {e}")
    # Last resort: taskkill also takes the child processes the game may spawn
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(game.pid)],
            capture_output=True,
            timeout=KILL_WAIT_S,
        )
        if result.returncode == 0:
            log.info("[RECONNECT] Closed the game with taskkill")
            return True
    except Exception as e:  # noqa: BLE001 - already reported above
        log.debug(f"[RECONNECT] taskkill failed: {e}")
    return False


def reconnect_to_game(connection=None, stopped: Optional[Callable[[], bool]] = None,
                      timeout: float = RECONNECT_WAIT_S) -> bool:
    """Ask the client to reconnect to the match once it noticed the game is
    gone (phase Reconnect, or FailedToLaunch for a game killed while it was
    still launching). The LCU uses riot:<password> Basic auth over a
    self-signed TLS certificate (LCUConnection sets both). False when the
    match ended, the session was stopped, or the client never asked."""
    if connection is None:
        from lcu.core.lcu_connection import LCUConnection
        connection = LCUConnection()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stopped is not None and stopped():
            return False
        try:
            connection.refresh_if_needed()
        except Exception as e:
            log.debug(f"[RECONNECT] Could not refresh the LCU connection: {e}")
        if connection.ok:
            phase = None
            try:
                phase = connection.session.get(connection.base + PHASE_URI, timeout=3).json()
            except Exception as e:
                log.debug(f"[RECONNECT] Could not read the gameflow phase: {e}")
            if phase in RECONNECT_PHASES:
                try:
                    response = connection.session.post(connection.base + RECONNECT_URI, timeout=5)
                    if 200 <= response.status_code < 300:
                        log.info("[RECONNECT] The client is reconnecting to the match")
                        return True
                    log.debug(f"[RECONNECT] Reconnect returned HTTP {response.status_code}")
                except Exception as e:
                    log.debug(f"[RECONNECT] Reconnect request failed: {e}")
            elif phase is not None and phase not in MATCH_PHASES:
                log.warning(f"[RECONNECT] The match is over (phase {phase}): nothing to reconnect to")
                return False
        time.sleep(RECONNECT_POLL_S)
    log.warning(f"[RECONNECT] The client did not offer a reconnect within {timeout:.0f}s")
    return False
