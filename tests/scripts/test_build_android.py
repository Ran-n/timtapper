#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 11:04:05.049410
Revised: 2026/10/13 16:36:23.152207

Release Android builds: version codes, signing environment, flet command, dist names and the
upload-key certificate check (against real keytool/jarsigner signatures for bundles and real
apksigner v2/v3 signatures for APKs).
"""

import importlib.util
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "build_android.py"
_spec = importlib.util.spec_from_file_location("build_android", _PATH)
build_android = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_android)

BuildError = build_android.BuildError
PASSWORD = "test-password"
needs_jdk = pytest.mark.skipif(not shutil.which("keytool") or not shutil.which("jarsigner"), reason="needs a JDK")


def _apksigner() -> Path | None:
    try:
        return build_android.find_apksigner()
    except build_android.BuildError:
        return None


needs_apksigner = pytest.mark.skipif(
    not shutil.which("keytool") or _apksigner() is None, reason="needs a JDK and the Android SDK build-tools"
)


def test_version_code_examples():
    assert build_android.version_code("1.1.0") == 101_000_000
    assert build_android.version_code("1.1.1") == 101_010_000
    assert build_android.version_code("0.5.2") == 5_020_000
    assert build_android.version_code("20.99.99") == 2_099_990_000


@pytest.mark.parametrize("version", ["1.1", "1.1.0rc1", "v1.1.0", ""])
def test_version_code_rejects_non_semver(version):
    with pytest.raises(BuildError, match="MAJOR.MINOR.PATCH"):
        build_android.version_code(version)


@pytest.mark.parametrize("version", ["1.100.0", "1.0.100"])
def test_version_code_rejects_three_digit_minor_or_patch(version):
    with pytest.raises(BuildError, match="below 100"):
        build_android.version_code(version)


def test_version_code_rejects_past_play_limit():
    with pytest.raises(BuildError, match="limit"):
        build_android.version_code("21.0.0")


versions = st.tuples(st.integers(0, 20), st.integers(0, 99), st.integers(0, 99))


@pytest.mark.property
@given(versions, versions)
def test_every_apk_of_a_newer_release_sorts_above_the_older_ones(a, b):
    """Flutter's --split-per-abi adds abi * 1000 (abi 1, 2 or 4); that must never reorder releases."""
    older, newer = sorted((a, b))
    if older == newer:
        return
    low = build_android.version_code("{}.{}.{}".format(*older))
    high = build_android.version_code("{}.{}.{}".format(*newer))
    assert high > low + 4 * 1000


def test_project_version_reads_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "3.2.1"\n', encoding="utf-8")
    assert build_android.project_version(pyproject) == "3.2.1"


@pytest.fixture
def key_files(tmp_path):
    store = tmp_path / "upload.jks"
    store.write_bytes(b"not read here")
    password = tmp_path / "upload.pass"
    password.write_text(f"{PASSWORD}\n", encoding="utf-8")
    return store, password


def test_signing_env_fills_defaults(key_files):
    store, password = key_files
    env = build_android.signing_env({"PATH": "x"}, store, password)
    assert env == {
        "PATH": "x",
        build_android.STORE_ENV: str(store),
        build_android.ALIAS_ENV: "upload",
        build_android.STORE_PASSWORD_ENV: PASSWORD,
        build_android.KEY_PASSWORD_ENV: PASSWORD,
    }


def test_signing_env_keeps_values_already_set(key_files, tmp_path):
    store, password = key_files
    other = tmp_path / "other.jks"
    other.write_bytes(b"")
    given_env = {
        build_android.STORE_ENV: str(other),
        build_android.ALIAS_ENV: "release",
        build_android.STORE_PASSWORD_ENV: "store",
        build_android.KEY_PASSWORD_ENV: "key",
    }
    assert build_android.signing_env(given_env, store, password) == given_env


def test_signing_env_does_not_need_password_file_when_password_set(key_files, tmp_path):
    store, _ = key_files
    env = build_android.signing_env({build_android.STORE_PASSWORD_ENV: "s"}, store, tmp_path / "missing.pass")
    assert env[build_android.KEY_PASSWORD_ENV] == "s"


def test_signing_env_without_key_store_refuses(tmp_path):
    with pytest.raises(BuildError, match="no upload key store"):
        build_android.signing_env({}, tmp_path / "missing.jks", tmp_path / "missing.pass")


def test_signing_env_without_password_refuses(key_files, tmp_path):
    store, _ = key_files
    with pytest.raises(BuildError, match="no key store password"):
        build_android.signing_env({}, store, tmp_path / "missing.pass")


def test_flet_command_for_bundle():
    assert build_android.flet_command("aab", "1.1.0") == [
        "flet",
        "build",
        "aab",
        "--build-version",
        "1.1.0",
        "--build-number",
        "101000000",
    ]


def test_flet_command_for_apks_splits_per_abi():
    command = build_android.flet_command("apk", "1.1.0")
    assert command[:3] == ["flet", "build", "apk"]
    assert command[-1] == "--split-per-abi"


@pytest.mark.parametrize(
    ("built", "dist"),
    [
        ("timtapper.aab", "timtapper-1.1.0.aab"),
        ("timtapper-arm64-v8a.apk", "timtapper-1.1.0-arm64-v8a.apk"),
        ("timtapper-x86_64.apk", "timtapper-1.1.0-x86_64.apk"),
    ],
)
def test_versioned_name(built, dist):
    assert build_android.versioned_name(Path("build") / built, "1.1.0") == dist


def _make_key(store: Path, alias: str, name: str) -> None:
    subprocess.run(
        [
            "keytool",
            "-genkeypair",
            "-keystore",
            str(store),
            "-storetype",
            "PKCS12",
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "1",
            "-storepass",
            PASSWORD,
            "-dname",
            f"CN={name}",
        ],
        check=True,
        capture_output=True,
    )


def _signed_archive(tmp_path: Path, store: Path, alias: str) -> Path:
    archive = tmp_path / f"signed-by-{alias}.aab"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("base/manifest/AndroidManifest.xml", b"manifest")
    subprocess.run(
        ["jarsigner", "-keystore", str(store), "-storepass", PASSWORD, str(archive), alias],
        check=True,
        capture_output=True,
    )
    return archive


@pytest.fixture
def upload_key(tmp_path):
    store = tmp_path / "upload.jks"
    _make_key(store, "upload", "Upload")
    return {
        build_android.STORE_ENV: str(store),
        build_android.ALIAS_ENV: "upload",
        build_android.STORE_PASSWORD_ENV: PASSWORD,
    }


@needs_jdk
def test_check_signed_accepts_the_upload_key(tmp_path, upload_key):
    archive = _signed_archive(tmp_path, Path(upload_key[build_android.STORE_ENV]), "upload")
    build_android.check_signed(archive, upload_key)


@needs_jdk
def test_check_signed_rejects_another_key(tmp_path, upload_key):
    other = tmp_path / "debug.jks"
    _make_key(other, "androiddebugkey", "Android Debug")
    archive = _signed_archive(tmp_path, other, "androiddebugkey")
    with pytest.raises(BuildError, match="not signed with the upload key"):
        build_android.check_signed(archive, upload_key)


@needs_jdk
def test_check_signed_rejects_an_unsigned_archive(tmp_path, upload_key):
    archive = tmp_path / "unsigned.aab"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("base/manifest/AndroidManifest.xml", b"manifest")
    with pytest.raises(BuildError, match="found no certificate"):
        build_android.check_signed(archive, upload_key)


def _apk(tmp_path: Path, name: str) -> Path:
    apk = tmp_path / name
    with zipfile.ZipFile(apk, "w") as z:
        z.writestr("AndroidManifest.xml", b"manifest")
    return apk


def _signed_apk(tmp_path: Path, store: Path, alias: str) -> Path:
    """An APK signed the way flet's release APKs are: APK Signature Scheme v2/v3 only, no JAR signature."""
    apk = _apk(tmp_path, f"signed-by-{alias}.apk")
    subprocess.run(
        [
            str(_apksigner()),
            "sign",
            "--ks",
            str(store),
            "--ks-key-alias",
            alias,
            "--ks-pass",
            f"pass:{PASSWORD}",
            "--min-sdk-version",
            "24",
            "--v1-signing-enabled",
            "false",
            str(apk),
        ],
        check=True,
        capture_output=True,
    )
    return apk


@needs_apksigner
@pytest.mark.regression
def test_check_signed_accepts_an_apk_signed_without_a_jar_signature(tmp_path, upload_key):
    # keytool -printcert -jarfile reads only JAR (v1) signatures, so every v2-only release APK was
    # rejected with "Not a signed jar file" even though it carried the upload key
    apk = _signed_apk(tmp_path, Path(upload_key[build_android.STORE_ENV]), "upload")
    build_android.check_signed(apk, upload_key)


@needs_apksigner
def test_check_signed_rejects_an_apk_signed_with_another_key(tmp_path, upload_key):
    other = tmp_path / "debug.jks"
    _make_key(other, "androiddebugkey", "Android Debug")
    apk = _signed_apk(tmp_path, other, "androiddebugkey")
    with pytest.raises(BuildError, match="not signed with the upload key"):
        build_android.check_signed(apk, upload_key)


@needs_apksigner
def test_check_signed_rejects_an_unsigned_apk(tmp_path, upload_key):
    with pytest.raises(BuildError, match="apksigner.* failed"):
        build_android.check_signed(_apk(tmp_path, "unsigned.apk"), upload_key)


def _build_tools(home: Path, *versions: str) -> None:
    name = "apksigner.bat" if build_android.os.name == "nt" else "apksigner"
    for version in versions:
        (home / "build-tools" / version).mkdir(parents=True)
        (home / "build-tools" / version / name).write_text("")


def test_find_apksigner_picks_the_newest_build_tools_by_number(tmp_path):
    _build_tools(tmp_path, "9.0.0", "35.0.0", "34.0.0")
    found = build_android.find_apksigner({"ANDROID_HOME": str(tmp_path), "LOCALAPPDATA": str(tmp_path / "none")})
    assert found.parent.name == "35.0.0"


def test_find_apksigner_falls_back_to_android_sdk_root(tmp_path):
    _build_tools(tmp_path / "sdk", "34.0.0")
    found = build_android.find_apksigner({"ANDROID_SDK_ROOT": str(tmp_path / "sdk"), "LOCALAPPDATA": str(tmp_path)})
    assert found.parent.name == "34.0.0"


def test_find_apksigner_without_an_sdk_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(build_android.Path, "home", lambda: tmp_path)
    with pytest.raises(BuildError, match="no apksigner"):
        build_android.find_apksigner({"LOCALAPPDATA": str(tmp_path)})


def test_main_reports_a_failed_build_and_exits_1(monkeypatch):
    def fail(target):
        raise BuildError("no upload key store at x")

    errors = []
    monkeypatch.setattr(build_android, "build", fail)
    monkeypatch.setattr(build_android._log, "error", lambda msg, *args: errors.append(msg % args))
    monkeypatch.setattr("sys.argv", ["build_android.py"])
    assert build_android.main() == 1
    assert errors == ["build failed: no upload key store at x"]
