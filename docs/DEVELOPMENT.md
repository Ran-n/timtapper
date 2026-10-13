[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/13 16:19:34.144622 )
[//]: # (+ Revised: 	2026/10/13 22:03:51.585120 )
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

## Run on desktop

```sh
uv sync
uv run flet run
```

Run it from the repository root, so dev data goes to `.flet/storage/` (git-ignored) and not into the folder that gets
packaged. `uv run timtapper` also works and stores data in `~/.timtapper/`.

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

## Build for the web

```sh
uv run python scripts/build_web.py              # build/web + dist/timtapper-<version>-web.zip
uv run python scripts/build_web.py --publish    # ...then force-push it to the `pages` branch
```

`flet build web` turns the app into a static site whose Python runs in the browser on Pyodide. The script fixes two
things after it: flet leaves `assets/` out of the Python archive (the app reads `leaders.json`, fonts and portraits
from disk, so they go back in), and `index.html` asks for the archive with `?v=<version>`, so browsers fetch the new
one after a release. `[tool.flet.web]` in `pyproject.toml` sets the `/timtapper/` base path and `#` routes, so a
reload on any screen only ever asks the host for `index.html`.

`--publish` pushes the site as the single commit of the `pages` branch on `github` and `codeberg`, served at
[ran-n.github.io/timtapper](https://ran-n.github.io/timtapper/) (Settings → Pages: branch `pages`, root) and
[ran-n.codeberg.page/timtapper](https://ran-n.codeberg.page/timtapper/). Publish after each release, from its tag.

In the browser the file system is in memory: `core/web.py` mounts the data folder on IndexedDB, loads it before the
database opens and saves it after every commit. Sharing hands the browser the file's bytes rather than its path, and
falls back to a download.

## Tests

```sh
uv run pytest                            # unit, DB, migrations, widget tree, property, regression
uv run pytest --cov                      # same, failing below 99% branch coverage
uv run pytest -m "live and not desktop"  # against the real optcgapi.com and Limitless TCG (~40 s)
uv run pytest -m desktop                 # the real app, rendered (Windows; takes over mouse and screen ~2 min)
uv run pytest -m "desktop or live"       # both, including a real click on Update leaders
uv run pytest -m web                     # the built web app in headless Chrome (needs build_web.py first, ~1.5 min)
uv run ruff format src scripts tests && uv run ruff check src scripts tests
```

**CI.** `scripts/ci.sh` runs what CI runs on every push to `main` and every pull/merge request on GitHub
(`.github/workflows/ci.yml`), GitLab (`.gitlab-ci.yml`) and Codeberg (`.forgejo/workflows/ci.yml`, once Actions is
enabled): a locked `uv sync`, `ruff format --check`, `ruff check` and `pytest --cov`. The `live`, `desktop` and
`web` tests stay local.

**Live tests** check what mocks can't: that the card lists still parse and still hold every bundled leader and set,
that card images still download and crop, that a full sync fills a real database, and that Update leaders and the
startup check work end to end.

**Regressions.** Every bug fix comes with a test marked `regression` that says what used to go wrong.

**Golden files.**
- Backups: `tests/backup/golden/v3.json` pins the current shape, so a change fails until `VERSION` is bumped; every
  older file (`v1.json`, `v2.json`) must still restore.
- Share cards: each is rendered from fixed data and compared with an approved image in `tests/share/golden/`.

**Rendered tests** (`tests/rendered/`, marker `desktop`) start the real app on demo data, click it with the real
mouse and check the captured pixels: badges side by side, die pips, the picker's dots on one line at 360 dp, portrait
frame bands, theme swatches, tap-cycling, picker filters and theme switching. Captures are shrunk to dp and clicks
scaled back up, so they pass at any Windows display scaling. Whole screens are compared with baselines, including
settings in Spanish at 360 dp (the longest labels), one set per scaling: `tests/rendered/baselines/` at 100%,
`baselines/scale-125/` at 125%. Keep the window uncovered while they run.

**Web tests** (`tests/web/`, marker `web`) serve `build/web` under `/timtapper/` and drive it in headless Chrome:
events survive a reload on an inner screen, sharing downloads the card where the browser has no Web Share API, and a
backup exported in one browser restores in another and survives its reload.

After an intended visual change, rerun the share-card or rendered tests with `TIMTAPPER_UPDATE_BASELINES=1`, review
every rewritten image and commit it.

## README screenshots

```sh
uv run python scripts/make_screenshots.py
```

Opens the app on a throwaway database seeded with demo events (`scripts/app_driver.py`, shared with the rendered
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
  core/             logging, storage paths, the web build's browser storage (web.py), errors, version
  stats/            pure stat functions (records, splits, matchups)
  share/            Pillow share cards + share-sheet/save delivery
  backup/           JSON export/import
  db/               SQLAlchemy models, Alembic migrations
  i18n/             en/es/gl tables keyed by English source strings
  ui/               screens (events, event, stats, settings), picker, widgets
  assets/           fonts, icons, logo_mark, bundled leaders.json + leaders/*.webp portraits
scripts/            build_leaders, build_android, build_web, make_icon, make_screenshots, make_bye_joker,
                    app_driver + app_window (run, capture and click the real app), ci.sh
docs/               logo, screenshots, these docs
tests/              mirrors src/timtapper; rendered/ drives the real app (marker `desktop`), web/ the web build
                    (marker `web`)
```

## Third-party art

The jester standing in for a bye's opponent is adapted from Microsoft's
[Fluent Emoji](https://github.com/microsoft/fluentui-emoji) "Joker" (MIT License, © Microsoft Corporation; the notice
ships as `src/timtapper/assets/LICENSE-fluent-emoji.txt`).
