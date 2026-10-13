[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.981408 )
[//]: # (+ Revised: 	2026/10/13 16:46:53.648476 )
[//]: # ( ---------------------------------------------------------------------- )

# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.1] — 2026-10-13

### Changed

- Shortened the README to a first read with a download button for the latest release; every feature in detail now lives in `docs/FEATURES.md`, and building, testing and the leader catalogue in `docs/DEVELOPMENT.md`
- Retook the README screenshots

### Removed

- Removed every portrait taken from another site: all 138 bundled portraits are now cropped from the card art by `scripts/build_leaders.py`

### Fixed

- Fixed the leader portraits that cut off, or missed, the leader's face: all 138 were checked by hand against the full card, each now frames the whole head, and the two-character cards ST12-001 and ST30-001 show both faces
- Fixed the "SAMPLE" watermark showing across the face in 32 portraits: it's now removed before cropping, recovered exactly where it's see-through and painted over from the surrounding art on the 4 cards where it's solid
- Fixed Settings showing 1.2.0 as the app version
- Fixed `scripts/build_android.py apk` rejecting every release APK as unsigned: APKs carry only v2/v3 signatures, which keytool can't read, so they're now checked with the Android SDK's apksigner
- Fixed the leader picker keeping its old order after a round's opponent was changed (or the round made a bye or played again): it lists your most-played opponents first, and now counts the change straight away
- Fixed a leader update stopping halfway when a card image was too large to open safely: that leader's portrait is now skipped and the rest still download

## [1.2.0] — 2026-10-13

### Added

- Added the Dracula (with its Alucard light palette) and Rosé Pine (Main and Dawn) themes
- Added `scripts/build_android.py`: a Google Play bundle or per-ABI APKs signed with the upload key (never the debug key), checked for its certificate and copied into `dist/` with the version in the name
- Added a privacy policy (PRIVACY.md) for the Google Play listing: nothing collected, public card data downloaded only

### Fixed

- Fixed the portraits of OP03-022, OP10-099 and ST13-001 to frame their faces
- Fixed a portrait download cut off mid-write counting as downloaded and never being fetched again
- Fixed a damaged downloaded portrait stopping every share card showing that leader from rendering
- Fixed saving a round's kind unchanged switching a best of 3 to that stage's usual best-of
- Fixed an unexpected error in the daily background set check escaping instead of being logged
- Fixed card codes with a trailing newline passing as card codes

### Security

- Fixed backup restore accepting any text as a leader or set code: a crafted file could point portrait lookups outside the portrait folders

## [1.1.0] — 2026-10-13

### Added

- Added each set's English release date, bundled and synced from Limitless TCG; a main set still missing one is asked for again at the daily check

### Changed

- Changed a new event's set from the newest set to the main set out on its date; changing the date moves the set with it unless it was picked by hand

## [1.0.0] — 2026-10-13

### Added

- Added Swiss, top cut and bye rounds: a bye has no opponent, counts as a win in the event standing and shows a jester where a leader would be
- Added best of 3 rounds holding each game's turn order, result and who chose the turn order (higher seed in game 1, then the previous game's loser, overridable); top cut defaults to best of 3 and any round switches between Bo1 and Bo3
- Added a confirmation before a Bo3→Bo1 or played→bye switch drops games holding a result or turn order
- Added the set an event was played in (newest by default) and a dropped flag; placement shows as a bracket ("Top 4 · #3 of 32", "1st place", "Dropped")
- Added a set filter to the events list and stats screen, and leader portraits in the stats leader filter
- Added a game record, per-game turn and die splits and a who-chose-the-turn split to stats; a best of 3 counts once in the match record and byes stay out of win rates and matchups
- Added the leader's portrait to the header of share cards for stats narrowed to one leader
- Added default event names from the type and count ("Local #4"), following a type change until renamed; a new event left unchanged is discarded
- Added a "60 of N leaders — search to find the rest" line when the leader picker's list is cut
- Added backup format version 3 (round kinds, best-of games, set, dropped); version 1 and 2 files still restore
- Added translated backup errors that name the event, round and game at fault
- Added CI on GitHub, GitLab and Codeberg running `scripts/ci.sh` (locked sync, format check, lint, tests with the coverage gate)
- Added golden-image tests for the share cards and rendered baselines for Spanish, Galician, empty, bye and Bo3 screens

### Changed

- Changed event types to Bandai's official tiers: Pirates Party, locals, release event, sealed, Heroines Battle, team battle, Store Championship, Treasure Cup, Flagship Battle, Extra Grand Battle, regional, national and World Championship, plus testing and other
- Changed rounds to stay collapsed unless opened, and an opened round to stay open until closed
- Changed the share card's event name to shrink and wrap onto a second line instead of being cut
- Changed the launcher icon to the bare mark centred in Android's adaptive-icon safe circle, without the name

### Removed

- Removed the "online" event type: stored online events and those in old backups become "other"

### Fixed

- Fixed rendered share cards and exported backups piling up in the temp folder: ones older than a day are deleted
- Fixed saving a share card or backup over an existing file on desktop keeping the old file's contents
- Fixed the database error screen showing in English whatever the chosen language
- Fixed a failed background leader update or backup restore going unreported; both now log and show the error
- Fixed the startup leader check crashing on a last-check time stored without a time zone
- Fixed a leader catalogue entry with a non-text name, colour or set breaking the whole sync
- Fixed a full or read-only portrait cache aborting the portrait download instead of skipping that portrait

## [0.5.2] — 2026-10-12

### Added

- Added a startup report under the "could not open its database" error: app, Python, SQLite, SQLAlchemy and Alembic versions, the database file with its tables and migration stamp, the bundled migration files and the log of the attempt, selectable so it can be copied off a phone

## [0.5.1] — 2026-10-12

### Fixed

- Fixed the Android app failing on first start with "no such table: color": the migrations ship compiled, and Alembic skipped them, so no tables were created

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
