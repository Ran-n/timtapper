[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/13 16:19:34.068656 )
[//]: # (+ Revised: 	2026/10/15 01:26:05.592309 )
[//]: # ( ---------------------------------------------------------------------- )

# Features in detail

What every screen does and why it behaves the way it does. The [README](../README.md) has the short version.

## Events

Every official One Piece TCG event type is available: Pirates Party, locals, release events, sealed, Heroines Battle,
team battles, Store Championship, Treasure Cup, Flagship Battle, Extra Grand Battle, regional, national and World
Championship, plus your own testing sessions and "other".

Each event has a name, date, your leader, notes, the set it was played in, where you finished and how many played.
Standings read the way players say them ("Top 4 · #3 of 32", "1st place", "Dropped"); testing sessions have none.

- **Search and filters**: search the list by name, or narrow it by your leader, event type and set. Filters stay set
  while you open an event and come back.
- **New events** are named after their type and count ("Local #4") and start in the set that was out on their date:
  the newest main booster by then, by English release date (extra boosters, starters and promo packs join the format
  before them). The name follows a type change until you rename it, and a new event you leave without changing
  anything is discarded.
- **Changing the date** moves the set with it, unless you picked the set yourself.

## Rounds

Each round is **Swiss**, **top cut** or a **bye** (no opponent, an automatic win, shown with a jester where a leader
would be).

- **Swiss** rows show die roll, turn order and result; tap any of them to cycle it. The die shows a green six when
  you won the roll, a red one when you lost it.
- **Top cut** is a **best of 3**: the row keeps its round number, shows the score and lists each game with its own
  turn order, result and who chose the turn order. That's filled in for you (the higher seed in game 1, then whoever
  lost the game before) and tappable for events that do it differently.
- Any round can switch between best of 1 and best of 3. A switch that would drop games holding a result or turn order
  (best of 3 to 1, or a played round to a bye) asks first.
- Results are W/L only: the OPTCG has no draws.
- Everything is edited in place, with no forms. Round notes show on the row. Rounds stay collapsed until you open one,
  and an open round stays open until you close it.

## Leader picker

Search by name, code or color, then narrow by color dots (a leader must have every color you select) and by set. The
opponents you face most come first. The list shows 60 at a time and says how many more a search would find.

## Stats

- Overall record and win rate (a best of 3 counts once; byes stay out), plus the games behind it.
- Splits per game: going 1st vs 2nd, won vs lost die roll, and who chose the turn order.
- Best and worst matchup (3+ matches; no worst when it would win as often as the best), recent form and a full
  matchup table.
- Filter by your leader (each shown with its portrait), event type and set.

## Share images

1080×1350 PNG cards rendered on-device for an event, a matchup or your overall summary, with the app's logo and each
leader's portrait framed in its colors.

- Stats narrowed to one leader carry that leader's portrait in the header.
- The event card puts your placement in a band of its own and shows each round's turn order, die roll and result.
- A long event name shrinks and wraps onto a second line rather than being cut.
- Android opens the system share sheet; desktop shows a save dialog.
- Rendered cards and exported backups left in the app's temp folder are deleted after a day.

## Look and language

- **Themes**: Gruvbox (default), Catppuccin, Dracula, Nord, Rosé Pine, Solarized, Tokyo Night and Classic, each with a
  light and a dark palette. Follow the system or force light or dark. Typeset in Poppins.
- **Languages**: English, Español, Galego.
- **Desktop**: the window opens phone-shaped (412 × 892), so the layout matches a phone; resize it freely down to
  360 × 640.

## Leader catalogue

138 leaders up to OP17 ship with the app, each with a small portrait cropped from its card art, so it works offline.

New sets arrive on their own. Once a day, at startup, the app asks [optcgapi.com](https://optcgapi.com) for its list
of sets (a few KB) and downloads leaders and portraits only when a new set is listed. Each set's English release date
comes from [Limitless TCG](https://onepiece.limitlesstcg.com/cards) (optcgapi.com has none) during that same update,
and is asked for again at each daily check while a main set still lacks one. Failures are logged and retried on the
next start. *Settings → Update leaders* forces a refresh.

Leaders downloaded this way get a default upper-middle crop until a release ships their hand-framed portraits (see
[DEVELOPMENT.md](DEVELOPMENT.md#leader-catalogue-and-portraits)).

## In the browser

The same app runs in any modern browser at [timtapper.breren.com](https://timtapper.breren.com/) (mirrors:
[ran-n.codeberg.page/timtapper](https://ran-n.codeberg.page/timtapper/),
[ran-n.gitlab.io/timtapper](https://ran-n.gitlab.io/timtapper/)), iPhones included. Nothing is sent anywhere:
the app's Python runs in the page itself.

- **Your data stays in that browser.** Events are saved to the browser's storage after every change and come back on
  the next visit. Clearing the site's data, or a private window, deletes them: export a backup now and then. If the
  browser refuses a save (its storage is full, say), the app tells you, so you can export a backup before leaving.
- **Sharing** opens the device's share sheet where the browser supports it, and downloads the image otherwise.
  Backups download the same way, and *Import backup* opens the browser's file picker.
- **New sets**: the daily check works as in the app, but Limitless TCG doesn't let other sites read its pages, so a
  new set's release date only arrives with the next release of timtapper.
- **Opens at once.** The page shows your events the moment it opens, as you left them: a copy the app saves after
  every change. You can look through it straight away — the tabs, each event and its rounds — while the app starts
  behind it (about a second; a few more on a first visit), then the app takes over on the screen you're on. Editing waits for the app: tapping a
  field or a button shows *Opening…* until it's ready, and *New event* opens the new event as soon as it is. A first
  visit shows the empty app the same way.
- **First visit** downloads about 19 MB (the app and Python); after that the browser keeps it, and a new version
  arrives in the background, taking over on a later visit.

## Backup

Export every event to a JSON file and restore it on any install. The format is versioned: every older backup still
restores.
