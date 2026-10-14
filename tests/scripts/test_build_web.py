#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.266526
Revised: 2026/10/14 16:30:40.074666

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
    '<base href="/timtapper/"><meta charset="UTF-8">'
    '<script>flet = { appPackageUrl: "assets/app/app.zip", noCdn: false,'
    ' pyodideUrl: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs" };'
    'loader.load({ entrypointBaseUrl: "/timtapper/", assetBase: "/timtapper/" });</script>'
    "<body><script>flutter</script></body>"
)
SHELL = {"version": 1, "icons": {"add": 0xE047}, "defaults": {"light": {"v": 1}, "dark": {"v": 1}}}


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


@pytest.mark.regression
def test_preloads_start_the_archive_and_pyodide_with_the_page(site):
    """flet's loader asked for Pyodide only once Flutter had started and for the archive only once Pyodide had, so
    the three downloads ran one after another (14.6 s to start on a fast line, 12 s of it waiting)."""
    pyodide = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/"
    urls = build_web.add_preloads(site / "index.html", "1.2.1")
    assert urls == ["assets/app/app.zip?v=1.2.1", pyodide + "pyodide.asm.wasm", pyodide + "python_stdlib.zip"]
    html = (site / "index.html").read_text(encoding="utf-8")
    links = [f'<link rel="preload" href="{url}" as="fetch" crossorigin>' for url in urls]
    assert all(link in html for link in links)
    # after <base>, which relative hrefs resolve against, and before any script runs
    assert html.index('<base href="/timtapper/">') < html.index(links[0]) < html.index("<script>")


def test_preloads_refuse_an_unknown_template(site):
    (site / "index.html").write_text('<meta charset="UTF-8"><script>flet = {};</script>', encoding="utf-8")
    with pytest.raises(BuildError, match="web template changed"):
        build_web.add_preloads(site / "index.html", "1.2.1")


def test_unknown_index_template_refuses(site):
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(BuildError, match="web template changed"):
        build_web.version_archive_url(site / "index.html", "1.2.1")


def test_finish_site(site, assets):
    build_web.finish_site(site, "1.2.1", assets, config=SHELL)
    assert (site / ".nojekyll").is_file()
    html = (site / "index.html").read_text(encoding="utf-8")
    assert 'appPackageUrl: "assets/app/app.zip?v=1.2.1"' in html
    assert '<link rel="preload" href="assets/app/app.zip?v=1.2.1" as="fetch" crossorigin>' in html
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
    for name in ("github", "gitlab", "codeberg"):
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
    assert not (site / ".gitlab-ci.yml").exists()
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX


def test_prepare_for_a_ci_host_adds_the_pages_job(site):
    build_web.prepare_for(site, build_web.PagesHost(ci_job=True))
    assert (site / ".gitlab-ci.yml").read_text(encoding="utf-8") == build_web.GITLAB_CI
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX


def test_gitlab_pages_job_publishes_the_site_and_nothing_else():
    job = build_web.GITLAB_CI
    # GitLab Pages deploys a job's `public` folder only when the job says `pages: true`: named `pages` alone, it ran
    # and uploaded the site but nothing was deployed
    assert job.startswith("# ") and "\npages:\n  pages: true\n" in job
    assert "paths: [public]" in job
    assert "grep -vx -e .public -e .git -e .gitlab-ci.yml" in job  # neither the repo nor this file is served
    assert '$CI_COMMIT_BRANCH == "pages"' in job


def test_hosts_github_on_its_domain_and_gitlab_and_codeberg_on_the_subpath():
    hosts = build_web.PAGES_HOSTS
    assert hosts["github"] == build_web.PagesHost("/", "timtapper.breren.com")
    assert hosts["gitlab"] == build_web.PagesHost("/timtapper/", ci_job=True)
    assert hosts["codeberg"] == build_web.PagesHost("/timtapper/")
    assert set(hosts) == {"github", "gitlab", "codeberg"}


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
    assert _git(remotes["gitlab"], "show", "pages:index.html") == INDEX
    assert _git(remotes["gitlab"], "show", "pages:.gitlab-ci.yml") == build_web.GITLAB_CI.rstrip("\n")
    for remote in ("github", "codeberg"):
        assert ".gitlab-ci.yml" not in _git(remotes[remote], "ls-tree", "--name-only", "pages")
    assert (site / "index.html").read_text(encoding="utf-8") == INDEX  # build/web keeps /timtapper/ for the tests
    assert not (site / "CNAME").exists()


def test_publish_to_a_missing_remote_refuses(site, repo_with_remotes):
    repo, _ = repo_with_remotes
    with pytest.raises(BuildError, match="git remote failed"):
        build_web.publish(site, "1.2.1", hosts={"forgejo": build_web.PagesHost()}, repo=repo)


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


def test_drop_unused_takes_out_only_what_the_browser_never_uses(site):
    keep = ["main.pyc", "__pypackages__/sqlalchemy/orm/session.pyc", "__pypackages__/alembic/command.pyc"]
    drop = [
        "__pypackages__/sqlalchemy/testing/fixtures.pyc",
        "__pypackages__/alembic/testing/env.pyc",
        "__pypackages__/bin/alembic.exe",
    ]
    archive = _archive_with(site, keep + drop)
    assert build_web.drop_unused(archive) == 3
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
    build_web.finish_site(site, "1.2.1", assets, shell=False)
    with zipfile.ZipFile(archive) as z:
        assert "__pypackages__/sqlalchemy/testing/fixtures.pyc" not in z.namelist()
        assert "assets/data/leaders.json" in z.namelist()


# ---- the shell ----------------------------------------------------------------------
def test_finish_site_paints_the_shell_first(site, assets):
    build_web.finish_site(site, "1.2.1", assets, config=SHELL)
    html = (site / "index.html").read_text(encoding="utf-8")
    assert html.index("<body>") < html.index("window.TIMTAPPER_SHELL") < html.index("<script>flutter</script>")


def test_finish_site_builds_the_shell_config_when_not_given(site, assets, monkeypatch):
    monkeypatch.setattr(build_web, "shell_config", lambda: SHELL)
    build_web.finish_site(site, "1.2.1", assets)
    assert '"icons":{"add":57415}' in (site / "index.html").read_text(encoding="utf-8")


def test_finish_site_can_leave_the_shell_out(site, assets):
    build_web.finish_site(site, "1.2.1", assets, shell=False)
    assert "TIMTAPPER_SHELL" not in (site / "index.html").read_text(encoding="utf-8")


def test_add_shell_inlines_style_config_and_script(site, tmp_path):
    shell_dir = tmp_path / "shell"
    shell_dir.mkdir()
    (shell_dir / "shell.css").write_text("#tt-shell{}", encoding="utf-8")
    (shell_dir / "shell.js").write_text("paint();", encoding="utf-8")
    config = {**SHELL, "defaults": {"light": {"text": "</script><b>"}}}
    build_web.add_shell(site / "index.html", config, shell_dir)
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "<style>#tt-shell{}</style>" in html and "<script>paint();</script>" in html
    assert r"<\/script><b>" in html and "</script><b>" not in html  # a value can't end the script early


def test_add_shell_again_replaces_the_shell(site):
    index = site / "index.html"
    build_web.add_shell(index, SHELL)
    build_web.add_shell(index, {**SHELL, "version": 2})
    html = index.read_text(encoding="utf-8")
    assert html.count("<!-- timtapper shell -->") == 1 and '"version":2' in html


def test_add_shell_refuses_an_unknown_template(site):
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    with pytest.raises(BuildError, match="<body>"):
        build_web.add_shell(site / "index.html", SHELL)


def test_icon_names_are_every_icon_the_app_names(tmp_path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "a.py").write_text("ft.Icon(ft.Icons.ADD)\nft.Icons.SEARCH_OFF, ft.Icons.ADD", encoding="utf-8")
    assert build_web.icon_names(tmp_path) == {"add", "search_off", *build_web.SHELL_ICONS}


def test_the_apps_icons_are_real_icons():
    """A typo would name an icon Flutter doesn't have, and the build would refuse it."""
    import flet as ft

    assert all(hasattr(ft.Icons, name.upper()) for name in build_web.icon_names())


ICONS_DART = """
  static const IconData add = IconData(0xe047, fontFamily: 'MaterialIcons');
  static const IconData arrow_back = IconData(
    0xe092,
    fontFamily: 'MaterialIcons',
    matchTextDirection: true,
  );
"""


def test_icon_codepoints_reads_flutters_table(tmp_path):
    dart = tmp_path / "icons.dart"
    dart.write_text(ICONS_DART, encoding="utf-8")
    assert build_web.icon_codepoints({"add", "arrow_back"}, dart) == {"add": 0xE047, "arrow_back": 0xE092}
    with pytest.raises(BuildError, match="no search"):
        build_web.icon_codepoints({"add", "search"}, dart)


def test_flutter_icons_is_in_the_sdk_flet_builds_with(tmp_path, monkeypatch):
    import flet_cli.utils.flutter as flutter

    monkeypatch.setattr(flutter, "get_flutter_dir", lambda version: str(tmp_path / version))
    with pytest.raises(BuildError, match="flet build web"):
        build_web.flutter_icons()
    import flet.version

    dart = tmp_path / flet.version.flutter_version / "packages/flutter/lib/src/material/icons.dart"
    dart.parent.mkdir(parents=True)
    dart.write_text(ICONS_DART, encoding="utf-8")
    assert build_web.flutter_icons() == dart


def test_shell_config_names_where_the_app_keeps_the_shell(monkeypatch, tmp_path):
    from core import web

    dart = tmp_path / "icons.dart"
    dart.write_text(
        "".join(f"static const IconData {n} = IconData(0x{i + 1:x});\n" for i, n in enumerate(build_web.icon_names())),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_web, "flutter_icons", lambda: dart)
    monkeypatch.setattr(build_web, "first_visit_shells", lambda: {"light": {}, "dark": {}})
    config = build_web.shell_config()
    assert (config["db"], config["store"], config["key"]) == (web.SHELL_DB, web.SHELL_STORE, web.SHELL_KEY)
    assert (config["channel"], config["ready"]) == (web.SHELL_CHANNEL, web.SHELL_READY)
    assert set(config["icons"]) == build_web.icon_names() and config["defaults"] == {"light": {}, "dark": {}}


@pytest.mark.parametrize("before", [None, "elsewhere"])
def test_first_visit_shells_are_the_empty_app_and_touch_no_data_folder(monkeypatch, before):
    import os

    if before is None:
        monkeypatch.delenv("FLET_APP_STORAGE_DATA", raising=False)
    else:
        monkeypatch.setenv("FLET_APP_STORAGE_DATA", before)
    shells = build_web.first_visit_shells()
    assert set(shells) == {"light", "dark"} and shells["dark"]["dark"] is True
    assert set(shells["light"]["views"]) == {"/events", "/stats", "/settings"}
    assert os.environ.get("FLET_APP_STORAGE_DATA") == before
