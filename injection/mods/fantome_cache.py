#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packed .fantome archives, reused by content instead of repacked.

Packing a mod folder takes seconds (a font, a voiceover, a carrier skin), and
two code paths need the same archive: the countdown's stager and the injection
that follows it. Without a cache the same folder is packed twice per game, and
again on the next game, and every copy is another copy of the same bytes.

The cache is content-addressed (mod_fingerprint) and bounded: entries are
removed oldest-first once it grows past its limit, so it cannot fill the disk.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

from utils.core.logging import get_logger

from .fantome import write_fantome_zip
from .fingerprint import mod_fingerprint

log = get_logger()

# A few games' worth of mods. A carrier skin is tens of MB, a map hundreds.
MAX_CACHE_BYTES = 1024 * 1024 * 1024

_lock = threading.Lock()


def cache_root(mods_dir: Path) -> Path:
    """The cache next to the mods folder (inside Rose's injection directory)."""
    return Path(mods_dir).parent / "fantome_cache"


def _prune_locked(root: Path, keep: Optional[Path], max_bytes: int) -> None:
    try:
        entries = [p for p in root.rglob("*.fantome") if p.is_file()]
    except OSError:
        return
    total = sum(p.stat().st_size for p in entries if p != keep)
    if total <= max_bytes:
        return
    # Oldest first; the archive being used right now is never removed
    for path in sorted(entries, key=lambda p: p.stat().st_mtime):
        if total <= max_bytes:
            return
        if path == keep:
            continue
        try:
            total -= path.stat().st_size
            path.unlink()
            log.debug(f"[FANTOME] Cache evicted {path.name}")
        except OSError as e:
            log.debug(f"[FANTOME] Could not evict {path}: {e}")


def prune(mods_dir: Path, max_bytes: int = MAX_CACHE_BYTES) -> None:
    """Trim the cache to *max_bytes*, oldest archives first."""
    with _lock:
        _prune_locked(cache_root(mods_dir), None, max_bytes)


def packed(mod_folder: Path, mods_dir: Path, max_bytes: int = MAX_CACHE_BYTES) -> Optional[Path]:
    """The archive for *mod_folder*, packing it only when the cache lacks it."""
    folder = Path(mod_folder)
    if not folder.is_dir():
        return None
    try:
        fingerprint = mod_fingerprint(folder)
    except OSError as e:
        log.debug(f"[FANTOME] Could not fingerprint {folder.name}: {e}")
        return None

    root = cache_root(mods_dir)
    target = root / fingerprint[:2] / f"{fingerprint}.fantome"
    with _lock:
        if target.is_file() and target.stat().st_size:
            # Recently used: keep it away from the next eviction
            try:
                os.utime(target, None)
            except OSError:
                pass
            return target

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            write_fantome_zip(folder, partial)
            partial.replace(target)
        except OSError as e:
            log.debug(f"[FANTOME] Could not pack {folder.name}: {e}")
            return None
        _prune_locked(root, target, max_bytes)
        return target
