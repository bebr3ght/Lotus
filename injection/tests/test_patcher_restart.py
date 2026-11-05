#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restarting the patcher when the mod set changed.

A stop request is answered before LTK Manager's host has unwound its scan, so a
start right after it can still be told ALREADY_RUNNING. Treating that as fatal
unloaded every mod from under the running patcher, which the game then failed
to read: a black screen instead of a missing skin.
"""

import unittest
from unittest import mock

from injection.overlay import overlay_manager as om
from injection.tools.bridge import BridgeCommandError


class _Bridge:
    def __init__(self, answers):
        self._answers = list(answers)
        self.calls = []

    def start_patcher(self):
        self.calls.append("start")
        answer = self._answers.pop(0) if self._answers else None
        if answer:
            raise BridgeCommandError(answer)

    def stop_patcher(self):
        self.calls.append("stop")


def _manager():
    manager = object.__new__(om.OverlayManager)
    manager.process_manager = None
    return manager


def _session(bridge):
    return {"bridge": bridge, "patcher_running": False, "ended": False}


class PatcherRestartTests(unittest.TestCase):
    def _start(self, answers):
        bridge = _Bridge(answers)
        with mock.patch.object(om, "LtkLogTail"), mock.patch.object(om.time, "sleep"):
            result = _manager()._start_patcher(_session(bridge))
        return result, bridge

    def test_a_stop_that_has_not_landed_yet_is_retried(self):
        result, bridge = self._start([
            "PATCHER ALREADY_RUNNING: The patcher is already running",
            "PATCHER ALREADY_RUNNING: The patcher is already running",
        ])

        self.assertTrue(result)
        self.assertEqual(bridge.calls, ["start", "stop", "start", "stop", "start"])

    def test_a_patcher_that_will_not_restart_is_kept_not_fatal(self):
        """Failing here unloads the mods the game is being served."""
        result, bridge = self._start(["PATCHER ALREADY_RUNNING"] * om.PATCHER_START_ATTEMPTS)

        self.assertTrue(result)
        self.assertEqual(bridge.calls.count("start"), om.PATCHER_START_ATTEMPTS)

    def test_another_start_error_is_still_a_failure(self):
        result, _ = self._start(["CDP unavailable"])
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
