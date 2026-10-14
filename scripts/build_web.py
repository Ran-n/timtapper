#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.026136
Revised: 2026/10/14 13:16:03.771926

Build the web version (the app's Python on Pyodide, in the browser) into build/web and dist/, and optionally
publish it to GitHub Pages and Codeberg Pages:

    uv run python scripts/build_web.py              # build/web + dist/timtapper-<version>-web.zip
    uv run python scripts/build_web.py --publish    # ...then force-push the site to the `pages` branch

Three fixes on top of `flet build web`:
- flet leaves assets/ out of the Python archive (the browser gets those files over HTTP), but the app reads
  leaders.json, fonts and portraits from disk, so they're added back into assets/app/app.zip;
- the test-suite packages of SQLAlchemy and Alembic, which nothing in the app imports, are taken out of it, so every
  visitor downloads and unpacks less before the app starts;
- index.html asks for the archive with ?v=<version>, so a browser holding an older copy fetches the new one.

The base path (/timtapper/) and hash routes come from [tool.flet.web] in pyproject.toml. That is where Codeberg Pages
serves it (ran-n.codeberg.page/timtapper/); GitHub Pages serves it at the root of its own domain
(timtapper.breren.com), so its copy is rebased to / and carries a CNAME file naming the domain.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # build_android, when imported from the tests

from build_android import DIST, ROOT, BuildError, project_version  # noqa: E402  (it puts the app on sys.path)

from core.logging import get_logger, setup_logging  # noqa: E402

SITE = ROOT / "build" / "web"
ASSETS = ROOT / "src" / "timtapper" / "assets"
APP_ARCHIVE = Path("assets") / "app" / "app.zip"
ARCHIVE_URL = 'appPackageUrl: "assets/app/app.zip"'
PAGES_BRANCH = "pages"
# packages in the archive that only the libraries' own test suites import
UNUSED = ("__pypackages__/sqlalchemy/testing/", "__pypackages__/alembic/testing/")
_FLET_WEB = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["flet"]["web"]
BUILT_BASE = f"/{_FLET_WEB['base_url']}/"
BASE_MARKERS = ('<base href="{}">', 'entrypointBaseUrl: "{}"', 'assetBase: "{}"')  # where flet writes it in index.html


@dataclass(frozen=True)
class PagesHost:
    """How one static host serves the site: under `base`, and on its own `domain` (written to CNAME) if it has one."""

    base: str = BUILT_BASE
    domain: str | None = None


PAGES_HOSTS = {"github": PagesHost("/", "timtapper.breren.com"), "codeberg": PagesHost()}

_log = get_logger("scripts.build_web")


def add_assets(archive: Path, assets: Path = ASSETS) -> int:
    """Put every file under `assets` into the Python archive at assets/<path>, as native builds ship it.
    Returns how many were added; files already there are left alone."""
    with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as z:
        present = set(z.namelist())
        added = 0
        for path in sorted(p for p in assets.rglob("*") if p.is_file()):
            name = f"assets/{path.relative_to(assets).as_posix()}"
            if name not in present:
                z.write(path, name)
                added += 1
    return added


def drop_unused(archive: Path, prefixes: tuple[str, ...] = UNUSED) -> int:
    """Rewrite the Python archive without the files under `prefixes`. Returns how many were dropped."""
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        kept = [e for e in entries if not e.filename.startswith(prefixes)]
        if len(kept) == len(entries):
            return 0
        slim = archive.with_name(archive.name + ".slim")
        with zipfile.ZipFile(slim, "w", zipfile.ZIP_DEFLATED) as out:
            for entry in kept:
                out.writestr(entry, z.read(entry), compress_type=entry.compress_type)
    slim.replace(archive)
    return len(entries) - len(kept)


def version_archive_url(index: Path, version: str) -> None:
    """Make index.html fetch the Python archive as app.zip?v=<version>."""
    html = index.read_text(encoding="utf-8")
    if ARCHIVE_URL not in html:
        raise BuildError(f"{index.name} no longer holds {ARCHIVE_URL}: flet's web template changed")
    index.write_text(html.replace(ARCHIVE_URL, f'appPackageUrl: "assets/app/app.zip?v={version}"'), encoding="utf-8")


def finish_site(site: Path, version: str, assets: Path = ASSETS) -> None:
    dropped = drop_unused(site / APP_ARCHIVE)
    _log.info("dropped %d unused library files from the Python archive", dropped)
    added = add_assets(site / APP_ARCHIVE, assets)
    _log.info("added %d asset files to the Python archive", added)
    version_archive_url(site / "index.html", version)
    (site / ".nojekyll").touch()  # GitHub Pages: serve the files as they are


def rebase_site(site: Path, base: str, built: str = BUILT_BASE) -> None:
    """Make index.html load the app from `base` instead of the `built` path flet wrote into it."""
    if base == built:
        return
    index = site / "index.html"
    html = index.read_text(encoding="utf-8")
    for marker in BASE_MARKERS:
        old = marker.format(built)
        if old not in html:
            raise BuildError(f"{index.name} no longer holds {old}: flet's web template changed")
        html = html.replace(old, marker.format(base))
    index.write_text(html, encoding="utf-8")


def prepare_for(site: Path, host: PagesHost) -> None:
    rebase_site(site, host.base)
    if host.domain:
        (site / "CNAME").write_text(f"{host.domain}\n", encoding="utf-8")


def zip_site(site: Path, out: Path) -> Path:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in site.rglob("*") if p.is_file()):
            z.write(path, path.relative_to(site).as_posix())
    return out


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        raise BuildError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def publish(site: Path, version: str, hosts: dict[str, PagesHost] = PAGES_HOSTS, repo: Path = ROOT) -> None:
    """Force-push `site`, prepared for each remote's host, as the single commit of its `pages` branch: a build
    output, so no history."""
    for remote, host in hosts.items():
        url = _git(repo, "remote", "get-url", remote)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "site"
            shutil.copytree(site, work)
            prepare_for(work, host)
            _git(work, "init", "-q", "-b", PAGES_BRANCH)
            _git(work, "add", "-A")
            _git(work, "commit", "-q", "-m", f"[B] web {version}")
            _git(work, "push", "-q", "-f", url, f"HEAD:{PAGES_BRANCH}")
        _log.info("published web %s to %s/%s (%s%s)", version, remote, PAGES_BRANCH, host.domain or "", host.base)


def build() -> Path:
    version = project_version()
    shutil.rmtree(SITE, ignore_errors=True)
    _log.info("building web %s", version)
    # flet's progress output has emoji; on Windows, redirected to a file or pipe, cp1252 can't encode them
    env = os.environ | {"PYTHONUTF8": "1"}
    subprocess.run(["uv", "run", "flet", "build", "web"], cwd=ROOT, env=env, check=True)
    if not (SITE / APP_ARCHIVE).is_file():
        raise BuildError(f"flet build left no {APP_ARCHIVE.as_posix()} in {SITE}")
    finish_site(SITE, version)
    DIST.mkdir(exist_ok=True)
    out = zip_site(SITE, DIST / f"timtapper-{version}-web.zip")
    _log.info("wrote %s", out.relative_to(ROOT))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--publish", action="store_true", help=f"push the site to {', '.join(PAGES_HOSTS)}")
    args = parser.parse_args()
    setup_logging()
    try:
        build()
        if args.publish:
            publish(SITE, project_version())
    except (BuildError, subprocess.CalledProcessError) as exc:
        _log.error("build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
