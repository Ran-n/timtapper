#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 10:06:11.455263
Revised: 2026/10/14 10:07:44.148049

Build the Windows app into build/windows and two release files in dist/: a portable zip and an installer:

    uv run python scripts/build_windows.py    # dist/timtapper-<version>-windows-x64.zip and ...-windows-x64-setup.exe

`flet build windows` makes a folder, not one file: timtapper.exe is a small launcher that needs the Flutter engine,
the plugin DLLs and the bundled Python beside it. The zip is that folder; the installer (Inno Setup, compiled from
scripts/timtapper.iss) puts it under Program Files or the user's programs folder and adds Start-menu and desktop
shortcuts and an uninstaller. Flet's bundled Python also carries a debug build of every extension module
(DLLs/<name>_d.pyd), about 9 MB the app never loads; those are removed before packaging.

Needs Inno Setup 6 (winget install JRSoftware.InnoSetup); ISCC is looked up on PATH, then in the usual install folders.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # build_android, when imported from the tests

from build_android import DIST, ROOT, BuildError, project_version  # noqa: E402  (it puts the app on sys.path)
from build_web import zip_site  # noqa: E402

from core.logging import get_logger, setup_logging  # noqa: E402

OUT = ROOT / "build" / "windows"
ISS = ROOT / "scripts" / "timtapper.iss"
ICON = ROOT / "src" / "timtapper" / "assets" / "icon.ico"
LICENSE = ROOT / "LICENSE"
EXE = "timtapper.exe"
PUBLISHER = "Ran#"
URL = "https://github.com/Ran-n/timtapper"
DEBUG_SUFFIX = "_d"

_log = get_logger("scripts.build_windows")


def product_name(pyproject: Path = ROOT / "pyproject.toml") -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["tool"]["flet"]["product"]


def strip_debug_twins(folder: Path) -> dict[Path, int]:
    """Delete every <name>_d.pyd / <name>_d.dll whose release twin <name>.pyd / <name>.dll sits beside it.
    Returns each deleted file with its size; a file merely ending in _d, without a twin, is kept."""
    removed = {}
    for path in sorted(folder.rglob(f"*{DEBUG_SUFFIX}.*")):
        if path.suffix in {".pyd", ".dll"} and path.with_stem(path.stem.removesuffix(DEBUG_SUFFIX)).is_file():
            removed[path] = path.stat().st_size
            path.unlink()
    return removed


def find_iscc(environ: Mapping[str, str] = os.environ) -> Path:
    """Inno Setup's command-line compiler: on PATH, else where the per-user or the machine-wide install puts it."""
    if found := shutil.which("ISCC", path=environ.get("PATH")):
        return Path(found)
    homes = [Path(environ["LOCALAPPDATA"]) / "Programs"] if environ.get("LOCALAPPDATA") else []
    homes += [Path(environ[var]) for var in ("ProgramFiles(x86)", "ProgramFiles") if environ.get(var)]
    for home in homes:
        if (iscc := home / "Inno Setup 6" / "ISCC.exe").is_file():
            return iscc
    raise BuildError("no Inno Setup compiler (ISCC.exe): winget install JRSoftware.InnoSetup")


def utf8_bom_copy(text_file: Path, out: Path) -> Path:
    """Inno Setup reads a .txt without a byte-order mark as ANSI, garbling LICENSE's non-ASCII text."""
    out.write_text(text_file.read_text(encoding="utf-8"), encoding="utf-8-sig")
    return out


def installer_command(iscc: Path, source: Path, version: str, out_dir: Path, license_file: Path) -> list[str]:
    defines = {
        "AppName": product_name(),
        "AppVersion": version,
        "AppPublisher": PUBLISHER,
        "AppUrl": URL,
        "AppExe": EXE,
        "SourceDir": source,
        "OutputDir": out_dir,
        "OutputBase": f"timtapper-{version}-windows-x64-setup",
        "IconFile": ICON,
        "LicenseFile": license_file,
    }
    return [str(iscc), "/Q", *(f"/D{name}={value}" for name, value in defines.items()), str(ISS)]


def build() -> list[Path]:
    version = project_version()
    iscc = find_iscc()  # before the long flet build, so a missing Inno Setup fails at once
    shutil.rmtree(OUT, ignore_errors=True)
    _log.info("building windows %s", version)
    # flet's progress output has emoji; on Windows, redirected to a file or pipe, cp1252 can't encode them
    env = os.environ | {"PYTHONUTF8": "1"}
    subprocess.run(["uv", "run", "flet", "build", "windows", "--build-version", version], cwd=ROOT, env=env, check=True)
    if not (OUT / EXE).is_file():
        raise BuildError(f"flet build left no {EXE} in {OUT}")
    removed = strip_debug_twins(OUT)
    _log.info("removed %d debug modules (%.1f MB)", len(removed), sum(removed.values()) / 2**20)
    DIST.mkdir(exist_ok=True)
    portable = zip_site(OUT, DIST / f"timtapper-{version}-windows-x64.zip")
    _log.info("wrote %s", portable.relative_to(ROOT))
    license_file = utf8_bom_copy(LICENSE, ROOT / "build" / "LICENSE.txt")
    subprocess.run(installer_command(iscc, OUT, version, DIST, license_file), check=True)
    installer = DIST / f"timtapper-{version}-windows-x64-setup.exe"
    if not installer.is_file():
        raise BuildError(f"ISCC left no {installer.name} in {DIST}")
    _log.info("wrote %s", installer.relative_to(ROOT))
    return [portable, installer]


def main() -> int:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[1]).parse_args()
    setup_logging()
    try:
        build()
    except (BuildError, subprocess.CalledProcessError) as exc:
        _log.error("build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
