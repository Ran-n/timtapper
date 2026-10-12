[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.981408 )
[//]: # (+ Revised: 	2026/10/12 17:26:41.159376 )
[//]: # ( ---------------------------------------------------------------------- )

# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] — 2026-10-12

### Added

- Added rendered UI tests (`uv run pytest -m desktop`, Windows) that drive the real app with real mouse clicks and check the captured pixels: split record badges, type pills, portrait frame bands, die pips, picker dots at 360 dp, tap-to-cycle and colour filtering
- Added whole-screen snapshot tests against approved baselines in `tests/rendered/baselines/`, refreshed with `TIMTAPPER_UPDATE_BASELINES=1`
- Added `scripts/app_driver.py` and `scripts/app_window.py`, which run, capture and click the real app on demo data; `make_screenshots.py` now uses them
- Added widget, portrait-crop and watermark-lift tests, including property-based ones, for the 0.4.0 changes
- Added where you finished and how many played to every ranked event, typed in place on the event screen and shown as "#3 of 32" on its tile; testing sessions have no standings
- Added a search field and a Filters panel (your leader, event type) to the events list, kept while you open an event and come back
- Added the app's logo, framed leader portraits, a placement band and each round's turn order, die roll and result to the share cards
- Added backup format version 2, which carries placement and players; version 1 files still restore
- Added a 99% branch-coverage gate (`uv run pytest --cov`), a `regression` test marker, a golden backup file and rendered baselines for 125% display scaling and Spanish settings at 360 dp

### Changed

- Changed round rows to fit on one line at 360 dp, with a smaller opponent portrait and short names for Donquixote Doflamingo and Eustass "Captain" Kid
- Changed leader names to wrap between words instead of being cut with an ellipsis
- Changed the stats screen's best and worst matchups to a row each, with the record beside the name

### Removed

- Removed draws: the OPTCG has none, so rounds are Win or Loss only; stored draws and draws in old backups become losses

### Fixed

- Fixed the event type dropdown clipping "Regional" to "Regiona" at 360 dp
- Fixed "Sistema" wrapping mid-word in the Spanish brightness selector at 360 dp
- Fixed leader names from optcgapi.com keeping a card-code suffix with no set number (e.g. "- P-001") or leading spaces

## [0.4.0] — 2026-10-12

### Added

- Added two-face portraits for cards with two characters: a list of boxes in `scripts/portrait_crops.json` gives each face its own vertical strip, used for ST22-001 Ace & Newgate
- Added `scripts/portrait_overlays.json`, which lists where the card image's "SAMPLE" watermark crosses a face so `build_leaders.py` lifts it off before cropping

### Changed

- Changed the die-roll badge on round rows to a green six-pip die when won and a red one-pip die when lost
- Changed records to show the win-loss record and the win rate as two separate badges on the events list and the stats screen
- Changed event tiles on the Events tab to show the event type as a badge with an icon at the top
- Changed the leader picker's colour filter to a single row of colour dots
- Changed leader portraits to have a border in the leader's colours

### Fixed

- Fixed the red Shanks (OP09-001) leader portrait showing only his hair
- Fixed the Belo Betty (OP05-002) leader portrait showing only one eye and her forehead
- Fixed the Ace & Newgate (ST22-001) leader portrait cutting off half of Ace's face and leaving out Newgate

## [0.3.1] — 2026-10-12

### Changed

- Changed the logo from a red card with a gold arc (Spain's flag colors) to a blue card with an orange arc, in the launcher icon, window icon, in-app mark and README wordmark

### Fixed

- Fixed the version shown in *Settings → About*, which still read 0.2.0 after the 0.3.0 release

## [0.3.0] — 2026-10-12

### Added

- Added color chips and a set dropdown to the leader picker: a leader must have every selected color, sets run newest first (OP, EB, ST, PRB), and filters reset each time the picker opens
- Added turn order and die roll to every round row next to the result; tapping any of the three cycles its value and saves it without expanding the row
- Added `scripts/make_screenshots.py`, which takes the README screenshots from the real app on a throwaway demo database (Windows only)
- Added screenshots of the events list, an event, the leader picker, stats, settings, the light theme and a share card to the README

### Changed

- Changed the event screen's delete button into a ⋮ menu holding "Delete event", so a destructive action is no longer one tap away
- Changed event tiles to give the event name its own line, with the record pill beside the leader name, so names are no longer cut short
- Changed the README into a fuller overview: grouped features, screenshots and a section on regenerating them

### Fixed

- Fixed the desktop window ignoring its phone shape and opening at 1280 × 720: the size is now applied before the saved preferences are read

## [0.2.0] — 2026-10-11

### Added

- Added automatic leader updates: once a day at startup the app checks optcgapi.com's set list in the background and downloads leaders and portraits only when a new set is listed, with a short notice when new leaders arrive; failures are logged and retried on the next start
- Added the set ids the bundled list was built from to `leaders.json` (`"sources"`), written by `scripts/build_leaders.py`
- Added a small portrait next to every leader (events list, picker, event, rounds, stats), a 160 px face crop from the card art (sharp at 56 dp on 3× screens); the 138 bundled leaders ship theirs, and *Update leaders* downloads portraits for new ones
- Added `scripts/fetch_davyback_portraits.py`, which swaps in davyback.gg's leader icons for the 75 leaders it covers; `build_leaders.py` no longer re-crops those
- Added `--force` to `scripts/build_leaders.py`, which now also writes the bundled portraits, each cropped around the face set for that card in `scripts/portrait_crops.json` so every portrait shows the leader's face
- Added the app logo: a red card mid-tap with a rising bar chart over the name "timtapper", its "app" highlighted in gold, as the launcher icon; the bare mark shows in the events app bar, on the empty events screen, in *Settings → About* and as the Windows window icon, and the README carries it as a wordmark (`docs/logo.png`); `scripts/make_icon.py` draws them all

### Changed

- Changed the desktop window to open phone-shaped (412 × 892, centred, no smaller than 360 × 640), so the mobile layout looks the same as on a phone
- Changed *Update leaders* and the background check to share one update path, so they can never run at the same time

## [0.1.0] — 2026-10-11

### Added

- Added events (testing, locals, regional, national, online, other) with name, date, own leader and notes, all edited in place
- Added round logging per event: opponent leader, W/L/D result, turn order, die roll, top cut and notes; rounds without a result stay open and don't count in stats
- Added stats screen with overall record, win rate, 1st/2nd and die-roll splits, best/worst matchup (3+ games), recent form and a per-leader matchup table, filterable by own leader and event type
- Added shareable 1080×1350 PNG cards (event result, matchups, overall summary) rendered on-device with Pillow and handed to the share sheet, with a save-dialog fallback on desktop
- Added a bundled catalogue of 138 leaders (up to OP17) and an in-app "Update leaders" action backed by optcgapi.com
- Added JSON backup export and validated, all-or-nothing import
- Added English, Spanish and Galician translations, and system/light/dark themes
- Added a local SQLite database with Alembic migrations applied on every start
- Added `scripts/build_leaders.py` to refresh the bundled leader list and `scripts/make_icon.py` to draw the app icon
