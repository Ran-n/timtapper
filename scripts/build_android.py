#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 11:01:44.904139
Revised: 2026/10/13 22:03:51.747750

Build a release-signed Android bundle (for Google Play), per-ABI APKs or one universal APK (for sideloading)
and copy them into dist/ with the version in the name:

    uv run python scripts/build_android.py              # dist/timtapper-<version>.aab
    uv run python scripts/build_android.py apk          # dist/timtapper-<version>-<abi>.apk
    uv run python scripts/build_android.py universal    # dist/timtapper-<version>-universal.apk (every ABI)

Signs with the upload key. flet build reads it from the FLET_ANDROID_SIGNING_* variables; any that are unset
are filled in from ../secrets/timtapper-upload.jks (alias "upload") and the password in
../secrets/timtapper-upload.pass, both kept outside the repository. Without a key the build stops instead of
falling back to flet's debug key, which Google Play rejects. After building, each artifact's certificate is
checked against the key store's: with keytool for the bundle (JAR-signed) and with the Android SDK's apksigner
for APKs (APK Signature Scheme v2/v3 only, which keytool can't read).
"""

import argparse
import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "timtapper"))

from core.logging import get_logger, setup_logging  # noqa: E402

DIST = ROOT / "dist"
SECRETS = ROOT.parent / "secrets"
KEY_STORE = SECRETS / "timtapper-upload.jks"
PASSWORD_FILE = SECRETS / "timtapper-upload.pass"
KEY_ALIAS = "upload"

STORE_ENV = "FLET_ANDROID_SIGNING_KEY_STORE"
STORE_PASSWORD_ENV = "FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD"
KEY_PASSWORD_ENV = "FLET_ANDROID_SIGNING_KEY_PASSWORD"
ALIAS_ENV = "FLET_ANDROID_SIGNING_KEY_ALIAS"

# Flutter's --split-per-abi adds abi * 1000 (1, 2 or 4) to each APK's version code, so the version part
# leaves the last four digits free: every APK of a release then sorts above every APK of the one before.
_ABI_ROOM = 10_000
_MAX_VERSION_CODE = 2_100_000_000  # Google Play's ceiling

# script target -> (flet build target, extra flags). A universal APK is flet's plain apk build, holding every
# ABI; --split-per-abi is never left off the per-ABI build, or stale per-ABI APKs from an earlier build stay behind.
TARGETS = {"aab": ("aab", []), "apk": ("apk", ["--split-per-abi"]), "universal": ("apk", [])}

_log = get_logger("scripts.build_android")


class BuildError(Exception):
    """The release can't be built or the result isn't signed with the upload key."""


def project_version(pyproject: Path = ROOT / "pyproject.toml") -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def version_code(version: str) -> int:
    """1.1.0 -> 101000000: major, minor and patch two digits each, then room for the ABI offset."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise BuildError(f"version {version!r} is not MAJOR.MINOR.PATCH")
    major, minor, patch = map(int, match.groups())
    if minor > 99 or patch > 99:
        raise BuildError(f"version {version}: minor and patch must stay below 100 to fit the version code")
    code = (major * 10_000 + minor * 100 + patch) * _ABI_ROOM
    if code + 4 * 1000 > _MAX_VERSION_CODE:
        raise BuildError(f"version {version}: version code {code} is above Google Play's limit")
    return code


def signing_env(
    environ: Mapping[str, str], key_store: Path = KEY_STORE, password_file: Path = PASSWORD_FILE
) -> dict[str, str]:
    """The environment for flet build, with every signing variable set; values already in `environ` win."""
    env = dict(environ)
    env.setdefault(STORE_ENV, str(key_store))
    env.setdefault(ALIAS_ENV, KEY_ALIAS)
    if not Path(env[STORE_ENV]).is_file():
        raise BuildError(f"no upload key store at {env[STORE_ENV]} (set {STORE_ENV} to its path)")
    if STORE_PASSWORD_ENV not in env:
        try:
            env[STORE_PASSWORD_ENV] = password_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise BuildError(f"no key store password: set {STORE_PASSWORD_ENV} or create {password_file}") from exc
    env.setdefault(KEY_PASSWORD_ENV, env[STORE_PASSWORD_ENV])  # PKCS12 stores share one password
    return env


def flet_command(target: str, version: str) -> list[str]:
    flet_target, flags = TARGETS[target]
    build_number = str(version_code(version))
    return ["flet", "build", flet_target, "--build-version", version, "--build-number", build_number, *flags]


def versioned_name(artifact: Path, version: str) -> str:
    """timtapper-arm64-v8a.apk -> timtapper-1.1.0-arm64-v8a.apk; timtapper.aab -> timtapper-1.1.0.aab;
    timtapper.apk (no ABI, so every ABI) -> timtapper-1.1.0-universal.apk."""
    name, sep, rest = artifact.stem.partition("-")
    if not sep and artifact.suffix == ".apk":
        sep, rest = "-", "universal"
    return f"{name}-{version}{sep}{rest}{artifact.suffix}"


def _run(command: list[str], env: Mapping[str, str] | None = None) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    if result.returncode:
        raise BuildError(f"{' '.join(command[:2])} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _pem_digest(command: list[str], env: Mapping[str, str] | None = None) -> str:
    """SHA-256 of the one certificate `command` prints as PEM, as lowercase hex."""
    pem = re.search(r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", _run(command, env), re.DOTALL)
    if not pem:
        raise BuildError(f"{' '.join(command[:2])} found no certificate")
    return hashlib.sha256(base64.b64decode("".join(pem.group(1).split()))).hexdigest()


def find_apksigner(environ: Mapping[str, str] = os.environ) -> Path:
    """apksigner from the newest build-tools of the Android SDK flet builds with."""
    homes = [environ.get("ANDROID_HOME"), environ.get("ANDROID_SDK_ROOT")]
    homes += [Path.home() / "Android" / "sdk", Path(environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"]
    name = "apksigner.bat" if os.name == "nt" else "apksigner"
    for home in filter(None, homes):
        found = sorted(
            Path(home).glob(f"build-tools/*/{name}"), key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)]
        )
        if found:
            return found[-1]
    raise BuildError("no apksigner in any Android SDK build-tools (set ANDROID_HOME)")


def _apk_digest(apk: Path) -> str:
    # the minimum SDK only picks which signature schemes verify must find; this check is about who signed
    out = _run([str(find_apksigner()), "verify", "--print-certs", "--min-sdk-version", "24", str(apk)])
    digests = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$", out, re.MULTILINE)
    if len(digests) != 1:
        raise BuildError(f"apksigner verify found {len(digests)} signers in {apk.name}, expected 1")
    return digests[0]


def check_signed(artifact: Path, env: Mapping[str, str]) -> None:
    """Raise unless `artifact` carries the upload key's certificate (and not flet's debug one)."""
    expected = _pem_digest(
        [
            "keytool",
            "-exportcert",
            "-rfc",
            "-keystore",
            env[STORE_ENV],
            "-alias",
            env[ALIAS_ENV],
            "-storepass:env",
            STORE_PASSWORD_ENV,
        ],
        env={**os.environ, **env},
    )
    if artifact.suffix == ".apk":
        actual = _apk_digest(artifact)
    else:
        actual = _pem_digest(["keytool", "-printcert", "-rfc", "-jarfile", str(artifact)])
    if actual != expected:
        raise BuildError(f"{artifact.name} is not signed with the upload key")


def build(target: str) -> list[Path]:
    version = project_version()
    # flet's progress output has emoji; on Windows, redirected to a file or pipe, cp1252 can't encode them
    env = signing_env(os.environ) | {"PYTHONUTF8": "1"}
    flet_target, _ = TARGETS[target]
    out_dir = ROOT / "build" / flet_target
    shutil.rmtree(out_dir, ignore_errors=True)
    _log.info("building %s %s (version code %d)", target, version, version_code(version))
    subprocess.run(["uv", "run", *flet_command(target, version)], cwd=ROOT, env=env, check=True)
    artifacts = sorted(out_dir.glob(f"*.{flet_target}"))
    if not artifacts:
        raise BuildError(f"flet build left no .{flet_target} in {out_dir}")
    DIST.mkdir(exist_ok=True)
    copies = []
    for artifact in artifacts:
        check_signed(artifact, env)
        copy = DIST / versioned_name(artifact, version)
        shutil.copy2(artifact, copy)
        _log.info("wrote %s", copy.relative_to(ROOT))
        copies.append(copy)
    return copies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("target", nargs="?", choices=tuple(TARGETS), default="aab")
    args = parser.parse_args()
    setup_logging()
    try:
        build(args.target)
    except (BuildError, subprocess.CalledProcessError) as exc:
        _log.error("build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
