#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core component initialization
"""

import ctypes
import sys
from typing import Optional, Tuple

from lcu import LCU, LCUSkinScraper
from state import SharedState, AppStatus
from injection import InjectionManager
from injection.game.game_monitor import resume_orphaned_game
from injection.mods.storage import ModStorageService
from utils.core.logging import get_logger, log_success
from utils.system.admin_utils import ensure_admin_rights
from utils.threading.thread_manager import create_daemon_thread
from config import APP_VERSION, set_config_option, get_config_file_path

log = get_logger()


def _make_skin_selector(lcu):
    """Build the callable the UI uses to select a skin in the client.

    Logs every attempt in full, because the previous behaviour was to write the
    selection silently: when auto-lock did not mark the skin as chosen there was
    nothing in the log to tell whether the write never happened, was refused, or
    landed.
    """
    from utils.core.utilities import get_champion_id_from_skin_id

    def select_skin(skin_id: int, reason: str = "") -> bool:
        if not lcu or not lcu.ok:
            log.warning(f"[AUTOLOCK] {reason or 'select'} skin {skin_id}: LCU is not connected")
            return False
        try:
            target = int(skin_id)
        except (TypeError, ValueError):
            log.warning(f"[AUTOLOCK] {reason or 'select'}: {skin_id!r} is not a skin id")
            return False

        champion_id = get_champion_id_from_skin_id(target)
        log.info(
            f"[AUTOLOCK] {reason or 'Writing'} skin {target} "
            f"(champion {champion_id}) into the client selection"
        )

        ok = False
        try:
            ok = bool(lcu.set_my_selection_skin(target))
        except Exception as exc:  # noqa: BLE001
            log.error(f"[AUTOLOCK] {reason or 'select'} skin {target} raised: {exc}", exc_info=True)
            return False

        if ok:
            log.info(f"[AUTOLOCK] Client now has skin {target} selected")
        else:
            log.warning(
                f"[AUTOLOCK] The client refused skin {target}. This is expected for a "
                "skin the account does not own: the client only accepts owned skins, "
                "and unowned ones are injected instead."
            )
        return ok

    return select_skin


def initialize_core_components(args, injection_threshold: Optional[float] = None) -> Tuple[LCU, LCUSkinScraper, SharedState, InjectionManager]:
    """
    Initialize core application components
    
    Returns:
        Tuple of (lcu, skin_scraper, state, injection_manager)
    """
    # installed_version must only follow the binary that is really on disk.
    # Stamping APP_VERSION here unconditionally erased the "an update failed"
    # signal before the updater could read it, so a broken release was
    # downloaded and applied again on every single launch.
    try:
        from launcher.update.update_sequence import reconcile_installed_version
        reconcile_installed_version(get_config_file_path())
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not reconcile installed_version: %s", exc)

    # Check for admin rights FIRST (required for injection to work)
    ensure_admin_rights()

    # Ensure mods directory layout exists early (and clean unknown root categories)
    try:
        ModStorageService()
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to initialize mods storage directories: %s", exc)
    
    # Initialize core components with error handling
    try:
        log.info("Initializing LCU client...")
        lcu = LCU(args.lockfile)
        log.info("LCU client initialized")

        log.info("Initializing skin scraper...")
        skin_scraper = LCUSkinScraper(lcu)
        log.info("Skin scraper initialized")
        
        log.info("Initializing shared state...")
        state = SharedState()
        log.info("Shared state initialized")

        # Let the UI layers write a skin into the client's champ-select
        # selection. They have no LCU of their own, and auto-lock otherwise
        # injected the skin without the client marking it as chosen.
        state.select_skin_callback = _make_skin_selector(lcu)
    except Exception as e:
        log.error("=" * 80)
        log.error("FATAL ERROR DURING INITIALIZATION")
        log.error("=" * 80)
        log.error(f"Failed to initialize core components: {e}")
        log.error(f"Error type: {type(e).__name__}")
        import traceback
        log.error(f"Traceback:\n{traceback.format_exc()}")
        log.error("=" * 80)
        
        # Show error message to user
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Rose failed to initialize:\n\n{str(e)}\n\nCheck the log file for details:\n{log.handlers[0].baseFilename if log.handlers else 'N/A'}",
                    "Rose - Initialization Error",
                    0x50010  # MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TOPMOST
                )
            except Exception:
                pass
        sys.exit(1)
    
    # Initialize injection manager with database (lazy initialization)
    try:
        log.info("Initializing injection manager...")
        injection_manager = InjectionManager(shared_state=state)
        # Listing processes takes seconds on Windows: keep it off the startup path
        create_daemon_thread(resume_orphaned_game, "OrphanedGameCheck").start()
        if injection_threshold is not None:
            log.info(f"Launcher override: setting injection threshold to {injection_threshold:.2f}s")
            injection_manager.injection_threshold = max(0.0, injection_threshold)
        log.info("Injection manager initialized")
        # Don't initialize injection system yet - wait for WebSocket to be active
        # This will be called in main/__init__.py after WebSocket is ready
        
        # Hash check is now handled by the launcher before the app starts
        # No need to check again here - launcher ensures hashes are ready
        if getattr(args, "dev", False):
            log.info("Skipping hashes.game.txt check (dev mode)")
        else:
            log.debug("Hashes should already be ready (checked by launcher)")
    except Exception as e:
        log.error("=" * 80)
        log.error("FATAL ERROR DURING INJECTION MANAGER INITIALIZATION")
        log.error("=" * 80)
        log.error(f"Failed to initialize injection manager: {e}")
        log.error(f"Error type: {type(e).__name__}")
        import traceback
        log.error(f"Traceback:\n{traceback.format_exc()}")
        log.error("=" * 80)
        
        # Show error message to user
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Rose failed to initialize injection system:\n\n{str(e)}\n\nCheck the log file for details:\n{log.handlers[0].baseFilename if log.handlers else 'N/A'}",
                    "Rose - Injection Error",
                    0x50010  # MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TOPMOST
                )
            except Exception:
                pass
        sys.exit(1)
    
    return lcu, skin_scraper, state, injection_manager

