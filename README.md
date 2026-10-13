[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 15:48:36.910831 )
[//]: # (+ Revised: 	2026/10/13 22:03:51.502334 )
[//]: # ( ---------------------------------------------------------------------- )

# timtapper

<p align="center"><img src="docs/logo.png" alt="timtapper" width="420"></p>

<p align="center">
  <b>Match tracker for the One Piece Trading Card Game.</b><br>
  Log every round, see your matchups, share your results. Android, Windows and the browser, fully offline.
</p>

<p align="center">
  <img src="docs/screenshots/events.png" alt="Events list" width="200">
  <img src="docs/screenshots/event.png" alt="An event and its rounds" width="200">
  <img src="docs/screenshots/stats.png" alt="Stats" width="200">
  <img src="docs/screenshots/picker.png" alt="Leader picker with color and set filters" width="200">
</p>

<p align="center">
  <a href="https://github.com/Ran-n/timtapper/releases/latest"><img src="https://img.shields.io/badge/Download-Android%20APK%20%C2%B7%20Windows-ea6c1a?style=for-the-badge&logo=github" alt="Download the latest release" height="40"></a>
  <a href="https://ran-n.github.io/timtapper/"><img src="https://img.shields.io/badge/Open%20in%20browser-iPhone%20%C2%B7%20any%20device-2185d0?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Open timtapper in your browser" height="40"></a>
</p>

<p align="center"><sub>
  Mirrors:
  <a href="https://codeberg.org/ran-n/timtapper/releases/latest"><img src="https://img.shields.io/badge/Codeberg-2185D0?logo=codeberg&logoColor=white" alt="Codeberg" align="center"></a>
  <a href="https://gitlab.com/Ran-n/timtapper/-/releases/permalink/latest"><img src="https://img.shields.io/badge/GitLab-FC6D26?logo=gitlab&logoColor=white" alt="GitLab" align="center"></a>
  · browser:
  <a href="https://ran-n.codeberg.page/timtapper/"><img src="https://img.shields.io/badge/Codeberg%20Pages-2185D0?logo=codeberg&logoColor=white" alt="timtapper on Codeberg Pages" align="center"></a>
</sub></p>

No accounts, no server, no sync: your events live on your device, and a JSON backup moves them to another install.
In the browser they stay in that browser's storage; export a backup now and then.

## Features

- **Every event type**: locals, Store Championships, Treasure Cups, regionals and the rest of the official calendar,
  plus testing sessions. Track your leader, set and final standing ("Top 4 · #3 of 32").
- **Fast round logging**: Swiss, best-of-3 top cut and byes. Tap the die roll, turn order or result to cycle it; no
  forms.
- **Stats that matter**: win rate, going 1st vs 2nd, die roll, best and worst matchups and a full matchup table,
  filtered by leader, event type and set.
- **Share cards**: event, matchup and summary images ready for the share sheet.
- **Always-current leaders**: 138 leaders up to OP17 bundled with portraits; new sets download on their own.
- **Themes and languages**: 8 themes (Gruvbox, Catppuccin, Dracula, Nord, Rosé Pine…) in light and dark; English,
  Español, Galego.

<p align="center">
  <img src="docs/screenshots/share-card.png" alt="Event share card" width="280">
  <img src="docs/screenshots/settings.png" alt="Settings in the light Gruvbox theme" width="200">
  <img src="docs/screenshots/events-light.png" alt="Events list in the light Gruvbox theme" width="200">
</p>

Every feature in detail: [docs/FEATURES.md](docs/FEATURES.md).

## Quick start

Requires Python ≥ 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run flet run
```

Android builds, tests, screenshots and the leader catalogue: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Privacy

timtapper collects nothing: your data stays on your device, and the app only downloads public card data. See
[PRIVACY.md](PRIVACY.md).

## Disclaimer

timtapper is a fan-made tool, not affiliated with or endorsed by Bandai, Eiichiro Oda or Shueisha. Leader portraits
are small crops of the official card art, which belongs to its owners. The bye jester is adapted from Microsoft's
[Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT).

## License

[PayBack License (PBL)](LICENSE). Contributions welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).
