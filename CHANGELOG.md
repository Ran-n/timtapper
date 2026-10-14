[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.981408 )
[//]: # (+ Revised: 	2026/10/14 17:09:23.446800 )
[//]: # ( ---------------------------------------------------------------------- )

# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] — 2026-10-14

### Added

- Added an instant start to the web version: the page shows your events, each event's rounds and the Stats and Settings tabs the moment it opens, from a copy the app saves after every change, while the app starts behind it; edits wait for the app ("Opening…"), which takes over on the screen you're on, and *New event* opens the new event as soon as it's ready
- Added a GitLab Pages mirror of the web version at ran-n.gitlab.io/timtapper

### Changed

- Made the web version's first start download the app, Python and Flutter side by side instead of one after another: about 8 s instead of 15 on a fast line
- Dropped the Windows launchers from the web version's Python archive, so every visitor downloads 0.3 MB less

### Fixed

- Fixed the web version saving its whole database to the browser's storage after every read, not only after changes

## [1.3.1] — 2026-10-14

### Changed

- Moved the web version to timtapper.breren.com; ran-n.github.io/timtapper now redirects there, and the Codeberg mirror stays at ran-n.codeberg.page/timtapper
- Made the web version start faster: it no longer loads the image library before the first screen, and downloads about 0.5 MB less

## [1.3.0] — 2026-10-13

### Added

- Added a web version that runs in any browser, iPhones included, at ran-n.github.io/timtapper (mirror: ran-n.codeberg.page/timtapper): events are kept in the browser's storage, sharing opens the share sheet or downloads the image, and backups download and import through the browser
- Added a universal Android APK (every chip type in one file) to the release downloads, built with `scripts/build_android.py universal`
- Added an "Open in browser" button to the README
- Added the rendered UI tests on every platform the app ships to: the same flows and snapshot baselines now run on desktop (`-m desktop`), in a browser (`-m web`) and on an Android emulator (`-m android`), against driven builds made with `scripts/build_driven.py`
- Added `scripts/demo_driver.py` (the demo data and driver commands shared by every target), `scripts/driven_main.py` (the entry point of the driven web and Android builds) and `scripts/serve_site.py` (a local stand-in for the static hosts, with the channel the driven builds poll)
- Added platform checks for the desktop and Android builds, matching the web ones: events survive the app being killed, sharing reaches the system's share sheet or save dialog, and a backup restores through the system's own file picker (`scripts/android_phone.py` drives the emulator through adb, booting the generic `generic_phone_api34` AVD when none runs)
- Added a test that the database migrations build exactly the schema the models describe, so a model change without its migration fails before release
- Added a Windows installer (`timtapper-<version>-windows-x64-setup.exe`) next to the portable zip: it installs without an admin prompt, adds a Start-menu entry, an optional desktop shortcut and an uninstaller, and upgrades in place. `scripts/build_windows.py` builds both and leaves out the ~9 MB of debug Python modules flet bundles

### Changed

- Moved the win rate on the event share card up onto the leader code's line, so it no longer sits against the bottom of its box
- Moved the desktop snapshot baselines to `tests/rendered/baselines/desktop/`; web and Android have their own folders beside it
- Raised the test coverage gate to 100% branch coverage

### Fixed

- Fixed the leader picker's search hint being cut off on narrow screens (in English on 360 dp phones, in Spanish on any 360 dp screen): it now reads "Name, code or color", beside the search icon
- Fixed the app failing to start when `LOG_LEVEL` names no log level (e.g. `verbose`): it now warns and logs at INFO
- Fixed the web version losing changes without a word when the browser refuses to save them: it now says so and suggests exporting a backup
- Fixed an edit on the event screen that the database fails to write going unreported: it now says the change could not be saved
- Fixed a portrait download that fails mid-write (a full disk) leaving its half-written file in the app's storage
- Fixed restoring a backup looking each leader and set up again for every round and event: a large backup now restores in far fewer queries
- Fixed every start reading the bundled leader list twice
- Fixed Settings showing no brightness mode picked when the saved one isn't System, Light or Dark: it now falls back to System
- Fixed the browser tests (`-m web`) erroring when the rendered web tests ran before them: the whole run now shares one Playwright
- Fixed Android snapshot tests (`-m android`) failing by a few pixels after a display resize or a cold boot: every capture now re-reads the status and navigation bars it is cropped by
- Fixed two leader-update tests failing in `-m live` after the rendered web target: tests that use Playwright now run last, after every asyncio test

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
