#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Product identity for the build scripts.

config.py is the single source of truth for the name, the version and the
executable. Rose.spec cannot import it (PyInstaller runs specs with a
restricted sys.path), so it repeats the name -- therefore ``check_identity``
refuses to build a package when the two have drifted apart, which is how the
installer came to ship an executable that was never produced.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PY = ROOT / "config.py"
INSTALLER_ISS = ROOT / "installer.iss"


def _config_str(name: str, required: bool = True) -> str | None:
    source = CONFIG_PY.read_text(encoding="utf-8")
    match = re.search(rf'^{name}\s*=\s*"([^"]*)"', source, re.MULTILINE)
    if not match:
        if required:
            raise SystemExit(f"{name} not found in {CONFIG_PY}")
        return None
    return match.group(1)


def app_name() -> str:
    return _config_str("APP_NAME")


def app_version() -> str:
    return _config_str("APP_VERSION")


def app_exe_name() -> str:
    """The executable's file name.

    config.py spells it as an f-string off APP_NAME so the two can never
    disagree there; here it is derived the same way and cross-checked against
    any literal, because installer.iss and Rose.spec both spell it out.
    """
    derived = f"{app_name()}.exe"
    literal = _config_str("APP_EXE_NAME", required=False)
    if literal and literal != derived:
        raise SystemExit(
            f"config.py APP_EXE_NAME is {literal!r} but APP_NAME implies {derived!r}"
        )
    return derived


def dist_dir() -> Path:
    return ROOT / "dist" / app_name()


def dist_exe() -> Path:
    return dist_dir() / app_exe_name()


def installer_path() -> Path:
    """The installer file Inno Setup last compiled, newest first."""
    files = sorted((ROOT / "installer").glob(f"{app_name()}_Setup*.exe"))
    return files[-1] if files else ROOT / "installer" / f"{app_name()}_Setup.exe"


def _iss_define(name: str) -> str | None:
    source = INSTALLER_ISS.read_text(encoding="utf-8")
    match = re.search(rf'^#define {name}\s+"([^"]*)"', source, re.MULTILINE)
    return match.group(1) if match else None


def check_identity() -> None:
    """Fail loudly when config.py, installer.iss and the spec disagree.

    Every installer defect this catches shipped a build that installed
    shortcuts pointing at a file that did not exist.
    """
    problems = []

    for define, expected in (
        ("MyAppName", app_name()),
        ("MyAppExeName", app_exe_name()),
        ("MyAppVersion", app_version()),
    ):
        found = _iss_define(define)
        if found != expected:
            problems.append(f"installer.iss {define} is {found!r}, config.py says {expected!r}")

    spec = (ROOT / "Rose.spec").read_text(encoding="utf-8")
    spec_name = re.search(r"^\s*name='([^']+)'", spec, re.MULTILINE)
    if not spec_name or spec_name.group(1) != app_name():
        problems.append(
            f"Rose.spec builds {spec_name.group(1) if spec_name else 'nothing'!r}, "
            f"config.py says {app_name()!r}"
        )

    if problems:
        raise SystemExit(
            "Product identity is inconsistent, refusing to package:\n  - "
            + "\n  - ".join(problems)
        )