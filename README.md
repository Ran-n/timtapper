[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.910831 )
[//]: # (+ Revised: 	2026/10/11 16:32:59.406519 )
[//]: # ( ---------------------------------------------------------------------- )

# timtapper

Local-first match tracker for the **One Piece Trading Card Game**, built with Flet for Android and desktop. Log your
testing sessions, locals and majors round by round, see your matchup stats, and share them as images. There are no
accounts, no server and no sync: everything stays on your device.

## Features

- **Events**: testing, locals, regional, national, online or other. Each event has a name, date, your leader and notes.
- **Rounds**: opponent's leader, result (W/L/D), turn order, die roll, top cut and notes, all edited in place. A round
  can be logged as soon as you sit down and given its result when the game ends.
- **Stats**: overall record and win rate, going 1st vs 2nd, won vs lost die roll, best and worst matchup (3+ games),
  recent form, and a full matchup table. Filter by your leader and by event type.
- **Share images** (1080×1350 PNG, rendered on-device): event result card, matchup card and overall summary card. On
  Android they open the system share sheet; on desktop you get a save dialog.
- **Leader catalogue**: 138 leaders up to OP17 are bundled, so the app works offline. *Settings → Update leaders* pulls
  new sets from [optcgapi.com](https://optcgapi.com).
- **Backup**: export every event to a JSON file and restore it on any install.
- **Languages**: English, Español, Galego. **Themes**: system, light, dark.

## Stack

| Layer      | Technology                                                       |
|------------|------------------------------------------------------------------|
| UI         | Flet 1.0 (Android APK + desktop)                                 |
| Storage    | SQLite via SQLAlchemy 2.0, schema migrated by Alembic on startup |
| Images     | Pillow, with the Poppins font bundled (OFL)                      |
| Leaders    | Bundled JSON + optcgapi.com (httpx)                              |
| Tooling    | uv, ruff, pytest (+ hypothesis, respx)                           |

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

## Refresh the bundled leaders

Run this before a release when a new set is out:

```sh
uv run python scripts/build_leaders.py
```

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
  catalog/              leader catalogue: optcgapi parser, bundled list, repository
  events/               events and rounds: CRUD as plain dataclasses
  stats/                pure stat functions (records, splits, matchups)
  share/                Pillow share cards + share-sheet/save delivery
  backup/               JSON export/import
  db/                   SQLAlchemy models, Alembic migrations
  i18n/                 en/es/gl tables keyed by English source strings
  ui/                   screens (events, event, stats, settings), picker, widgets
  assets/               fonts, icon, bundled leaders.json
scripts/                build_leaders.py, make_icon.py
tests/                  mirrors src/timtapper
```

## Disclaimer

timtapper is a fan-made tool. It is not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. Share cards
draw no card art.

## License

This project is distributed under the [PayBack License (PBL)](LICENSE).
