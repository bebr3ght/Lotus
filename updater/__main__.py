#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rose Standalone Updater

Entry point for the standalone updater executable.
This is compiled separately and runs independently of the main Rose application.

Usage:
    updater.exe --pid <PID> --install-dir <PATH> --staging-dir <PATH> [--log-file <PATH>] [--zip-file <PATH>]

Arguments:
    --pid          PID of the main Rose process to wait for
    --install-dir  Installation directory (where Rose.exe lives)
    --staging-dir  Staging directory (extracted update files)
    --log-file     Optional log file path for debugging
    --zip-file     Optional ZIP file path to delete after update

Exit codes:
    0  - Success
    1  - Failed to wait for process
    2  - Failed to apply update
    3  - Failed to restart application
    4  - Invalid arguments
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import local modules (will be bundled with the updater)
from .updater_core import apply_update, cleanup_staging, wait_for_process_exit
from .updater_dialog import UpdaterDialog


def write_log(log_file: Optional[Path], message: str) -> None:
    """Append a timestamped message to the log file."""
    if log_file is None:
        return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # Silent fail - logging should never break updater


def main() -> int:
    """Main entry point for the updater."""
    parser = argparse.ArgumentParser(
        description="Rose Standalone Updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pid",
        type=int,
        required=True,
        help="PID of main Rose process to wait for",
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        required=True,
        help="Installation directory",
    )
    parser.add_argument(
        "--staging-dir",
        type=str,
        required=True,
        help="Staging directory with extracted update",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path for debugging",
    )
    parser.add_argument(
        "--zip-file",
        type=str,
        default=None,
        help="ZIP file path to delete after update",
    )

    try:
        args = parser.parse_args()
    except SystemExit:
        return 4

    # Convert paths
    install_dir = Path(args.install_dir)
    staging_dir = Path(args.staging_dir)
    log_file = Path(args.log_file) if args.log_file else None
    zip_file = Path(args.zip_file) if args.zip_file else None

    # Validate paths
    if not staging_dir.exists():
        print(f"Error: Staging directory does not exist: {staging_dir}")
        return 4

    if not install_dir.exists():
        print(f"Error: Install directory does not exist: {install_dir}")
        return 4

    # Initialize logging
    if log_file:
        write_log(log_file, "=" * 60)
        write_log(log_file, "Rose Updater Started")
        write_log(log_file, f"PID to wait for: {args.pid}")
        write_log(log_file, f"Install dir: {install_dir}")
        write_log(log_file, f"Staging dir: {staging_dir}")
        if zip_file:
            write_log(log_file, f"ZIP file: {zip_file}")

    # Create progress dialog
    dialog = UpdaterDialog("Rose Updater")

    def status(msg: str) -> None:
        """Update dialog status and log."""
        dialog.set_status(msg)
        write_log(log_file, msg)

    try:
        # Step 1: Wait for main process to exit
        status(f"Waiting for Rose to close (PID: {args.pid})...")

        if not wait_for_process_exit(args.pid, timeout=60.0, status_callback=status):
            status("Warning: Could not confirm process exit")
            write_log(log_file, "WARNING: Process may still be running")

        # Additional delay for file handle cleanup by OS
        status("Preparing update...")
        time.sleep(1.5)

        # Step 2: Apply update
        status("Applying update...")

        success, failed_files = apply_update(
            staging_dir, install_dir, status_callback=status
        )

        if not success:
            status(f"Update completed with {len(failed_files)} failed files")
            write_log(log_file, f"Failed files: {failed_files}")
            # Continue anyway - partial update might still work
        else:
            write_log(log_file, "All files copied successfully")

        # Step 3: Cleanup
        cleanup_staging(staging_dir, zip_file, status_callback=status)

        # Step 4: Restart Rose
        status("Restarting Rose...")

        exe_path = install_dir / "Rose.exe"
        if not exe_path.exists():
            status(f"Error: Rose.exe not found at {exe_path}")
            write_log(log_file, f"ERROR: Rose.exe not found at {exe_path}")
            dialog.allow_close()
            time.sleep(5.0)
            return 3

        try:
            # Launch Rose.exe detached from this process
            subprocess.Popen(
                [str(exe_path)],
                cwd=str(install_dir),
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            write_log(log_file, "Rose.exe launched successfully")
        except Exception as e:
            status(f"Failed to restart Rose: {e}")
            write_log(log_file, f"ERROR: Failed to launch Rose.exe: {e}")
            dialog.allow_close()
            time.sleep(5.0)
            return 3

        # Success
        status("Update complete!")
        write_log(log_file, "UPDATE SUCCESSFUL")
        time.sleep(1.0)

        return 0

    except Exception as e:
        status(f"Update failed: {e}")
        write_log(log_file, f"FATAL ERROR: {e}")
        dialog.allow_close()
        time.sleep(5.0)
        return 2

    finally:
        dialog.close()


if __name__ == "__main__":
    sys.exit(main())
