#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.266526
Revised: 2026/10/13 22:03:51.266526

The web build's post-processing (scripts/build_web.py): assets added back into the Python archive, the archive
URL versioned in index.html, the site zipped, and publishing to the `pages` branch (against local bare repos).
"""

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("build_web", _SCRIPTS / "build_web.py")
build_web = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_web)

BuildError = build_web.BuildError
INDEX = '<script>flet = { appPackageUrl: "assets/app/app.zip", noCdn: false };</script>'


@pytest.fixture
def assets(tmp_path):
    root = tmp_path / "assets"
    (root / "data").mkdir(parents=True)
    (root / "data" / "leaders.json").write_text("[]")
    (root / "leaders").mkdir()
    (root / "leaders" / "OP01-001.webp").write_bytes(b"webp")
    return root


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "web"
    (root / "assets" / "app").mkdir(parents=True)
    with zipfile.ZipFile(root / build_web.APP_ARCHIVE, "w") as z:
        z.writestr("main.pyc", b"code")
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    return root


@pytest.mark.regression
def test_assets_go_back_into_the_python_archive(site, assets):
    """flet build web leaves assets/ out of the archive, and the web app crashed reading leaders.json."""
    archive = site / build_web.APP_ARCHIVE
    assert build_web.add_assets(archive, assets) == 2
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == ["assets/data/leaders.json", "assets/leaders/OP01-001.webp", "main.pyc"]
        assert z.read("assets/leaders/OP01-001.webp") == b"webp"


def test_adding_assets_twice_adds_nothing(site, assets):
    archive = site / build_web.APP_ARCHIVE
    build_web.add_assets(archive, assets)
    assert build_web.add_assets(archive, assets) == 0
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 3


def test_archive_url_carries_the_version(site):
    build_web.version_archive_url(site / "index.html", "1.2.1")
    assert 'appPackageUrl: "assets/app/app.zip?v=1.2.1"' in (site / "index.html").read_text(encoding="utf-8")


def test_unknown_index_template_refuses(site):
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(BuildError, match="web template changed"):
        build_web.version_archive_url(site / "index.html", "1.2.1")


def test_finish_site(site, assets):
    build_web.finish_site(site, "1.2.1", assets)
    assert (site / ".nojekyll").is_file()
    assert "?v=1.2.1" in (site / "index.html").read_text(encoding="utf-8")
    with zipfile.ZipFile(site / build_web.APP_ARCHIVE) as z:
        assert "assets/data/leaders.json" in z.namelist()


def test_zip_site_keeps_paths_relative(site, tmp_path):
    out = build_web.zip_site(site, tmp_path / "timtapper-1.2.1-web.zip")
    with zipfile.ZipFile(out) as z:
        assert sorted(z.namelist()) == ["assets/app/app.zip", "index.html"]


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo_with_remotes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    remotes = {}
    for name in ("github", "codeberg"):
        bare = tmp_path / f"{name}.git"
        _git(tmp_path, "init", "-q", "--bare", str(bare))
        _git(repo, "remote", "add", name, str(bare))
        remotes[name] = bare
    return repo, remotes


def test_publish_force_pushes_one_commit_to_every_remote(site, repo_with_remotes):
    repo, remotes = repo_with_remotes
    build_web.publish(site, "1.2.0", repo=repo)
    (site / "index.html").write_text("v2", encoding="utf-8")
    build_web.publish(site, "1.2.1", repo=repo)
    for bare in remotes.values():
        assert _git(bare, "log", "--format=%s", "pages") == "[B] web 1.2.1"  # replaced, not stacked
        assert _git(bare, "show", "pages:index.html") == "v2"
        assert "assets/app/app.zip" in _git(bare, "ls-tree", "-r", "--name-only", "pages")


def test_publish_to_a_missing_remote_refuses(site, repo_with_remotes):
    repo, _ = repo_with_remotes
    with pytest.raises(BuildError, match="git remote failed"):
        build_web.publish(site, "1.2.1", remotes=("gitlab",), repo=repo)


def test_main_reports_a_failed_build_and_exits_1(monkeypatch):
    def fail():
        raise BuildError("flet build left no assets/app/app.zip")

    errors = []
    monkeypatch.setattr(build_web, "build", fail)
    monkeypatch.setattr(build_web._log, "error", lambda msg, *args: errors.append(msg % args))
    monkeypatch.setattr("sys.argv", ["build_web.py"])
    assert build_web.main() == 1
    assert errors == ["build failed: flet build left no assets/app/app.zip"]


@pytest.mark.parametrize(("argv", "published"), [([], False), (["--publish"], True)])
def test_main_publishes_only_when_asked(monkeypatch, argv, published):
    calls = []
    monkeypatch.setattr(build_web, "build", lambda: calls.append("build"))
    monkeypatch.setattr(build_web, "publish", lambda site, version: calls.append(("publish", version)))
    monkeypatch.setattr("sys.argv", ["build_web.py", *argv])
    assert build_web.main() == 0
    assert calls == ["build", *([("publish", build_web.project_version())] if published else [])]
