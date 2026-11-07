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

    def test_the_global_picks_are_part_of_the_selection(self):
        self.manager.prepare_custom_mod.side_effect = lambda mod, label: mod["mod_name"]
        self.handler.state.selected_map_mod = {"mod_name": "map-x"}
        self.handler.state.selected_font_mod = {"mod_name": "font-x"}
        self.handler.state.selected_announcer_mod = {"mod_name": "ann-x"}
        self.handler.state.selected_other_mods = [
            {"mod_name": "sfx-x"},
            {"mod_name": "forcer-x", "is_map_forcer": True},
        ]

        self.assertEqual(
            self.handler._selected_global_mods(),
            ["map-x", "font-x", "ann-x", "sfx-x", "forcer-x"],
        )

    def test_a_pick_made_during_the_queue_is_added_at_injection(self):
        mods_dir = self.manager.injector.mods_dir
        (mods_dir / "skin_141009").mkdir()
        self.manager.prepare_custom_mod.side_effect = lambda mod, label: mod["mod_name"]
        self.handler.state.selected_map_mod = {"mod_name": "map-x"}

        # "gone" was taken back while the queue ran: its folder is gone too
        self.assertEqual(
            self.handler._refresh_swiftplay_mods(["skin_141009", "gone"]),
            ["skin_141009", "map-x"],
        )

    def test_picks_during_a_run_collapse_into_one_more(self):
        calls = []

        def trigger():
            calls.append(1)
            if len(calls) == 1:
                self.handler.request_restage()  # a pick while the first run goes

        with patch.object(self.handler, "trigger_swiftplay_injection", side_effect=trigger):
            self.handler.request_restage()

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
