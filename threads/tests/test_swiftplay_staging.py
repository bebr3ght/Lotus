import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from state import SharedState
from threads.handlers import swiftplay_handler as swiftplay_module
from threads.handlers.swiftplay_handler import SwiftplayHandler


class _InlineThread:
    """Runs the staging thread body at start(), so the test can see the call"""

    def __init__(self, target=None, daemon=None, name=None):
        self._target = target

    def start(self):
        self._target()


class SwiftplayStagingTests(unittest.TestCase):
    """Swiftplay has no countdown: the mods are staged while the queue runs,
    so LTK Manager's patcher is already scanning when the game is created"""

    def setUp(self):
        self.lcu = MagicMock()
        self.manager = MagicMock()
        self.overlay = self.manager.injector.overlay_manager
        self.manager.injector.mods_dir = Path(tempfile.mkdtemp())
        self.handler = SwiftplayHandler(self.lcu, SharedState(), self.manager)
        thread = patch.object(swiftplay_module.threading, "Thread", _InlineThread)
        thread.start()
        self.addCleanup(thread.stop)

    def test_the_mods_are_staged_while_the_queue_runs(self):
        self.handler._stage_swiftplay_mods(["skin_141009", "ROSE-LoadingName"])

        self.overlay.open_staging.assert_called_once()
        args, kwargs = self.overlay.stage_mods.call_args
        self.assertEqual(args[1], ["skin_141009", "ROSE-LoadingName"])
        self.assertIn("selected_at", kwargs)
        self.assertTrue(args[2]())  # still wanted

    def test_a_cancelled_queue_gives_up_on_the_staging(self):
        self.handler._stage_swiftplay_mods(["skin_141009"])
        still_wanted = self.overlay.stage_mods.call_args[0][2]

        self.handler._drop_swiftplay_staging()

        self.assertFalse(still_wanted())
        self.manager.discard_early_patcher.assert_called_once()

    def test_new_picks_make_the_old_staging_give_up(self):
        self.handler._stage_swiftplay_mods(["skin_141009"])
        first = self.overlay.stage_mods.call_args[0][2]

        self.handler._stage_swiftplay_mods(["skin_142012"])

        self.assertFalse(first())
        self.assertTrue(self.overlay.stage_mods.call_args[0][2]())

    def test_no_injector_yet_is_harmless(self):
        handler = SwiftplayHandler(self.lcu, SharedState(), None)

        handler._stage_swiftplay_mods(["skin_141009"])

        self.overlay.stage_mods.assert_not_called()


if __name__ == "__main__":
    unittest.main()
