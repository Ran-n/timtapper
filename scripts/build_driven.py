#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:11:32.226320
Revised: 2026/10/14 01:08:29.222706

Build the driven web site and Android APK the rendered tests run on (tests/rendered/, markers `web` and `android`):

    uv run python scripts/build_driven.py        # both, into build/driven/: web/ and the driven x86_64 APK
    uv run python scripts/build_driven.py web    # only the site (a few minutes)
    uv run python scripts/build_driven.py apk    # only the APK (longer)

Each is the real app built by `flet build` from a staged copy of the project with scripts/demo_driver.py and
scripts/driven_main.py beside main.py, started from driven_main instead: the demo data on screen, taking commands
from the test harness. Neither is a release: they stay in build/driven/, the APK is debug-signed, x86_64 only (the
emulator's) and installs as its own app (com.breren.timtapper.driven), never over a real timtapper.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_android import ROOT, BuildError, project_version  # noqa: E402  (it puts the app on sys.path)
from build_web import finish_site  # noqa: E402

from core.logging import get_logger, setup_logging  # noqa: E402

SCRIPTS = ROOT / "scripts"
APP = ROOT / "src" / "timtapper"
OUT = ROOT / "build" / "driven"
STAGE = OUT / "stage"
DRIVER_MODULES = ("demo_driver.py", "driven_main.py")
ENTRY = "driven_main"
ANDROID_ARCH = "x86_64"  # the emulator's: the driven APK only ever runs there
BUNDLE_ID = "com.breren.timtapper.driven"  # its own app on the phone, beside a real timtapper, never replacing it
PRODUCT = "timtapper driven"
TARGETS = ("web", "apk")

_log = get_logger("scripts.build_driven")


def stage(out: Path = STAGE, root: Path = ROOT, app: Path = APP, scripts: Path = SCRIPTS) -> Path:
    """A copy of the project flet can build: pyproject.toml and the app, with the driver modules beside main.py."""
    shutil.rmtree(out, ignore_errors=True)
    staged_app = out / app.relative_to(root)
    shutil.copytree(app, staged_app, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(root / "pyproject.toml", out / "pyproject.toml")
    for name in DRIVER_MODULES:
        shutil.copy2(scripts / name, staged_app / name)
    return out


def flet_command(target: str, version: str, staged: Path, output: Path) -> list[str]:
    if target not in TARGETS:
        raise BuildError(f"unknown driven target {target!r}: one of {', '.join(TARGETS)}")
    command = ["flet", "build", target, str(staged), "--module-name", ENTRY, "--output", str(output), "--yes"]
    command += ["--build-version", version]
    if target == "apk":  # debug-signed: it only runs on the emulator
        command += ["--arch", ANDROID_ARCH, "--bundle-id", BUNDLE_ID, "--product", PRODUCT]
    return command


def apk_name(version: str) -> str:
    return f"timtapper-{version}-driven-{ANDROID_ARCH}.apk"


def artifact(target: str, version: str | None = None, out: Path = OUT) -> Path:
    """Where the driven build of `target` lands: the site's folder, or the APK."""
    return out / "web" if target == "web" else out / apk_name(version or project_version())


def build(target: str) -> Path:
    version = project_version()
    staged = stage()
    output = OUT / target
    shutil.rmtree(output, ignore_errors=True)
    # flet's progress output has emoji; on Windows, redirected to a file or pipe, cp1252 can't encode them.
    # The signing variables are dropped: the driven APK is debug-signed, never the upload key's
    env = {k: v for k, v in os.environ.items() if not k.startswith("FLET_ANDROID_SIGNING_")} | {"PYTHONUTF8": "1"}
    _log.info("building driven %s %s", target, version)
    subprocess.run(["uv", "run", *flet_command(target, version, staged, output)], cwd=ROOT, env=env, check=True)
    if target == "web":
        finish_site(output, version)
        return output
    apks = sorted(output.glob("*.apk"))
    if len(apks) != 1:
        raise BuildError(f"flet build left {len(apks)} APKs in {output}, expected 1")
    target_path = artifact("apk", version)
    shutil.copy2(apks[0], target_path)
    _log.info("wrote %s", target_path.relative_to(ROOT))
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("targets", nargs="*", choices=TARGETS, default=list(TARGETS))
    args = parser.parse_args()
    setup_logging()
    try:
        for target in args.targets:
            build(target)
    except (BuildError, subprocess.CalledProcessError) as exc:
        _log.error("build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
