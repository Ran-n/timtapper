#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:45:47.553307
Revised: 2026/10/14 01:08:30.411950

The driven builds (scripts/build_driven.py): the staged project, the flet commands for the site and the APK,
where each lands, and that the APK never gets the upload key.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("build_driven", _SCRIPTS / "build_driven.py")
build_driven = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_driven)

BuildError = build_driven.BuildError


@pytest.fixture
def project(tmp_path):
    """A project shaped like this one: pyproject.toml, the app under src/timtapper, the driver modules in scripts/."""
    root = tmp_path / "project"
    app = root / "src" / "timtapper"
    (app / "ui").mkdir(parents=True)
    (app / "main.py").write_text("main")
    (app / "ui" / "app.py").write_text("ui")
    (app / "__pycache__").mkdir()
    (app / "__pycache__" / "main.cpython-314.pyc").write_bytes(b"pyc")
    (root / "pyproject.toml").write_text("[project]\n")
    scripts = root / "scripts"
    scripts.mkdir()
    for name in build_driven.DRIVER_MODULES:
        (scripts / name).write_text(name)
    return root


def test_stage_puts_the_driver_modules_beside_main(project, tmp_path):
    out = build_driven.stage(tmp_path / "stage", project, project / "src" / "timtapper", project / "scripts")
    app = out / "src" / "timtapper"
    assert (out / "pyproject.toml").read_text() == "[project]\n"
    assert (app / "main.py").read_text() == "main" and (app / "ui" / "app.py").read_text() == "ui"
    assert all((app / name).read_text() == name for name in build_driven.DRIVER_MODULES)
    assert not (app / "__pycache__").exists()  # the build compiles its own


def test_stage_starts_from_scratch(project, tmp_path):
    stale = tmp_path / "stage" / "src" / "timtapper" / "removed.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("gone from the project since the last build")
    build_driven.stage(tmp_path / "stage", project, project / "src" / "timtapper", project / "scripts")
    assert not stale.exists()


def test_web_command_starts_the_driven_entry(tmp_path):
    command = build_driven.flet_command("web", "1.3.0", tmp_path / "stage", tmp_path / "out")
    assert command[:4] == ["flet", "build", "web", str(tmp_path / "stage")]
    assert command[command.index("--module-name") + 1] == "driven_main"
    assert command[command.index("--output") + 1] == str(tmp_path / "out")
    assert "--arch" not in command


def test_apk_command_builds_its_own_x86_64_app(tmp_path):
    command = build_driven.flet_command("apk", "1.3.0", tmp_path / "stage", tmp_path / "out")
    assert command[command.index("--arch") + 1] == "x86_64"
    assert command[command.index("--bundle-id") + 1] == "com.breren.timtapper.driven"  # never the real app's id
    assert command[command.index("--build-version") + 1] == "1.3.0"
    assert "--split-per-abi" not in command  # one ABI: nothing to split


def test_unknown_target_refuses(tmp_path):
    with pytest.raises(BuildError, match="unknown driven target"):
        build_driven.flet_command("ipa", "1.3.0", tmp_path, tmp_path)


def test_artifacts_carry_the_version(tmp_path):
    assert build_driven.artifact("apk", "1.3.0", tmp_path) == tmp_path / "timtapper-1.3.0-driven-x86_64.apk"
    assert build_driven.artifact("web", "1.3.0", tmp_path) == tmp_path / "web"


def test_build_drops_the_upload_key_and_copies_the_apk(monkeypatch, tmp_path):
    seen = {}

    def run(command, cwd, env, check):
        seen["env"] = env
        out = Path(command[command.index("--output") + 1])
        out.mkdir(parents=True)
        (out / "app-release.apk").write_bytes(b"apk")

    monkeypatch.setenv("FLET_ANDROID_SIGNING_KEY_STORE", "upload.jks")
    monkeypatch.setattr(build_driven, "OUT", tmp_path)
    monkeypatch.setattr(build_driven, "stage", lambda: tmp_path / "stage")
    monkeypatch.setattr(build_driven, "artifact", lambda target, version: tmp_path / f"driven-{version}.apk")
    monkeypatch.setattr(build_driven, "ROOT", tmp_path)
    monkeypatch.setattr(build_driven.subprocess, "run", run)
    out = build_driven.build("apk")
    assert out.read_bytes() == b"apk"
    assert not any(k.startswith("FLET_ANDROID_SIGNING_") for k in seen["env"])  # debug-signed, never the upload key


def test_build_refuses_when_flet_leaves_no_apk(monkeypatch, tmp_path):
    monkeypatch.setattr(build_driven, "OUT", tmp_path)
    monkeypatch.setattr(build_driven, "stage", lambda: tmp_path / "stage")
    monkeypatch.setattr(build_driven.subprocess, "run", lambda *a, **k: None)
    with pytest.raises(BuildError, match="0 APKs"):
        build_driven.build("apk")


def test_main_reports_a_failed_build_and_exits_1(monkeypatch):
    def fail(target):
        raise subprocess.CalledProcessError(1, ["flet"])

    monkeypatch.setattr(build_driven, "build", fail)
    monkeypatch.setattr(sys, "argv", ["build_driven.py", "web"])
    assert build_driven.main() == 1


def test_main_builds_both_targets_by_default(monkeypatch):
    built = []
    monkeypatch.setattr(build_driven, "build", built.append)
    monkeypatch.setattr(sys, "argv", ["build_driven.py"])
    assert build_driven.main() == 0
    assert built == ["web", "apk"]
