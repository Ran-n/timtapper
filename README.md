[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.910831 )
[//]: # (+ Revised: 	2026/10/12 01:04:16.696968 )
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

- **Events**: testing, locals, regional, national, online or other, each with a name, date, your leader and notes.
- **Rounds**: opponent's leader, result (W/L/D), turn order, die roll, top cut and notes, all edited in place, with no
  forms or dialogs. Log a round when you sit down and give it a result when the game ends; rounds still being played
  stay open.
- **One-tap round rows**: turn order, die roll and result show on every round row. Tap one to cycle its value.
- **Leader picker**: search by name, code or color, then narrow by color chips (a leader must have every color you
  select) and by set. The opponents you face most come first.

### Understand your results

- **Stats**: overall record and win rate, going 1st vs 2nd, won vs lost die roll, best and worst matchup (3+ games),
  recent form and a full matchup table. Filter by your leader and by event type.
- **Share images**: 1080×1350 PNG cards rendered on-device for an event, a matchup or your overall summary. On Android
  they open the system share sheet; on desktop you get a save dialog.

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

It opens the app on a throwaway database seeded with demo events, walks the screens and saves them to
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
of 138 faces in One Piece card art, so positions are set by eye. A new leader with no entry gets the default
upper-middle crop and the script warns about it. Add an entry and rerun with `--force`. Leaders an installed app
downloads on its own always get the default crop until the next release ships their bundled portraits.

## Tests

```sh
uv run pytest                 # unit, DB, UI widget-tree, property tests
uv run pytest -m live         # also hits the real optcgapi.com
uv run ruff format src scripts tests && uv run ruff check src scripts tests
```

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
                        docs/logo.png), make_screenshots.py (docs/screenshots/)
docs/                   logo.png wordmark and screenshots/ for the README
tests/                  mirrors src/timtapper
```

## Disclaimer

timtapper is a fan-made tool. It is not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. Share cards
draw no card art.

## License

This project is distributed under the [PayBack License (PBL)](LICENSE).
