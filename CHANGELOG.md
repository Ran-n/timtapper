[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.981408 )
[//]: # (+ Revised: 	2026/10/11 16:33:03.318533 )
[//]: # ( ---------------------------------------------------------------------- )

# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
