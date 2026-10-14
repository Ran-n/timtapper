#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 10:06:11.554151
Revised: 2026/10/14 10:07:44.252649

The Windows build's packaging (scripts/build_windows.py): debug modules stripped, ISCC found, the installer
command, the BOM'd licence copy, and a real installer compiled from a stand-in app folder when Inno Setup is installed.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("build_windows", _SCRIPTS / "build_windows.py")
build_windows = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_windows)

BuildError = build_windows.BuildError


@pytest.fixture
def app_folder(tmp_path):
    """A stand-in for build/windows: the launcher, a release and a debug build of two modules, and lookalikes."""
    root = tmp_path / "windows"
    (root / "DLLs").mkdir(parents=True)
    (root / build_windows.EXE).write_bytes(b"MZ")
    for name in ("_ssl.pyd", "_ssl_d.pyd", "sqlite3.dll", "sqlite3_d.dll", "lonely_d.pyd", "notes_d.txt"):
        (root / "DLLs" / name).write_bytes(b"x" * 10)
    return root


def test_strip_removes_only_debug_twins(app_folder):
    removed = build_windows.strip_debug_twins(app_folder)
    assert {p.name: size for p, size in removed.items()} == {"_ssl_d.pyd": 10, "sqlite3_d.dll": 10}
    assert sorted(p.name for p in (app_folder / "DLLs").iterdir()) == [
        "_ssl.pyd",
        "lonely_d.pyd",  # no release twin: not a debug build of anything we ship
        "notes_d.txt",
        "sqlite3.dll",
    ]


def test_strip_twice_removes_nothing(app_folder):
    build_windows.strip_debug_twins(app_folder)
    assert build_windows.strip_debug_twins(app_folder) == {}


def _fake_iscc(home):
    iscc = home / "Inno Setup 6" / "ISCC.exe"
    iscc.parent.mkdir(parents=True)
    iscc.write_bytes(b"MZ")
    return iscc


def test_find_iscc_in_the_per_user_install(tmp_path):
    iscc = _fake_iscc(tmp_path / "local" / "Programs")
    assert build_windows.find_iscc({"PATH": "", "LOCALAPPDATA": str(tmp_path / "local")}) == iscc


def test_find_iscc_in_program_files(tmp_path):
    iscc = _fake_iscc(tmp_path / "pf86")
    environ = {"PATH": "", "LOCALAPPDATA": str(tmp_path / "local"), "ProgramFiles(x86)": str(tmp_path / "pf86")}
    assert build_windows.find_iscc(environ) == iscc


def test_find_iscc_on_path_wins(tmp_path):
    on_path = tmp_path / "bin" / ("ISCC.exe" if os.name == "nt" else "ISCC")  # CI runs on Linux
    on_path.parent.mkdir()
    on_path.write_bytes(b"MZ")
    on_path.chmod(0o755)
    _fake_iscc(tmp_path / "local" / "Programs")
    found = build_windows.find_iscc({"PATH": str(on_path.parent), "LOCALAPPDATA": str(tmp_path / "local")})
    assert found.resolve() == on_path.resolve()


def test_missing_iscc_says_how_to_install_it():
    with pytest.raises(BuildError, match="winget install JRSoftware.InnoSetup"):
        build_windows.find_iscc({"PATH": ""})


def test_installer_command_names_the_versioned_setup(tmp_path):
    command = build_windows.installer_command(Path("ISCC.exe"), tmp_path / "src", "1.3.0", tmp_path, tmp_path / "L")
    assert command[0] == "ISCC.exe"
    assert command[-1] == str(build_windows.ISS)
    assert "/DOutputBase=timtapper-1.3.0-windows-x64-setup" in command
    assert "/DAppVersion=1.3.0" in command
    assert f"/DAppName={build_windows.product_name()}" in command
    assert f"/DSourceDir={tmp_path / 'src'}" in command


@pytest.mark.regression
def test_licence_copy_carries_a_utf8_bom(tmp_path):
    """Without a BOM Inno Setup read LICENSE as ANSI and showed its accented text garbled on the licence page."""
    source = tmp_path / "LICENSE"
    source.write_text("Licença · Ñ", encoding="utf-8")
    copy = build_windows.utf8_bom_copy(source, tmp_path / "LICENSE.txt")
    assert copy.read_bytes() == b"\xef\xbb\xbf" + "Licença · Ñ".encode()


def test_iss_template_refuses_a_bare_compile():
    """Compiled without the build script's defines, the .iss stops instead of making a nameless installer."""
    assert "#error" in build_windows.ISS.read_text(encoding="utf-8")


def test_compiles_a_real_installer(app_folder, tmp_path):
    try:
        iscc = build_windows.find_iscc()
    except BuildError:
        pytest.skip("Inno Setup is not installed")
    license_file = build_windows.utf8_bom_copy(build_windows.LICENSE, tmp_path / "LICENSE.txt")
    out = tmp_path / "dist"
    subprocess.run(build_windows.installer_command(iscc, app_folder, "9.9.9", out, license_file), check=True)
    setup = out / "timtapper-9.9.9-windows-x64-setup.exe"
    assert setup.is_file()
    assert setup.read_bytes()[:2] == b"MZ"


def test_main_reports_a_failed_build_and_exits_1(monkeypatch):
    def fail():
        raise BuildError("flet build left no timtapper.exe")

    errors = []
    monkeypatch.setattr(build_windows, "build", fail)
    monkeypatch.setattr(build_windows._log, "error", lambda msg, *args: errors.append(msg % args))
    monkeypatch.setattr("sys.argv", ["build_windows.py"])
    assert build_windows.main() == 1
    assert errors == ["build failed: flet build left no timtapper.exe"]


def test_main_builds(monkeypatch):
    calls = []
    monkeypatch.setattr(build_windows, "build", lambda: calls.append("build"))
    monkeypatch.setattr("sys.argv", ["build_windows.py"])
    assert build_windows.main() == 0
    assert calls == ["build"]
