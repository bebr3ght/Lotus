#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The packed-archive cache.

Packing a mod takes seconds and two code paths need the same archive (the
countdown's stager and the injection), so without a cache the same folder is
packed twice per game and again on the next one. The cache is content-addressed
and bounded so it removes neither work nor safety: an archive is repacked only
when its folder changed, and the oldest ones go when it grows too large.
"""

import os
import tempfile
import time
import unittest
import zipfile
from unittest import mock
from pathlib import Path

from injection.mods import fantome_cache


class FantomeCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.mods = self.root / "injection" / "mods"
        self.mods.mkdir(parents=True)
        self.folder = self.mods / "Some Mod"
        self.folder.mkdir()
        (self.folder / "a.txt").write_text("hello", encoding="utf-8")

    def test_the_same_folder_is_packed_once(self):
        first = fantome_cache.packed(self.folder, self.mods)
        self.assertIsNotNone(first)

        with mock.patch("injection.mods.fantome_cache.write_fantome_zip") as pack:
            second = fantome_cache.packed(self.folder, self.mods)

        pack.assert_not_called()
        self.assertEqual(first, second)

    def test_it_is_a_real_archive(self):
        archive = fantome_cache.packed(self.folder, self.mods)
        self.assertTrue(zipfile.is_zipfile(archive))

    def test_a_changed_folder_gets_its_own_archive(self):
        first = fantome_cache.packed(self.folder, self.mods)
        (self.folder / "a.txt").write_text("changed", encoding="utf-8")
        second = fantome_cache.packed(self.folder, self.mods)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file(), "the old archive is kept for the previous game")

    def test_the_cache_lives_inside_the_injection_folder(self):
        archive = fantome_cache.packed(self.folder, self.mods)
        self.assertEqual(archive.parent.parent, self.root / "injection" / "fantome_cache")

    def test_it_never_grows_without_bound(self):
        archives = []
        for index in range(4):
            folder = self.mods / f"mod{index}"
            folder.mkdir()
            # Incompressible, so every archive has a known size on disk
            (folder / "payload.bin").write_bytes(os.urandom(4096))
            archives.append(fantome_cache.packed(folder, self.mods, max_bytes=10 ** 9))
            # distinct mtimes, so the eviction order is deterministic
            stamp = time.time() - (10 - index) * 60
            os.utime(archives[-1], (stamp, stamp))

        # Room for one archive: the rest have to go
        fantome_cache.prune(self.mods, max_bytes=5000)

        remaining = [path for path in archives if path.is_file()]
        self.assertEqual(remaining, [archives[-1]], "the newest archive is the one kept")


if __name__ == "__main__":
    unittest.main()
