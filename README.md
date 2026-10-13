[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.910831 )
[//]: # (+ Revised: 	2026/10/13 07:39:28.221889 )
[//]: # ( ---------------------------------------------------------------------- )

# timtapper

<p align="center"><img src="docs/logo.png" alt="timtapper" width="420"></p>

<p align="center">
  <b>Match tracker for the One Piece Trading Card Game.</b><br>
  Log every round, see your matchups, share your results. Android and desktop, fully offline.
</p>

<p align="center">
  <img src="docs/screenshots/events.png" alt="Events list" width="200">
  <img src="docs/screenshots/event.png" alt="An event and its rounds" width="200">
  <img src="docs/screenshots/stats.png" alt="Stats" width="200">
  <img src="docs/screenshots/picker.png" alt="Leader picker with color and set filters" width="200">
</p>

timtapper is local-first: there are no accounts, no server and no sync. Your events live in a SQLite database on your
device, and a JSON backup moves them to another install.

## Features

### Log as you play

- **Events**: every official One Piece TCG event type (Pirates Party, locals, release events, sealed, Heroines Battle,
  team battles, Store Championship, Treasure Cup, Flagship Battle, Extra Grand Battle, regional, national, World
  Championship), plus your own testing sessions and "other", each with a name, date, your leader and notes,
  plus the set it was played in, where you finished and how many played, shown as standings are talked about
  ("Top 4 · #3 of 32", "1st place", "Dropped"; testing sessions have no standings).
  Search the list by name, or open its filters to narrow it by your leader, event type and set; the filters stay set
  while you open an event and come back. A new event is named after its type and count ("Local #4"), starts in the
  newest set, follows a type change while you haven't renamed it, and is discarded if you go back without changing
  anything.
- **Rounds**, the way [davyback.gg](https://davyback.gg) logs them, and then some: each is **Swiss**, **top cut** or a
  **bye** (no opponent, an automatic win, shown with a jester where a leader would be). A Swiss row reads die roll,
  turn order and result; tap any of them to cycle it (the die shows a green six when you won it, a red one when you
  lost it). Top cut is played as a **best of 3**: the row keeps its round number, shows the score and lists each game
  under it with its own turn order, result and who chose the turn order (the higher seed in game 1, then whoever lost
  the game before, filled in for you and tappable for events that do it differently). Any round can be switched
  between best of 1 and 3; a switch that would drop games holding a result or turn order (best of 3 to 1, or a played
  round to a bye) asks first. Results are W/L only: the OPTCG has no draws. Round notes show on the row; everything is
  edited in place, with no forms. Rounds stay collapsed unless you open one, and an open round stays open until you
  close it.
- **Leader picker**: search by name, code or color, then narrow by color dots (a leader must have every color you
  select) and by set. The opponents you face most come first; the list shows 60 at a time and says how many more a
  search would find.

### Understand your results

- **Stats**: overall record and win rate (a best of 3 counts once; byes stay out), the games behind it, going 1st vs
  2nd and won vs lost die roll per game, who chose the turn order, best and worst matchup (3+ matches; no worst when it
  would win as often as the best), recent form and a full matchup table. Filter by your leader (each shown with its portrait), event type and set.
- **Share images**: 1080×1350 PNG cards rendered on-device for an event, a matchup or your overall summary, with the
  app's logo and each leader's portrait framed in its colors; stats narrowed to one leader carry that leader's
  portrait in the header. The event card puts your placement in a band of its own
  and shows each round's turn order, die roll and result. A long event name shrinks and wraps onto a second line
  rather than being cut. On Android they open the system share sheet; on desktop you get a save dialog. Rendered
  cards and exported backups left in the app's temp folder are deleted after a day.

<p align="center">
  <img src="docs/screenshots/share-card.png" alt="Event share card" width="320">
</p>

### Make it yours

- **Themes**: Gruvbox (default), Catppuccin, Nord, Solarized, Tokyo Night and Classic, each with a light and a dark
  palette. Follow the system or force light or dark. Typeset in Poppins.
- **Languages**: English, Español, Galego.
- **Desktop**: the window opens phone-shaped (412 × 892), so the layout is the same as on a phone; resize it freely
  down to 360 × 640.

<p align="center">
  <img src="docs/screenshots/settings.png" alt="Settings in the light Gruvbox theme" width="200">
  <img src="docs/screenshots/events-light.png" alt="Events list in the light Gruvbox theme" width="200">
</p>

### Always current, always yours

- **Leader catalogue**: 138 leaders up to OP17 ship with the app, each with a small portrait cropped from its card art,
  so it works offline. New sets arrive on their own: once a day, at startup, the app asks
  [optcgapi.com](https://optcgapi.com) for its list of sets (a few KB) and downloads leaders and portraits only when a
  new set is listed. Failures are logged and retried on the next start. *Settings → Update leaders* forces a refresh.
- **Backup**: export every event to a JSON file and restore it on any install.

## Stack

| Layer   | Technology                                                       |
|---------|------------------------------------------------------------------|
| UI      | Flet 1.0 (Android APK + desktop)                                 |
| Storage | SQLite via SQLAlchemy 2.0, schema migrated by Alembic on startup |
| Images  | Pillow, with the Poppins font bundled (OFL)                      |
| Leaders | Bundled JSON + optcgapi.com (httpx)                              |
| Tooling | uv, ruff, pytest (+ hypothesis, respx)                           |

## Requirements

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/)
- For APK builds: the Flutter/Android toolchain that `flet build` uses

## Setup

```sh
uv sync
```

## Run (desktop)

Run from the repository root, so dev data goes to `.flet/storage/` (git-ignored) and not into the app folder that gets
packaged:

```sh
uv run flet run
```

`uv run timtapper` also works; it stores data in `~/.timtapper/`.

## Build the Android APK

```sh
uv run flet build apk --split-per-abi
```

Always pass `--split-per-abi`. Without it, `flet build` leaves stale per-ABI APKs in `build/apk/`. If in doubt, delete
the whole `build/` folder first.

## Update the README screenshots

```sh
uv run python scripts/make_screenshots.py
```

It opens the app on a throwaway database seeded with demo events (`scripts/app_driver.py`, shared with the rendered
tests), walks the screens and saves them to
`docs/screenshots/`, plus an event share card. Your own data is never touched. Windows only (Flet's own page capture
returns nothing on desktop, so the script grabs the window with Pillow); keep the window uncovered while it runs.

## Refresh the bundled leaders

Installed apps fetch new sets themselves, so this only matters for fresh installs: run it before a release so they
start current. It rewrites `leaders.json`, including the set ids the app compares against to spot a new release, and
adds a portrait to `assets/leaders/` for every leader that lacks one (`--force` re-crops them all):

```sh
uv run python scripts/build_leaders.py
```

75 of the portraits are davyback.gg's hand-made leader icons, fetched once by
`uv run python scripts/fetch_davyback_portraits.py` (run it after `build_leaders.py`; the codes are listed in
`scripts/davyback_portraits.json` and `build_leaders.py --force` leaves them alone). davyback.gg's terms forbid
reusing its content without written permission; this is a known, accepted risk.

Every other portrait is cropped around the face position set for that card in `scripts/portrait_crops.json`
(`{"OP01-001": [cx, cy, side]}`, as fractions of the card width). Automatic face detection was tried and found only 6
of 138 faces in One Piece card art, so positions are set by eye. A card with two characters (ST22-001 Ace &
Newgate) takes a list of boxes instead, `[[cx, cy, side], [cx, cy, side]]`, and each face fills one vertical strip of
the portrait. Where the card image's semi-transparent "SAMPLE" watermark crosses a face, its letter boxes are listed in
`scripts/portrait_overlays.json` (`{"ST22-001": [[x0, y0, x1, y1], …]}`, same units) and lifted off before cropping;
the watermark sits in a different place on each card, so the boxes are measured per card. A new leader with no entry gets the default
upper-middle crop and the script warns about it. Add an entry and rerun with `--force`. Leaders an installed app
downloads on its own always get the default crop until the next release ships their bundled portraits.

## Tests

```sh
uv run pytest                 # unit, DB, migrations, UI widget-tree, property, regression tests
uv run pytest --cov           # the same, failing below 99% branch coverage (fail_under in pyproject.toml)
uv run pytest -m "live and not desktop"  # against the real optcgapi.com and davyback.gg (network, ~40 s)
uv run pytest -m desktop      # the real app, rendered (Windows; takes over the mouse and screen for ~2 min)
uv run pytest -m "desktop or live"       # both, including a real click on Update leaders in the real app
uv run ruff format src scripts tests && uv run ruff check src scripts tests
```

`scripts/ci.sh` runs what CI runs on every push to `main` and every pull or merge request, on GitHub
(`.github/workflows/ci.yml`), GitLab (`.gitlab-ci.yml`) and Codeberg (`.forgejo/workflows/ci.yml`, once Actions is
enabled in the repository settings): a locked `uv sync`, `ruff format --check`, `ruff check` and `pytest --cov`. The
`live` and `desktop` tests stay local.

The `live` tests check what mocks can't: that the card lists still parse and still hold every bundled leader and
set, that card images still download and crop, that a full sync fills a real database, that the davyback.gg icon
scraper still matches the site, and that Settings → Update leaders and the startup check work end to end, in the
widget tree and (with `desktop`) with a real click in the real window.

Every bug fix comes with a test marked `regression` that says what used to go wrong. The backup format is pinned by
`tests/backup/golden/`: the current shape is checked in (`v3.json`), so a change to it fails until `VERSION` is bumped,
and every older pinned file (`v1.json`, `v2.json`) must still restore. The share cards are pinned the same way, in the
default run: each is rendered from fixed data and compared with an approved image in `tests/share/golden/` (refreshed
with `TIMTAPPER_UPDATE_BASELINES=1`, like the rendered baselines below).

The `desktop` tests (`tests/rendered/`) start the real app on the demo data from `scripts/app_driver.py`, click it
with the real mouse and check the captured pixels: badges side by side, die pips, the picker's dots on one line at
360 dp, portrait frame bands, the theme swatches previewing their own colours, taps cycling the die, filtering the
picker and switching the theme. Captures are shrunk to dp and clicks scaled back up, so the checks pass at any
Windows display scaling. They also compare whole screens with saved baselines, including settings in Spanish at 360
dp, where the labels are longest: one set per scaling, since text renders differently at each
(`tests/rendered/baselines/` at 100%, `baselines/scale-125/` at 125%). After an intended visual change, rerun them with
`TIMTAPPER_UPDATE_BASELINES=1`, look at every rewritten baseline and commit it. Keep the window uncovered while they run.

## Project layout

```
src/timtapper/          Flet app root (flet build packages this folder)
  main.py               entry point: open DB, migrate, sync leaders, route
  catalog/              leader catalogue: optcgapi parser, bundled list, repository, portraits, daily sync
  events/               events and rounds: CRUD as plain dataclasses
  stats/                pure stat functions (records, splits, matchups)
  share/                Pillow share cards + share-sheet/save delivery
  backup/               JSON export/import
  db/                   SQLAlchemy models, Alembic migrations
  i18n/                 en/es/gl tables keyed by English source strings
  ui/                   screens (events, event, stats, settings), picker, widgets
  assets/               fonts, icon (png/ico), logo_mark, bundled leaders.json + leaders/*.webp portraits
scripts/                build_leaders.py, fetch_davyback_portraits.py, make_icon.py (icons, logo_mark +
                        docs/logo.png), make_screenshots.py (docs/screenshots/), app_driver.py + app_window.py
                        (run, capture and click the real app)
docs/                   logo.png wordmark and screenshots/ for the README
tests/                  mirrors src/timtapper; rendered/ drives the real app (marker `desktop`)
```

## Disclaimer

timtapper is a fan-made tool. It is not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. The leader
portraits in the app and on share cards are small crops of the official card art, which belongs to its owners.
The jester standing in for a bye's opponent is adapted from Microsoft's [Fluent Emoji](https://github.com/microsoft/fluentui-emoji)
"Joker" (MIT License, © Microsoft Corporation; the notice ships as `src/timtapper/assets/LICENSE-fluent-emoji.txt`).
`scripts/bye_jester.svg` is the source; `uv run python scripts/make_bye_joker.py` renders it to the app's PNG.

## License

This project is distributed under the [PayBack License (PBL)](LICENSE).
