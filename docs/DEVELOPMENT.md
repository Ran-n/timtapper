[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/13 16:19:34.144622 )
[//]: # (+ Revised: 	2026/10/14 17:09:23.883094 )
[//]: # ( ---------------------------------------------------------------------- )

# Development

Building, testing and maintaining timtapper. See [CONTRIBUTING.md](../CONTRIBUTING.md) for how to submit changes.

## Stack

| Layer   | Technology                                                            |
|---------|-----------------------------------------------------------------------|
| UI      | Flet 1.0 (Android APK, desktop, web on Pyodide)                       |
| Storage | SQLite via SQLAlchemy 2.0, schema migrated by Alembic on startup      |
| Images  | Pillow, with the Poppins font bundled (OFL)                           |
| Leaders | Bundled JSON + optcgapi.com, release dates from Limitless TCG (httpx) |
| Tooling | uv, ruff, pytest (+ hypothesis, respx)                                |

## Requirements

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/)
- For Android builds: the Flutter/Android toolchain that `flet build` uses
- For Windows builds: Visual Studio's C++ desktop workload (what `flet build windows` needs) and
  [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`) for the installer

## Run on desktop

```sh
uv sync
uv run flet run
```

Run it from the repository root, so dev data goes to `.flet/storage/` (git-ignored) and not into the folder that gets
packaged. `uv run timtapper` also works and stores data in `~/.timtapper/`.

Environment variables:

| Variable | Default | What it does |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Log level of the `timtapper.*` loggers (`DEBUG`, `INFO`, `WARNING`, `ERROR`); an unknown one falls back to `INFO` with a warning |
| `FLET_APP_STORAGE_DATA` | `~/.timtapper` | Where the database and downloaded portraits live; `flet run` and packaged builds set it |
| `FLET_APP_STORAGE_TEMP` | system temp + `/timtapper` | Where share cards and backup exports are written before the share sheet takes them |

## Build for Android

```sh
uv run python scripts/build_android.py            # Google Play bundle: dist/timtapper-<version>.aab
uv run python scripts/build_android.py apk        # sideloading: dist/timtapper-<version>-<abi>.apk
uv run python scripts/build_android.py universal  # sideloading, every ABI: dist/timtapper-<version>-universal.apk
```

The universal APK is about 2.5× the size of a per-ABI one (157 MB for 1.2.1), over GitLab's 100 MB release-attachment
limit: upload it to the project's generic package registry and link that from the GitLab release instead.

Don't call `flet build` directly for a release: it signs with the debug key.

**Signing.** Both are signed with the upload key, kept outside the repository at `../secrets/timtapper-upload.jks`
(alias `upload`), with its password in `../secrets/timtapper-upload.pass`. To use a key elsewhere, set
`FLET_ANDROID_SIGNING_KEY_STORE`, `FLET_ANDROID_SIGNING_KEY_ALIAS` and `FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD`.
Without a key the script stops rather than fall back to the debug key, which Google Play rejects, and after the build
it checks every file carries the upload key's certificate. Losing the key store blocks every Play update until Google
resets the upload key, so keep a copy off this machine.

**Version codes** come from the version: 1.1.0 becomes 101000000. The last four digits leave room for the offset
`--split-per-abi` adds to each APK, so every APK of a release sorts above those of the one before (the universal APK
takes the plain code, below that release's per-ABI ones but above every APK of the release before). The script deletes
`build/aab/` or `build/apk/` first, so no stale per-ABI APK is left behind.

APKs up to 1.1.0 were signed with the debug key. Android won't update them in place: export a backup, uninstall,
install the new APK, then restore.

## Build for Windows

```sh
uv run python scripts/build_windows.py    # build/windows + dist/timtapper-<version>-windows-x64.zip and -setup.exe
```

`flet build windows` makes a folder, not a single file: `timtapper.exe` is a small launcher that needs the Flutter
engine, the plugin DLLs and the bundled Python beside it. The script packs that folder twice: as the portable zip, and
as an installer compiled by Inno Setup from `scripts/timtapper.iss`. The installer installs for the current user by
default (no admin prompt), adds a Start-menu entry, an optional desktop shortcut and an uninstaller, and on an upgrade
replaces the bundled Python and app code whole. The app's data lives elsewhere, so upgrading or uninstalling keeps it.
Never change the `AppId` in the `.iss`: Windows matches upgrades on it.

Before packaging, the script deletes the debug build of each Python extension module that flet ships next to the
release one (`DLLs/<name>_d.pyd`, about 9 MB). Attach both files to every release.

## Build for the web

```sh
uv run python scripts/build_web.py              # build/web + dist/timtapper-<version>-web.zip
uv run python scripts/build_web.py --publish    # ...then force-push it to the `pages` branch
```

`flet build web` turns the app into a static site whose Python runs in the browser on Pyodide. The script changes five
things after it: flet leaves `assets/` out of the Python archive (the app reads `leaders.json`, fonts and portraits
from disk, so they go back in); it takes what the browser never uses out of that archive (SQLAlchemy's and Alembic's
own test suites, the Windows launchers in `bin/`; `UNUSED` in `scripts/build_web.py`); `index.html` preloads the
archive and the Pyodide runtime, which flet's loader would otherwise fetch one after the other, each only once the one
before has started (a first visit took 14.6 s, about 8 s with the preloads); and `index.html` asks for the archive
with `?v=<version>`, so browsers fetch the new one after a release; and `index.html` paints the web shell first (below).
`[tool.flet.web]` in `pyproject.toml` sets the `/timtapper/` base path and `#` routes, so a reload on any screen only
ever asks the host for `index.html`.

**The web shell.** Even with everything cached, Python takes about 4 s to start in the browser, so the page doesn't
wait for it. `index.html` carries `scripts/shell/` inline and paints a read-only copy of the app's screens at once:
what the app saved on the last visit, or on a first visit the empty app, built with the site in light and dark.
`ui/shell.py` writes that copy: after every change (a commit that wrote, a new language or theme, a screen change) it
builds each screen the app can open at startup — the three tabs and every event — with the app's own `build_view`,
and saves the control tree as JSON in the browser's IndexedDB (`ShellStore` in `core/web.py`), with colours resolved
and icons by name (the build adds the codepoints of every `ft.Icons` the code names, read from Flutter's
`icons.dart`). An event's screen is rebuilt only when it or the look changes, and the digests are saved with the
copy, so a new visit picks up where the last left off. `scripts/shell/shell.js` draws the tree with flexbox under
Flutter's Material 3 sizes at web (compact) density; tabs, events and back work in the copy, a tap that needs the app
shows *Opening…*, and *New event* queues `#/new` (`NEW_ROUTE`, which starts one event, once). When the app has drawn
its first screen it says so on a `BroadcastChannel`, with its route; the page sends it to the screen the copy shows if
that's another one, and fades the copy out. The driven test builds go without it (`finish_site(shell=False)`):
nothing in them says when they're ready. `tests/web` checks it in Chrome: the empty app on a first visit, your events
on the next, opening one in the copy, the tabs and *New event*.

Every package imported before the first screen is unpacked and compiled in the browser while the visitor waits, so
PIL (leader updates and share cards only) is imported where it's used, not at module level in `catalog/portraits.py`
or the share views; `tests/test_startup_imports.py` fails if it, or a library test suite, comes back into startup.

`--publish` pushes the site as the single commit of the `pages` branch on `github`, `gitlab` and `codeberg`, served at
[timtapper.breren.com](https://timtapper.breren.com/), [ran-n.codeberg.page/timtapper](https://ran-n.codeberg.page/timtapper/)
and [ran-n.gitlab.io/timtapper](https://ran-n.gitlab.io/timtapper/). Publish after each release, from its tag.
Codeberg serves the build as it is, under `/timtapper/`; GitHub's copy is rebased to `/` and carries a `CNAME` file
naming the domain (`PAGES_HOSTS` in `scripts/build_web.py`). GitLab serves only what a CI job publishes, so its copy
carries a `.gitlab-ci.yml` whose `pages: true` job publishes the files as they are (Settings → Pages: access for
everyone, unique domain off, so it's served under `/timtapper/` like Codeberg). GitLab takes 15–20 minutes after the
job to serve a new copy; until then the previous one stays up. `build/web` and the release's web zip keep `/timtapper/`.

GitHub Pages: Settings → Pages, branch `pages`, root, custom domain `timtapper.breren.com`, HTTPS enforced. The domain
is a DNS-only (not proxied) Cloudflare `CNAME` from `timtapper` to `ran-n.github.io`, so GitHub can issue its
certificate; the old `ran-n.github.io/timtapper/` redirects there.

In the browser the file system is in memory: `core/web.py` mounts the data folder on IndexedDB, loads it before the
database opens and saves it after every commit that wrote (reads commit too, and used to save the whole file again). Sharing hands the browser the file's bytes rather than its path, and
falls back to a download.

## Tests

```sh
uv run pytest                            # unit, DB, migrations, widget tree, property, regression
uv run pytest --cov                      # same, failing below 100% branch coverage
uv run pytest -m "live and not desktop and not web and not android"   # the real optcgapi.com and Limitless (~40 s)
uv run pytest -m desktop                 # every UI test on Windows (takes over mouse and screen ~8 min)
uv run pytest -m web                     # every UI test in headless Chrome (~5 min)
uv run pytest -m android                 # every UI test on the Android emulator (~12 min)
uv run pytest -m live                    # the live tests, a real click on Update leaders on every target included
uv run ruff format src scripts tests && uv run ruff check src scripts tests
```

**CI.** `scripts/ci.sh` runs what CI runs on every push to `main` and every pull/merge request on GitHub
(`.github/workflows/ci.yml`), GitLab (`.gitlab-ci.yml`) and Codeberg (`.forgejo/workflows/ci.yml`, once Actions is
enabled): a locked `uv sync`, `ruff format --check`, `ruff check` and `pytest --cov`. The `live`, `desktop`, `web`
and `android` tests stay local; all of them pass before a version bump.

**Live tests** check what mocks can't: that the card lists still parse and still hold every bundled leader and set,
that card images still download and crop, that a full sync fills a real database, and that Update leaders and the
startup check work end to end.

**Regressions.** Every bug fix comes with a test marked `regression` that says what used to go wrong.

**Golden files.**
- Backups: `tests/backup/golden/v3.json` pins the current shape, so a change fails until `VERSION` is bumped; every
  older file (`v1.json`, `v2.json`) must still restore.
- Share cards: each is rendered from fixed data and compared with an approved image in `tests/share/golden/`.

**Every UI target gets the same tests.** The app ships to Windows, the browser and Android, and each one runs the
same rendered suite plus its own platform checks; a target with fewer tests than the others is a gap.

**Rendered tests** (`tests/rendered/`) start the real app on demo data (`scripts/demo_driver.py`), tap it for real
and check the captured pixels and what the app stored: badges side by side, die pips, the picker's dots on one line
at 360 dp, portrait frame bands, theme swatches, tap-cycling, the round editors, typing in the header, dialogs, picker
filters and theme switching. Each test runs once per target (`tests/rendered/targets.py`):

| Target | Marker | The app | Input |
|---|---|---|---|
| desktop | `desktop` | `scripts/app_driver.py` in a Windows window | real mouse and keyboard (`scripts/app_window.py`) |
| web | `web` | the driven web build in headless Chrome | Playwright touches, keys and wheel |
| android | `android` | the driven APK on an emulator | adb touches, keys and drags (`scripts/android_phone.py`) |

The web and Android targets run driven builds: the real app built by `flet build` with the demo driver inside,
started from `scripts/driven_main.py`, polling the test harness for commands (`scripts/serve_site.py`). Build them
first, and again after changing the app:

```sh
uv run python scripts/build_driven.py           # build/driven/web and build/driven/timtapper-<version>-driven-x86_64.apk
```

Captures are shrunk to dp and taps scaled back up, so the tests pass at any pixel density; the browser and the phone
get the desktop window's client area (396 x 853 dp, 344 dp wide at the 360 dp minimum). Phones lay controls out
roomier than desktops, so a test that needs something below the fold scrolls until it's there (`locate.scroll_until`)
instead of assuming how much fits. Whole screens are compared with baselines, one set per target in
`tests/rendered/baselines/<target>/` (desktop: one per display scaling, `desktop/scale-125/` at 125%), including
every screen in Spanish and Galician at 360 dp (the longest labels). Keep the desktop window uncovered while it runs.

The Android target uses the running emulator or device, or boots the generic `generic_phone_api34` AVD (Pixel 7,
API 34, x86_64; another with `TIMTAPPER_AVD`) headless and shuts it down afterwards. It installs the driven APK as its
own app (`com.breren.timtapper.driven`), and puts back everything it changed: the app, the port mapping, the display
size and the on-screen-keyboard setting. adb can only type ASCII, so the one test that types a non-ASCII name types
an ASCII one there.

**Platform checks** test what only that platform's own build shows, against the last release build of each:

- `tests/desktop/` (marker `desktop`): `main.py` on a fresh data folder. Events survive the app being killed and
  started again; Share reaches Windows' share or save dialog; a backup restores through Windows' Open dialog and
  stays. The app keeps your saved theme, so close a running timtapper first.
- `tests/web/` (marker `web`): `build/web` under `/timtapper/` in headless Chrome. Events survive a reload on an inner
  screen; sharing downloads the card where the browser has no Web Share API; a backup exported in one browser
  restores in another and survives its reload.
- `tests/android/` (marker `android`): `dist/timtapper-<version>-x86_64.apk`, read through its log in logcat. Events
  survive the process being killed; Share opens Android's share sheet; a backup restores through Android's own file
  picker and survives a restart.

After an intended visual change, rerun the share-card or rendered tests with `TIMTAPPER_UPDATE_BASELINES=1`, review
every rewritten image and commit it.

## README screenshots

```sh
uv run python scripts/make_screenshots.py
```

Opens the app on a throwaway database seeded with demo events (`scripts/demo_driver.py`, shared with the rendered
tests), walks the screens and saves them to `docs/screenshots/`, plus an event share card. Your own data is never
touched. Windows only (Flet's page capture returns nothing on desktop, so Pillow grabs the window); keep it uncovered
while it runs.

## Leader catalogue and portraits

Installed apps fetch new sets themselves, so this only matters for fresh installs: run it before a release.

```sh
uv run python scripts/build_leaders.py           # --force re-crops every portrait
```

It rewrites `leaders.json` (including the set ids the app compares against to spot a new release, and each set's
release date) and adds a portrait to `assets/leaders/` for every leader that lacks one.

**Face positions.** Each portrait is cropped around the face position set for that card in
`scripts/portrait_crops.json`: `{"OP01-001": [cx, cy, side]}`, as fractions of the card width. Automatic face
detection found only 6 of 138 faces in One Piece card art, so positions are set by eye. A card with two characters
(e.g. ST22-001 Ace & Newgate) takes a list of boxes, `[[cx, cy, side], [cx, cy, side]]`, and each face fills one
vertical strip. A new leader without an entry gets the default upper-middle crop and a warning: add an entry and rerun
with `--force`.

**Watermarks.** Where the card image's "SAMPLE" watermark crosses a face, `scripts/portrait_overlays.json` locates it
and it's removed before cropping, either as letter boxes (`{"ST22-001": [[x0, y0, x1, y1], …]}`, same units) or as
the whole word (`{"OP09-001": {"word": [x, y, width]}}`, top-left corner and width), drawn with the letter shapes in
`scripts/watermark.png`. Its place and size differ per card, so each entry is measured by hand. On most cards it's
see-through and the art under it is recovered exactly; on a few (OP02-049, OP04-019, OP05-041, OP05-060) it's solid
white, and `"opaque": true` paints the letters over from the surrounding art instead.

## Other scripts

- `scripts/make_icon.py`: app icons, `logo_mark` and the `docs/logo.png` wordmark.
- `scripts/make_bye_joker.py`: renders `scripts/bye_jester.svg` to the app's bye PNG.

## Project layout

```
src/timtapper/      Flet app root (flet build packages this folder)
  main.py           entry point: open DB, migrate, sync leaders, route
  catalog/          leader catalogue: optcgapi + Limitless parsers, bundled list, repository, portraits, daily sync
  events/           events and rounds: CRUD as plain dataclasses
  core/             logging, storage paths, the web build's browser storage and shell store (web.py), errors, version
  stats/            pure stat functions (records, splits, matchups)
  share/            Pillow share cards + share-sheet/save delivery
  backup/           JSON export/import
  db/               SQLAlchemy models, Alembic migrations
  i18n/             en/es/gl tables keyed by English source strings
  ui/               screens (events, event, stats, settings), picker, widgets, the web shell's screen copies (shell.py)
  assets/           fonts, icons, logo_mark, bundled leaders.json + leaders/*.webp portraits
scripts/            build_leaders, build_android, build_windows (+ timtapper.iss), build_web, build_driven,
                    make_icon, make_screenshots,
                    make_bye_joker, demo_driver (the demo data and driver commands), app_driver + app_window
                    (desktop), driven_main + serve_site (web, Android), android_phone (adb), ci.sh;
                    shell/ (the web shell's script and style, inlined into index.html by build_web)
docs/               logo, screenshots, these docs
tests/              mirrors src/timtapper; rendered/ drives the real app on every target (markers `desktop`,
                    `web`, `android`); desktop/, web/ and android/ check each platform's own build
```

## Third-party art

The jester standing in for a bye's opponent is adapted from Microsoft's
[Fluent Emoji](https://github.com/microsoft/fluentui-emoji) "Joker" (MIT License, © Microsoft Corporation; the notice
ships as `src/timtapper/assets/LICENSE-fluent-emoji.txt`).
