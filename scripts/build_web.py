#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.026136
Revised: 2026/10/15 01:26:05.893286

Build the web version (the app's Python on Pyodide, in the browser) into build/web and dist/, and optionally
publish it to GitHub Pages, GitLab Pages and Codeberg Pages:

    uv run python scripts/build_web.py              # build/web + dist/timtapper-<version>-web.zip
    uv run python scripts/build_web.py --publish    # ...then force-push the site to the `pages` branch

Five changes on top of `flet build web`:
- flet leaves assets/ out of the Python archive (the browser gets those files over HTTP), but the app reads
  leaders.json, fonts and portraits from disk, so they're added back into assets/app/app.zip;
- files nothing in the browser uses (SQLAlchemy's and Alembic's test suites, the Windows launchers in bin/) are
  taken out of it, so every visitor downloads and unpacks less before the app starts;
- index.html asks for the archive with ?v=<version>, so a browser holding an older copy fetches the new one;
- Python starts with the page: flet starts it only once Flutter has, and then loads Pyodide and downloads the archive
  one after the other; now the page starts the worker first thing, which loads both at once while Flutter starts;
- index.html paints the app's screens the moment it opens (scripts/shell/): what the app saved on the last visit, or
  on a first one the empty app, built here; Python takes over when it has started.

The base path (/timtapper/) and hash routes come from [tool.flet.web] in pyproject.toml. That is where Codeberg Pages
and GitLab Pages serve it (ran-n.codeberg.page/timtapper/, ran-n.gitlab.io/timtapper/; GitLab through the CI job its
branch carries); GitHub Pages serves it at the root of its own domain (timtapper.breren.com), so its copy is rebased
to / and carries a CNAME file naming the domain.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import blake3

sys.path.insert(0, str(Path(__file__).resolve().parent))  # build_android, when imported from the tests

from build_android import DIST, ROOT, BuildError, project_version  # noqa: E402  (it puts the app on sys.path)

from catalog.portraits import BUNDLED_LIST  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402
from core.web import PILLOW  # noqa: E402

SITE = ROOT / "build" / "web"
ASSETS = ROOT / "src" / "timtapper" / "assets"
APP_ARCHIVE = Path("assets") / "app" / "app.zip"
ARCHIVE_URL = 'appPackageUrl: "assets/app/app.zip"'
PAGES_BRANCH = "pages"
# files in the archive nothing in the browser uses: what only the libraries' own test suites import, and the
# console launchers (alembic.exe, flet.exe...) the packages install. SQLAlchemy's other dialects can't go: the app
# uses only sqlite, but importing alembic imports every dialect's DDL module
UNUSED = ("__pypackages__/sqlalchemy/testing/", "__pypackages__/alembic/testing/", "__pypackages__/bin/")
# what the web app fetches only when it draws a picture (core.web.RenderDeps): Pillow, from Pyodide's CDN, and the
# bundled portraits, from the site's leaders/ (flet copies assets/ there), whose names go in instead
LATER = ("__pypackages__/PIL/", f"__pypackages__/{PILLOW}-")
PORTRAITS = Path("leaders")
# flet's python.js starts the Python worker only when Dart connects, once Flutter has started; these make it start
# with the page, and the worker load Pyodide (or restore it from a snapshot) and unpack the app meanwhile
# (scripts/prestart/, see prestart_python)
PRESTART_DIR = ROOT / "scripts" / "prestart"
SNAPSHOT_KEY = "__SNAPSHOT_KEY__"
FLET_LOAD_BODY = "//FLET_LOAD_BODY\n"
FLET_OPTIONS = "FLET_OPTIONS"
PYTHON_JS_AFTER = "let _documentUrl = document.URL;\n"
PYTHON_JS_WORKER = 'app.worker = new Worker("python-worker.js", { type: "module" });'
PYTHON_JS_TAKE_OVER = (
    'app.worker = _prestarted || new Worker("python-worker.js", { type: "module" });\n    _prestarted = null;'
)
WORKER_LOAD = re.compile(
    r"const pyodideModule = await import\(self\.pyodideUrl\);\n(?P<body>.*?)[ \t]*self\.pyodide = await "
    r"(?P<call>loadPyodide\(\{.*?\}\);)",
    re.DOTALL,
)
WORKER_INIT_AT = "self.initPyodide = async function () {"
# the boot waits for the prestart before it touches Python: a JS object Python holds (flet_js, registered next) would
# keep the prestart from taking Python's snapshot
WORKER_START = (
    "self.pyodide = await self.startPyodide();\n"
    "        if (self.appUnpacked) flet_js.appUnpackedFrom = await self.appUnpacked;"
)
WORKER_DOWNLOAD = '        if "script" not in py_args:\n'
WORKER_SKIP_DOWNLOAD = """\
        if "script" not in py_args and getattr(flet_js, "appUnpackedFrom", None) == app_package_url:
            print("App archive unpacked ahead")
        elif "script" not in py_args:
"""
WORKER_ONMESSAGE = "self.onmessage = async (event) => {\n"
WORKER_ON_PRESTART = """\
    if (event.data && event.data.prestart) {
        self.pyodideUrl = event.data.pyodideUrl;
        self.appPackageUrl = event.data.appPackageUrl;
        self.pythonModuleName = event.data.pythonModuleName;
        self.snapshotKey = event.data.snapshotKey;
        self.prestart();
        return;
    }
"""
SHELL_DIR = ROOT / "scripts" / "shell"
SW_DIR = ROOT / "scripts" / "sw"
SW_FILE = "sw.js"
SW_BLOCK = re.compile(r"\n<!-- timtapper sw -->.*?<!-- /timtapper sw -->\n", re.DOTALL)
# what the service worker doesn't keep: what no page asks for (source maps, flet's build id, the licences page's
# NOTICES, which it keeps once asked for), the hosts' files, and the worker itself
SW_SKIP = re.compile(r"(^|/)\.|\.map$|\.hash$|^(NOTICES|assets/NOTICES|version\.json|CNAME|sw\.js)$")
# Flutter's own service worker: deprecated, empty, on the same scope as the site's, and its loader waits up to 4 s
# for it to activate before starting Flutter
FLUTTER_SW = "flutter_service_worker.js"
FLUTTER_SW_SETTINGS = re.compile(r"\n[ \t]*serviceWorkerSettings: \{.*?\n[ \t]*\},", re.DOTALL)
SHELL_AFTER = "<body>"
APP_SOURCE = ROOT / "src" / "timtapper"
ICON_USE = re.compile(r"\bft\.Icons\.([A-Z0-9_]+)\b")
ICON_DEF = re.compile(r"static const IconData (\w+) = IconData\(\s*0x([0-9a-fA-F]+)")
# what the shell draws itself: a pushed screen's back arrow, a dropdown's arrow, a selected segment's check
SHELL_ICONS = ("arrow_back", "arrow_drop_down", "check")
SHELL_BLOCK = re.compile(r"\n<!-- timtapper shell -->.*?<!-- /timtapper shell -->\n", re.DOTALL)
_FLET_WEB = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["flet"]["web"]
BUILT_BASE = f"/{_FLET_WEB['base_url']}/"
BASE_MARKERS = ('<base href="{}">', 'entrypointBaseUrl: "{}"', 'assetBase: "{}"')  # where flet writes it in index.html


# GitLab Pages serves only what a CI job named `pages` publishes, so GitLab's `pages` branch carries this job too
GITLAB_CI = """\
# the built site (scripts/build_web.py --publish), published by GitLab Pages as it is
pages:
  pages: true
  image: busybox
  script:
    - mkdir .public
    - cp -r $(ls -A | grep -vx -e .public -e .git -e .gitlab-ci.yml) .public/
    - mv .public public
  artifacts:
    paths: [public]
  rules:
    - if: $CI_COMMIT_BRANCH == "pages"
"""


@dataclass(frozen=True)
class PagesHost:
    """How one static host serves the site: under `base`, on its own `domain` (written to CNAME) if it has one, and
    through a GitLab CI `pages` job if `ci_job`."""

    base: str = BUILT_BASE
    domain: str | None = None
    ci_job: bool = False


PAGES_HOSTS = {
    "github": PagesHost("/", "timtapper.breren.com"),
    "gitlab": PagesHost(ci_job=True),
    "codeberg": PagesHost(),
}

_log = get_logger("scripts.build_web")


def add_assets(archive: Path, assets: Path = ASSETS) -> int:
    """Put every file under `assets` into the Python archive at assets/<path>, as native builds ship it, but the
    portraits: their names, in assets/leaders/bundled.txt. Returns how many were added; files already there are left
    alone."""
    portraits = assets / PORTRAITS
    with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as z:
        present = set(z.namelist())
        added = 0
        for path in sorted(p for p in assets.rglob("*") if p.is_file() and p.parent != portraits):
            name = f"assets/{path.relative_to(assets).as_posix()}"
            if name not in present:
                z.write(path, name)
                added += 1
        listed = f"assets/{(PORTRAITS / BUNDLED_LIST).as_posix()}"
        if listed not in present:
            z.writestr(listed, "".join(f"{p.name}\n" for p in sorted(portraits.glob("*.webp"))))
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


def _replace_once(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{name} no longer holds {old.strip()!r} once: flet's web template changed")
    return text.replace(old, new)


def snapshot_key(archive: Path) -> str:
    """What names the Python archive's snapshot: a digest of the archive, so another build's is never restored."""
    return blake3.blake3(archive.read_bytes()).hexdigest()[:16]


def prestart_python(site: Path, prestart_dir: Path = PRESTART_DIR) -> None:
    """Start Python with the page instead of once Flutter has started. flet's python.js creates the worker only when
    Dart connects, and the worker then loads Pyodide and downloads and unpacks the archive one after the other; now
    the page starts the worker first thing, which loads Pyodide (from a snapshot, after the first visit) and fetches
    the archive at once and unpacks it, while Flutter downloads and starts. When Dart connects it takes that worker
    over, and the boot script skips the download when the archive it would fetch is the one already unpacked."""
    python_js = site / "python.js"
    page = (prestart_dir / "page.js").read_text(encoding="utf-8")
    page = _replace_once(page, SNAPSHOT_KEY, snapshot_key(site / APP_ARCHIVE), "page.js")
    js = _replace_once(python_js.read_text(encoding="utf-8"), PYTHON_JS_AFTER, PYTHON_JS_AFTER + page, python_js.name)
    python_js.write_text(_replace_once(js, PYTHON_JS_WORKER, PYTHON_JS_TAKE_OVER, python_js.name), encoding="utf-8")

    worker = site / "python-worker.js"
    js = worker.read_text(encoding="utf-8")
    load = WORKER_LOAD.search(js)
    if load is None:
        raise BuildError(f"{worker.name} no longer loads Pyodide as expected: flet's web template changed")
    js = js[: load.start()] + WORKER_START + js[load.end() :]
    # flet's own options for loadPyodide, which the snapshot's are added to
    options = load["call"].removeprefix("loadPyodide(").removesuffix(");")
    prestart = (prestart_dir / "worker.js").read_text(encoding="utf-8")
    prestart = _replace_once(prestart, FLET_LOAD_BODY, load["body"], "worker.js")
    prestart = _replace_once(prestart, FLET_OPTIONS, options, "worker.js")
    js = _replace_once(js, WORKER_INIT_AT, prestart + WORKER_INIT_AT, worker.name)
    js = _replace_once(js, WORKER_DOWNLOAD, WORKER_SKIP_DOWNLOAD, worker.name)
    worker.write_text(
        _replace_once(js, WORKER_ONMESSAGE, WORKER_ONMESSAGE + WORKER_ON_PRESTART, worker.name), encoding="utf-8"
    )


def icon_names(source: Path = APP_SOURCE) -> set[str]:
    """Every Material icon the app's code names (ft.Icons.ADD -> "add"), and the shell's own."""
    names = set(SHELL_ICONS)
    for path in source.rglob("*.py"):
        names.update(m.lower() for m in ICON_USE.findall(path.read_text(encoding="utf-8")))
    return names


def flutter_icons() -> Path:
    """Flutter's icon table, in the SDK flet builds with."""
    import flet.version
    from flet_cli.utils.flutter import get_flutter_dir

    path = Path(get_flutter_dir(flet.version.flutter_version)) / "packages/flutter/lib/src/material/icons.dart"
    if not path.is_file():
        raise BuildError(f"no {path}: build once with `flet build web` so flet installs its Flutter SDK")
    return path


def icon_codepoints(names: set[str], icons_dart: Path) -> dict[str, int]:
    """Each icon's codepoint in Flutter's MaterialIcons font, which the site already serves."""
    table = {name: int(code, 16) for name, code in ICON_DEF.findall(icons_dart.read_text(encoding="utf-8"))}
    missing = sorted(names - table.keys())
    if missing:
        raise BuildError(f"{icons_dart.name} has no {', '.join(missing)}")
    return {name: table[name] for name in sorted(names)}


def first_visit_shells() -> dict[str, dict]:
    """The shell a first visit paints, in the light and dark palette: the screens of an empty app, built from an
    empty database in a scratch data folder (building screens looks for downloaded portraits there)."""
    from i18n import DEFAULT_LANG
    from main import open_database
    from ui.shell import default_documents
    from ui.theme import get_theme

    with tempfile.TemporaryDirectory() as tmp:
        saved = os.environ.get("FLET_APP_STORAGE_DATA")
        os.environ["FLET_APP_STORAGE_DATA"] = tmp
        try:
            db = open_database(path=Path(tmp) / "shell.db")
            try:
                docs = default_documents(db, get_theme(None), DEFAULT_LANG)
            finally:
                db.dispose()
        finally:
            if saved is None:
                os.environ.pop("FLET_APP_STORAGE_DATA", None)
            else:
                os.environ["FLET_APP_STORAGE_DATA"] = saved
    return {name: json.loads(text) for name, text in docs.items()}


def shell_config() -> dict:
    """What shell.js reads from window.TIMTAPPER_SHELL: where the app keeps the shell, how it says it's ready, the
    icons' codepoints and the first-visit shells."""
    from core import web
    from ui import shell

    return {
        "version": shell.VERSION,
        "db": web.SHELL_DB,
        "store": web.SHELL_STORE,
        "key": web.SHELL_KEY,
        "channel": web.SHELL_CHANNEL,
        "ready": web.SHELL_READY,
        "icons": icon_codepoints(icon_names(), flutter_icons()),
        "defaults": first_visit_shells(),
    }


def add_shell(index: Path, config: dict, shell_dir: Path = SHELL_DIR) -> None:
    """Paint the shell from index.html itself, first thing in <body>: no request stands between opening the page and
    seeing the app. A shell already there is replaced."""
    html = SHELL_BLOCK.sub("", index.read_text(encoding="utf-8"))
    if SHELL_AFTER not in html:
        raise BuildError(f"{index.name} has no {SHELL_AFTER}: flet's web template changed")
    data = json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css = (shell_dir / "shell.css").read_text(encoding="utf-8")
    js = (shell_dir / "shell.js").read_text(encoding="utf-8")
    block = (
        f"\n<!-- timtapper shell -->\n<style>{css}</style>\n<script>window.TIMTAPPER_SHELL = {data};</script>\n"
        f"<script>{js}</script>\n<!-- /timtapper shell -->\n"
    )
    index.write_text(html.replace(SHELL_AFTER, SHELL_AFTER + block, 1), encoding="utf-8")


def drop_flutter_service_worker(site: Path) -> None:
    """Keep Flutter's loader from registering its service worker (FLUTTER_SW), and take the file out."""
    bootstrap = site / "flutter_bootstrap.js"
    js, found = FLUTTER_SW_SETTINGS.subn("", bootstrap.read_text(encoding="utf-8"))
    if found != 1:
        raise BuildError(f"{bootstrap.name} has no serviceWorkerSettings: flet's web template changed")
    bootstrap.write_text(js, encoding="utf-8")
    (site / FLUTTER_SW).unlink(missing_ok=True)


def kept_files(site: Path, version: str) -> list[str]:
    """What the service worker keeps, as the page asks for it: the page as ./, the Python archive with its ?v=."""
    files = []
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        name = path.relative_to(site).as_posix()
        if SW_SKIP.search(name):
            continue
        files.append(
            "./" if name == "index.html" else f"{name}?v={version}" if name == APP_ARCHIVE.as_posix() else name
        )
    return files


def build_id(site: Path) -> str:
    """A digest of every file of the site: a new build's service worker is a new file, which browsers install."""
    digest = blake3.blake3()
    for path in sorted(p for p in site.rglob("*") if p.is_file() and p.name != SW_FILE):
        digest.update(path.relative_to(site).as_posix().encode() + b"\0")
        digest.update(blake3.blake3(path.read_bytes()).digest())
    return digest.hexdigest()[:16]


def add_service_worker(site: Path, version: str, config: dict, sw_dir: Path = SW_DIR) -> list[str]:
    """Write the site's service worker (scripts/sw/sw.js), keeping the site's files, and have index.html register it
    once the app says it's ready (scripts/sw/register.js), on `config`'s channel. Returns the files it keeps."""
    index = site / "index.html"
    html = SW_BLOCK.sub("", index.read_text(encoding="utf-8"))
    if SHELL_AFTER not in html:
        raise BuildError(f"{index.name} has no {SHELL_AFTER}: flet's web template changed")
    data = json.dumps({"url": SW_FILE, "channel": config["channel"], "ready": config["ready"]}, separators=(",", ":"))
    js = (sw_dir / "register.js").read_text(encoding="utf-8")
    block = (
        f"\n<!-- timtapper sw -->\n<script>window.TIMTAPPER_SW = {data};</script>\n<script>{js}</script>\n"
        "<!-- /timtapper sw -->\n"
    )
    index.write_text(html.replace(SHELL_AFTER, SHELL_AFTER + block, 1), encoding="utf-8")
    files = kept_files(site, version)
    build = json.dumps({"id": build_id(site), "files": files}, separators=(",", ":"))
    worker = (sw_dir / SW_FILE).read_text(encoding="utf-8")
    (site / SW_FILE).write_text(f"const BUILD = {build};\n{worker}", encoding="utf-8")
    return files


def finish_site(
    site: Path, version: str, assets: Path = ASSETS, *, shell: bool = True, config: dict | None = None
) -> None:
    """`shell`: paint the shell, from `config` (shell_config() when not given). The driven test builds go without
    it: nothing in them tells it the app is ready, and they test the app itself."""
    dropped = drop_unused(site / APP_ARCHIVE, UNUSED + LATER)
    _log.info("dropped %d unused library files from the Python archive", dropped)
    added = add_assets(site / APP_ARCHIVE, assets)
    _log.info("added %d asset files to the Python archive", added)
    version_archive_url(site / "index.html", version)
    prestart_python(site)
    _log.info("Python starts with the page")
    drop_flutter_service_worker(site)
    if not shell:
        return
    config = config if config is not None else shell_config()
    add_shell(site / "index.html", config)
    _log.info(
        "painting the shell first (%d icons, first-visit shells %s)",
        len(config["icons"]),
        ", ".join(config["defaults"]),
    )
    (site / ".nojekyll").touch()  # GitHub Pages: serve the files as they are
    kept = add_service_worker(site, version, config)
    _log.info("the service worker keeps %d files", len(kept))


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
    if host.ci_job:
        (site / ".gitlab-ci.yml").write_text(GITLAB_CI, encoding="utf-8")


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
