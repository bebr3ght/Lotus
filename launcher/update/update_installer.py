"""
Update Installer
Handles extracting and installing updates
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional

from utils.core.logging import get_named_logger
from utils.core.safe_extract import safe_extract, is_safe_path

updater_log = get_named_logger("updater", prefix="log_updater")

PERSISTENT_ROOT_FILES = ("icon.ico", "unins000.exe", "unins000.dat")

# User-provided files that should survive updates (relative to install dir)
# In frozen builds, files are under _internal/
PERSISTENT_USER_FILES = (
    # User-provided LTK patcher, not redistributed with Lotus
    "_internal/injection/tools/ltk_patcher_host.exe",
    "_internal/injection/tools/ltk_patcher_dll.dll",
)

UPDATE_RESULT_FILE = "last_update_result.txt"


def safe_remove_marker(path: Path) -> None:
    """Clear a previous run's marker so a stale failure is never reported."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        updater_log.debug(f"Could not clear the update marker {path}: {exc}")


def read_update_result(updates_root: Path) -> Optional[str]:
    """The outcome of the last applied update, and then clears it.

    The copy runs in a batch script after this process exits, so the only way
    to tell the user it failed is to leave a note behind and read it on the
    next launch.
    """
    path = updates_root / UPDATE_RESULT_FILE
    try:
        outcome = path.read_text(encoding="utf-8", errors="replace").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        updater_log.debug(f"Could not read the update marker {path}: {exc}")
        return None
    safe_remove_marker(path)
    return outcome or None

# Copies the update over the install once Lotus has exited, then starts it
# again. Its paths come in as environment variables (see install) so a path with
# non-ASCII characters never has to survive cmd's code page.
#
# The payload is a PyInstaller one-dir layout: everything except the executable
# and the icon lives under "_internal", so the plugins folder is
# %SOURCE%\_internal\Pengu Loader\plugins. Getting that prefix wrong made /XD
# exclude nothing and the plugin sync loop match nothing, which let /MIR purge
# the plugins users had installed themselves.
#
# robocopy retries a locked file 1,000,000 times 30s apart by default, which
# left the update hanging unseen: /R:5 /W:2 makes it fail and say so instead.
# Both outcomes restart the app -- the old code only restarted on success, so a
# failed update left Lotus dead with no error -- and leave a marker behind so
# the next launch can tell the user what happened.
APPLY_UPDATE_SCRIPT = r"""@echo off
setlocal enableextensions
set "PLUGINS=%SOURCE%\_internal\Pengu Loader\plugins"
set "RC=0"
echo [%date% %time%] Update start > "%LOG%"
if defined PID (
    echo [%date% %time%] Waiting for Lotus to exit >> "%LOG%"
    powershell -NoProfile -NonInteractive -Command "Wait-Process -Id %PID% -Timeout 30 -ErrorAction SilentlyContinue" >nul 2>&1
)
echo [%date% %time%] Mirroring files >> "%LOG%"
robocopy "%SOURCE%" "%DEST%" /MIR /R:5 /W:2 /NFL /NDL /NJH /NJS /XD __pycache__ "%PLUGINS%" /XF config.ini ltk_patcher_host.exe ltk_patcher_dll.dll hashes.game.txt >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] robocopy exit code %RC% >> "%LOG%"
if %RC% GEQ 8 goto :robofail

echo [%date% %time%] Updating ROSE plugins (preserving user-installed) >> "%LOG%"
if exist "%PLUGINS%" (
    if not exist "%DEST%\_internal\Pengu Loader\plugins" mkdir "%DEST%\_internal\Pengu Loader\plugins"
    for /d %%D in ("%PLUGINS%\ROSE-*") do (
        echo [%date% %time%]   Sync plugin %%~nxD >> "%LOG%"
        robocopy "%%D" "%DEST%\_internal\Pengu Loader\plugins\%%~nxD" /MIR /R:5 /W:2 /NFL /NDL /NJH /NJS /XD __pycache__ >> "%LOG%" 2>&1
        if errorlevel 8 goto :robofail
    )
)

echo [%date% %time%] Cleaning staging >> "%LOG%"
if exist "%STAGING%" rd /s /q "%STAGING%" >> "%LOG%" 2>&1
if exist "%ZIPFILE%" del "%ZIPFILE%" >> "%LOG%" 2>&1
> "%RESULT%" echo ok
echo [%date% %time%] Update done >> "%LOG%"
echo [%date% %time%] Starting Lotus >> "%LOG%"
start "" /D "%DEST%" "%DEST%\%EXE%"
exit

:robofail
echo [%date% %time%] Update FAILED (robocopy exit code %RC%) >> "%LOG%"
> "%RESULT%" echo failed %RC%
echo Update failed, details in "%LOG%"
echo.
echo Lotus could not be updated. Starting the installed version anyway.
echo Press any key to close.
pause >nul
echo [%date% %time%] Starting Lotus after a failed update >> "%LOG%"
start "" /D "%DEST%" "%DEST%\%EXE%"
exit 1
"""


class UpdateInstaller:
    """Handles update extraction and installation"""

    def __init__(self):
        pass

    def extract_update(
        self,
        zip_path: Path,
        staging_dir: Path,
        progress_callback: Callable[[int], None],
        status_callback: Callable[[str], None],
    ) -> Optional[Path]:
        """Extract update ZIP to staging directory

        Args:
            zip_path: Path to the update ZIP file
            staging_dir: Directory to extract to
            progress_callback: Callback for progress updates
            status_callback: Callback for status updates

        Returns:
            Path to extracted root directory, or None if failed
        """
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                members = zip_file.infolist()
                total_members = max(len(members), 1)
                for index, member in enumerate(members, start=1):
                    # Security: Use safe extraction to prevent path traversal attacks
                    safe_extract(zip_path, member.filename, staging_dir)
                    progress = 40 + int(20 * index / total_members)
                    progress_callback(min(progress, 60))

            extracted_root = self._resolve_extracted_root(staging_dir)
            if extracted_root is None:
                status_callback("Invalid update package")
                return None
            return extracted_root
        except Exception as exc:  # noqa: BLE001
            status_callback(f"Extraction failed: {exc}")
            updater_log.error(f"Update extraction failed: {exc}")
            return None

    def install(
        self,
        extracted_root: Path,
        install_dir: Path,
        updates_root: Path,
        zip_path: Path,
        staging_dir: Path,
        status_callback: Callable[[str], None],
    ) -> bool:
        """Start the script that copies the update over the install once Rose exits

        Args:
            extracted_root: Root directory of extracted update
            install_dir: Directory where application is installed
            updates_root: Root directory for updates
            zip_path: Path to the update ZIP file
            staging_dir: Staging directory
            status_callback: Callback for status updates

        Returns:
            True if the script started
        """
        exe_name = Path(sys.executable).name

        if not (extracted_root / exe_name).exists():
            status_callback("Update aborted: executable missing in package")
            updater_log.error(f"Executable {exe_name} not found in {extracted_root}")
            return False

        # Preserve persistent root files
        for relative_name in PERSISTENT_ROOT_FILES:
            source_path = install_dir / relative_name
            if not source_path.exists():
                continue
            target_path = extracted_root / relative_name
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
            except Exception as exc:  # noqa: BLE001
                status_callback(f"Warning: failed to preserve {relative_name}: {exc}")
                updater_log.warning(f"Failed to preserve {relative_name}: {exc}")

        # Preserve user-provided files (e.g., DLL that users must provide themselves)
        for relative_name in PERSISTENT_USER_FILES:
            source_path = install_dir / relative_name
            if not source_path.exists():
                continue
            target_path = extracted_root / relative_name
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                updater_log.info(f"Preserved user file: {relative_name}")
            except Exception as exc:  # noqa: BLE001
                status_callback(f"Warning: failed to preserve {relative_name}: {exc}")
                updater_log.warning(f"Failed to preserve user file {relative_name}: {exc}")

        batch_path = updates_root / "apply_update.bat"
        log_path = updates_root / "update.log"
        try:
            batch_path.write_text(APPLY_UPDATE_SCRIPT, encoding="ascii")
        except Exception as exc:  # noqa: BLE001
            status_callback(f"Failed to prepare updater: {exc}")
            updater_log.error(f"Failed to create batch script: {exc}")
            return False

        # cmd reads a script in the console code page: written into it, a
        # non-ASCII path (C:\Users\José) pointed nowhere and the update failed
        result_path = updates_root / "last_update_result.txt"
        safe_remove_marker(result_path)
        env = dict(
            os.environ,
            SOURCE=str(extracted_root),
            DEST=str(install_dir),
            EXE=exe_name,
            ZIPFILE=str(zip_path),
            STAGING=str(staging_dir),
            LOG=str(log_path),
            RESULT=str(result_path),
            PID=str(os.getpid()),
        )
        # With System32 missing from the user's PATH, cmd found no robocopy and
        # the update copied nothing (#363)
        system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        env["PATH"] = os.pathsep.join(
            [str(system32), str(system32 / "WindowsPowerShell" / "v1.0"), os.environ.get("PATH", "")]
        )
        # /s keeps the quotes around the path: without it, cmd drops them when
        # the path holds & or parentheses, and runs a cut off path.
        # Its own console window: the script pauses and reports when the copy
        # fails, and it inherited Lotus's hidden console before, so that pause
        # blocked forever on a window the user could neither see nor type into.
        try:
            subprocess.Popen(
                f'cmd /s /c ""{batch_path}""',
                env=env,
                close_fds=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as exc:  # noqa: BLE001
            status_callback(f"Failed to launch updater: {exc}")
            updater_log.error(f"Failed to launch installer: {exc}")
            return False

        # The files are only copied once Rose has exited: whether that worked
        # is in the script's own log
        updater_log.info(f"Update script started, its log is {log_path}")
        return True

    @staticmethod
    def _resolve_extracted_root(staging_dir: Path) -> Optional[Path]:
        """Return the directory that contains the update payload."""
        candidates = [p for p in staging_dir.iterdir() if not p.name.startswith("__MACOSX")]
        if not candidates:
            return None
        if len(candidates) == 1 and candidates[0].is_dir():
            return candidates[0]
        return staging_dir

