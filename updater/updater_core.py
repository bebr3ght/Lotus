#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core update logic for the standalone updater.
Handles waiting for process exit, copying files with retry, and cleanup.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional, Set

from .updater_win32 import terminate_process, wait_for_process

# Files that should never be overwritten from update package
PRESERVE_FILES: Set[str] = {
    "config.ini",
    "icon.ico",
    "unins000.exe",
    "unins000.dat",
}


def should_preserve_file(rel_path: Path) -> bool:
    """
    Check if a file should be preserved during update.

    Args:
        rel_path: Relative path from install root

    Returns:
        True if file should be preserved (not overwritten)
    """
    # Direct file name matches
    if rel_path.name in PRESERVE_FILES:
        return True

    # Check for user plugins (preserve non-ROSE plugins)
    path_str = str(rel_path).replace("\\", "/")
    if "Pengu Loader/plugins/" in path_str:
        parts = path_str.split("Pengu Loader/plugins/")
        if len(parts) > 1:
            plugin_part = parts[1]
            # Preserve user plugins, allow ROSE-* plugin updates
            if not plugin_part.startswith("ROSE-"):
                return True

    return False


def wait_for_process_exit(
    pid: int,
    timeout: float = 60.0,
    status_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Wait for a process to exit with timeout.

    Args:
        pid: Process ID to wait for
        timeout: Timeout in seconds
        status_callback: Optional callback for status updates

    Returns:
        True if process exited (or was killed), False if still running
    """
    if status_callback:
        status_callback(f"Waiting for process {pid} to exit...")

    # First, try to wait gracefully
    if wait_for_process(pid, int(timeout * 1000)):
        return True

    # Process didn't exit in time, try to force terminate
    if status_callback:
        status_callback(f"Force terminating process {pid}...")

    if terminate_process(pid):
        # Wait a bit for termination to complete
        time.sleep(1.0)
        return True

    return False


def copy_file_with_retry(
    src: Path,
    dst: Path,
    max_retries: int = 10,
    initial_delay: float = 0.5,
    status_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Copy a file with retry logic for locked files.

    Uses exponential backoff: 0.5s, 1s, 2s, 4s, 8s...

    Args:
        src: Source file path
        dst: Destination file path
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        status_callback: Optional callback for status updates

    Returns:
        True if copy succeeded, False if all retries failed
    """
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                if status_callback:
                    status_callback(
                        f"File locked, retry {attempt + 1}/{max_retries}: {dst.name}"
                    )
                time.sleep(delay)
                delay = min(delay * 2, 16.0)  # Cap at 16 seconds
            else:
                if status_callback:
                    status_callback(f"Failed to copy (locked): {dst.name}")
                return False
        except Exception as e:
            if status_callback:
                status_callback(f"Error copying {dst.name}: {e}")
            return False

    return False


def apply_update(
    source_dir: Path,
    target_dir: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> tuple[bool, List[str]]:
    """
    Apply update from source_dir to target_dir.

    Strategy:
    1. Copy all files from source to target (with retry for locked files)
    2. Skip files that should be preserved
    3. Delete files in target that don't exist in source (except preserved)

    Args:
        source_dir: Directory containing update files
        target_dir: Installation directory
        status_callback: Optional callback for status updates

    Returns:
        Tuple of (success, list of failed files)
    """
    failed_files: List[str] = []

    if status_callback:
        status_callback("Scanning update files...")

    # Build list of all files in source
    source_files = [f for f in source_dir.rglob("*") if f.is_file()]
    total = len(source_files)

    if status_callback:
        status_callback(f"Applying update ({total} files)...")

    # Copy files from source to target
    for i, src_file in enumerate(source_files):
        rel_path = src_file.relative_to(source_dir)
        dst_file = target_dir / rel_path

        # Check if file should be preserved
        if should_preserve_file(rel_path) and dst_file.exists():
            continue  # Skip - preserve existing user file

        # Update status periodically
        if status_callback and (i % 20 == 0 or i == total - 1):
            status_callback(f"Copying files... ({i + 1}/{total})")

        if not copy_file_with_retry(src_file, dst_file, status_callback=status_callback):
            failed_files.append(str(rel_path))

    # Cleanup: delete files in target that don't exist in source
    if status_callback:
        status_callback("Cleaning up old files...")

    # Build set of source relative paths for faster lookup
    source_rel_paths = {f.relative_to(source_dir) for f in source_files}

    for target_file in target_dir.rglob("*"):
        if not target_file.is_file():
            continue

        rel_path = target_file.relative_to(target_dir)

        # Skip if file exists in source
        if rel_path in source_rel_paths:
            continue

        # Skip if file should be preserved
        if should_preserve_file(rel_path):
            continue

        # Try to delete the file
        try:
            target_file.unlink()
        except Exception:
            pass  # Best effort cleanup, don't fail on this

    # Clean up empty directories
    for target_subdir in sorted(target_dir.rglob("*"), reverse=True):
        if target_subdir.is_dir():
            try:
                target_subdir.rmdir()  # Only removes if empty
            except OSError:
                pass  # Directory not empty, that's fine

    success = len(failed_files) == 0
    return success, failed_files


def cleanup_staging(
    staging_dir: Path,
    zip_file: Optional[Path] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Clean up staging directory and optionally the ZIP file.

    Args:
        staging_dir: Staging directory to remove
        zip_file: Optional ZIP file to remove
        status_callback: Optional callback for status updates
    """
    if status_callback:
        status_callback("Cleaning up temporary files...")

    # Remove staging directory
    if staging_dir.exists():
        try:
            shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception:
            pass

    # Remove ZIP file
    if zip_file and zip_file.exists():
        try:
            zip_file.unlink()
        except Exception:
            pass
