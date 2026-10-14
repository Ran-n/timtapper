#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.266526
Revised: 2026/10/14 13:16:04.086061

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
INDEX = (
    '<base href="/timtapper/">'
    '<script>flet = { appPackageUrl: "assets/app/app.zip", noCdn: false };'
    'loader.load({ entrypointBaseUrl: "/timtapper/", assetBase: "/timtapper/" });</script>'
)


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


def test_built_base_is_the_flet_base_url():
    assert build_web.BUILT_BASE == "/timtapper/"


def test_rebase_site_moves_every_base_path(site):
    build_web.rebase_site(site, "/")
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "/timtapper/" not in html
    assert '<base href="/">' in html
    assert 'entrypointBaseUrl: "/"' in html
    assert 'assetBase: "/"' in html


def test_rebase_site_to_the_built_base_changes_nothing(site):
    build_web.rebase_site(site, "/timtapper/")
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX


def test_rebase_site_refuses_an_unknown_template(site):
    (site / "index.html").write_text('<base href="/timtapper/">', encoding="utf-8")
    with pytest.raises(BuildError, match="entrypointBaseUrl"):
        build_web.rebase_site(site, "/")


def test_prepare_for_a_custom_domain_writes_cname(site):
    build_web.prepare_for(site, build_web.PagesHost("/", "timtapper.breren.com"))
    assert (site / "CNAME").read_text(encoding="utf-8") == "timtapper.breren.com\n"
    assert '<base href="/">' in (site / "index.html").read_text(encoding="utf-8")


def test_prepare_for_a_subpath_host_leaves_the_site_alone(site):
    build_web.prepare_for(site, build_web.PagesHost())
    assert not (site / "CNAME").exists()
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX


def test_github_pages_serves_the_custom_domain_and_codeberg_the_subpath():
    hosts = build_web.PAGES_HOSTS
    assert hosts["github"] == build_web.PagesHost("/", "timtapper.breren.com")
    assert hosts["codeberg"] == build_web.PagesHost("/timtapper/")
    assert set(hosts) == {"github", "codeberg"}


def test_publish_force_pushes_one_commit_to_every_remote(site, repo_with_remotes):
    repo, remotes = repo_with_remotes
    build_web.publish(site, "1.2.0", repo=repo)
    (site / "index.html").write_text(INDEX + "<!-- v2 -->", encoding="utf-8")
    build_web.publish(site, "1.2.1", repo=repo)
    for bare in remotes.values():
        assert _git(bare, "log", "--format=%s", "pages") == "[B] web 1.2.1"  # replaced, not stacked
        assert _git(bare, "show", "pages:index.html").endswith("<!-- v2 -->")
        assert "assets/app/app.zip" in _git(bare, "ls-tree", "-r", "--name-only", "pages")


def test_publish_prepares_each_host_and_leaves_the_build_untouched(site, repo_with_remotes):
    repo, remotes = repo_with_remotes
    build_web.publish(site, "1.3.0", repo=repo)
    github = _git(remotes["github"], "show", "pages:index.html")
    assert '<base href="/">' in github
    assert "/timtapper/" not in github
    assert _git(remotes["github"], "show", "pages:CNAME") == "timtapper.breren.com"
    assert _git(remotes["codeberg"], "show", "pages:index.html") == INDEX
    assert "CNAME" not in _git(remotes["codeberg"], "ls-tree", "--name-only", "pages")
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX  # build/web keeps /timtapper/ for the tests
    assert not (site / "CNAME").exists()


def test_publish_to_a_missing_remote_refuses(site, repo_with_remotes):
    repo, _ = repo_with_remotes
    with pytest.raises(BuildError, match="git remote failed"):
        build_web.publish(site, "1.2.1", hosts={"gitlab": build_web.PagesHost()}, repo=repo)


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


def _archive_with(site, names):
    with zipfile.ZipFile(site / build_web.APP_ARCHIVE, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.writestr(name, name.encode())
    return site / build_web.APP_ARCHIVE


def test_drop_unused_takes_out_only_the_test_suites(site):
    keep = ["main.pyc", "__pypackages__/sqlalchemy/orm/session.pyc", "__pypackages__/alembic/command.pyc"]
    drop = ["__pypackages__/sqlalchemy/testing/fixtures.pyc", "__pypackages__/alembic/testing/env.pyc"]
    archive = _archive_with(site, keep + drop)
    assert build_web.drop_unused(archive) == 2
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == sorted(keep)
        assert z.read("__pypackages__/sqlalchemy/orm/session.pyc") == b"__pypackages__/sqlalchemy/orm/session.pyc"
    assert not archive.with_name(archive.name + ".slim").exists()


def test_drop_unused_leaves_a_clean_archive_untouched(site):
    archive = site / build_web.APP_ARCHIVE
    before = archive.stat().st_mtime_ns
    assert build_web.drop_unused(archive) == 0
    assert archive.stat().st_mtime_ns == before


def test_finish_site_drops_the_test_suites(site, assets):
    archive = _archive_with(site, ["main.pyc", "__pypackages__/sqlalchemy/testing/fixtures.pyc"])
    build_web.finish_site(site, "1.2.1", assets)
    with zipfile.ZipFile(archive) as z:
        assert "__pypackages__/sqlalchemy/testing/fixtures.pyc" not in z.namelist()
        assert "assets/data/leaders.json" in z.namelist()
