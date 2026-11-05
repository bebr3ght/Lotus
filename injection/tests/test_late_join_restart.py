#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restarting a game the overlay could not reach.

LTK Manager only overlays a game the client creates after its scan started. A
skin picked in the last few seconds of champ select lands the game first, so
the mods are not applied - and because Rose held the game frozen through its
boot, it can hang until the player kills it. Rose therefore terminates it and
asks the client to reconnect, so the game created then lands under the scan
that is already running.
"""

import time
import unittest
from unittest import mock

from injection.overlay import overlay_manager as om


def _manager():
    return object.__new__(om.OverlayManager)


def _session(**overrides):
    session = {
        "late_restart_requested": False,
        "scan_started_at": time.time(),
    }
    session.update(overrides)
    return session


class LateJoinRestartTests(unittest.TestCase):
    def _proc(self, name="League of Legends.exe", pid=4242):
        proc = mock.MagicMock()
        proc.info = {"name": name}
        proc.pid = pid
        return proc

    def _restart(self, session, procs):
        with mock.patch.object(om.psutil, "process_iter", return_value=procs), \
                mock.patch.object(om.threading, "Thread") as thread:
            result = _manager()._restart_late_game(session)
        return result, thread

    def test_a_late_overlay_restarts_the_game_and_asks_for_a_reconnect(self):
        game = self._proc()
        result, thread = self._restart(_session(), [game])

        self.assertTrue(result)
        game.terminate.assert_called_once()
        game.wait.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_other_processes_are_left_alone(self):
        other = self._proc(name="explorer.exe", pid=1)
        result, thread = self._restart(_session(), [other])

        self.assertFalse(result)
        other.terminate.assert_not_called()
        thread.return_value.start.assert_not_called()

    def test_it_restarts_only_once(self):
        game = self._proc()
        session = _session()
        with mock.patch.object(om.psutil, "process_iter", return_value=[game]), \
                mock.patch.object(om.threading, "Thread"):
            self.assertTrue(_manager()._restart_late_game(session))
            self.assertFalse(_manager()._restart_late_game(session))

        game.terminate.assert_called_once()

    def test_a_game_running_for_a_while_is_left_alone(self):
        """Past the window the player is playing: restarting would cost more."""
        game = self._proc()
        session = _session(scan_started_at=time.time() - om.LATE_RESTART_WINDOW_S - 60)
        result, thread = self._restart(session, [game])

        self.assertFalse(result)
        game.terminate.assert_not_called()
        thread.return_value.start.assert_not_called()

    def test_a_missing_psutil_is_a_no_op(self):
        with mock.patch.object(om, "PSUTIL_AVAILABLE", False):
            self.assertFalse(_manager()._restart_late_game(_session()))

    def test_the_restart_never_raises(self):
        with mock.patch.object(om.psutil, "process_iter", side_effect=OSError("gone")):
            self.assertFalse(_manager()._restart_late_game(_session()))


class _FakeLCU:
    def __init__(self, phases):
        self._phases = list(phases)
        self.base = "https://127.0.0.1:1"
        self.s = mock.MagicMock()
        self.s.post.return_value = mock.Mock(status_code=204)

    def get(self, path, timeout=1.0, *, use_cache=True):
        # Same signature as LCU.get: a call with the wrong keywords has to fail
        # here, not be swallowed as "no phase" by the caller
        if use_cache:
            raise AssertionError("the phase poll must bypass the cache")
        return self._phases.pop(0) if self._phases else "Reconnect"


class ReconnectAfterRestartTests(unittest.TestCase):
    def _run(self, phases, *, wait_s=20.0, stopped=False):
        lcu = _FakeLCU(phases)
        manager = _manager()
        manager._stopped_by_rose = lambda: stopped

        with mock.patch("lcu.core.client.LCU", return_value=lcu), \
                mock.patch.object(om, "LATE_RECONNECT_WAIT_S", wait_s), \
                mock.patch.object(om.time, "sleep"):
            manager._reconnect_after_restart()
        return lcu

    def test_it_waits_for_the_client_to_offer_reconnect_then_asks_for_it(self):
        lcu = self._run(["InProgress", "InProgress", "Reconnect"])

        lcu.s.post.assert_called_once()
        self.assertIn("/lol-gameflow/v1/reconnect", lcu.s.post.call_args.args[0])

    def test_it_gives_up_when_the_client_never_offers_it(self):
        lcu = self._run(["InProgress"] * 50, wait_s=0.0)
        lcu.s.post.assert_not_called()

    def test_a_stopped_session_does_not_reconnect(self):
        lcu = self._run(["Reconnect"], stopped=True)
        lcu.s.post.assert_not_called()

    def test_a_client_that_cannot_be_reached_is_not_fatal(self):
        manager = _manager()
        manager._stopped_by_rose = lambda: False
        with mock.patch("lcu.core.client.LCU", side_effect=RuntimeError("no lockfile")):
            manager._reconnect_after_restart()  # must not raise


if __name__ == "__main__":
    unittest.main()
