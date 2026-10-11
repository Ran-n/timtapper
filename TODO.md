[//]: # ( ---------------------------------------------------------------------- )
[//]: # (+ Authors: 	Ran# <ran.hash@proton.me> )
[//]: # (+ Created: 	2026/10/11 17:36:52.145973 )
[//]: # (+ Revised: 	2026/10/11 17:36:52.252451 )
[//]: # ( ---------------------------------------------------------------------- )

# TODO

The backlog. Each item is self-contained: reading it alone is enough to
implement it fully, without asking anything. Work top to bottom unless an item
says otherwise.

Next item number: 4

## Adding an item

- Write for someone who has never seen the conversation: what happens today,
  what should happen instead, and why each non-obvious decision was made.
- Be concrete: real file paths, names, sizes, colours, keys. No open "maybe";
  if the implementer must choose, say how to choose and how to check.
- Use the template below. Implementation is a numbered list of steps in the
  order to do them; Done when is a checklist.
- Number it with "Next item number" above, then increase that number. Numbers
  are IDs: never reused or renumbered.
- File order is priority: the first item is the next one to do.
- Screenshots go in `docs/todo/<n>-<slug>.png`, linked from the item.
- Split anything bigger than one sitting into items that ship alone.

## Implementing an item

1. Read the whole item and every file it names; check `git status` first.
2. If the code has drifted from the item, adapt and note it; if the item
   contradicts a newer decision, ask before building.
3. Do the Implementation steps in order.
4. Write the listed tests, plus any others the change needs.
5. Lint, format, update file headers and run the full test suite until clean.
6. For visible changes, run the app and check it in the states the item names.
7. Update the listed docs; write the changelog line when committing.
8. Tick every Done when line, with evidence.
9. Delete the item and its screenshots; add follow-up work as new items.

## Template

```markdown
## <n>. <short imperative title>

**Why:** what happens today and what is wrong with it.
**Goal:** the result, as the user will see it.

### Behaviour
- One bullet per case, edge cases included.

### Out of scope
- What this item deliberately doesn't change.

### Implementation
1. `<path>`: what changes and why.

### Tests
- `<test file>`: each case and what it proves.

### Docs
- `<doc file>`: what to change. Changelog: "<line>".

### Done when
- [ ] Checkable result.
```

---

## 1. Filter the leader picker by color and by set

**Why:** the leader picker (`src/timtapper/ui/leader_picker.py`, a bottom sheet
opened for "Your leader", "Opponent's leader" and "Add round") has only a text
field ("Search name, code or color") over a list of up to `MAX_RESULTS = 60`
leaders. With 138+ leaders, finding "that purple-yellow one from OP09" means
guessing a name or typing color words; there is no way to browse by color or
by set.

**Goal:** under the search field, the sheet shows a row of six color chips
(Red, Green, Blue, Purple, Black, Yellow) and a set dropdown ("All sets",
then every set code). Tapping chips and picking a set narrows the list
instantly, combined with whatever is typed.

### Behaviour
- Color chips are multi-select toggles, all off when the sheet opens. A
  leader passes when it has **every** selected color (Red + Green shows only
  Red/Green dual-color leaders). AND, not OR, because the point is narrowing:
  OR would make each extra chip show more leaders, not fewer.
- Each chip shows a small dot filled with `CARD_COLORS[color]`
  (`src/timtapper/ui/theme.py`) next to the translated color name; a selected
  chip uses the Flet `Chip` selected state (filled background, checkmark).
- The set dropdown lists "All sets" (key `""`, the default) followed by every
  distinct `Leader.set_code` present in `ctx.leaders`, sorted by prefix
  (`OP`, `EB`, `ST`, `PRB`, then any other prefix alphabetically) and then by
  number descending within a prefix, so the newest main set (`OP17`) is first.
  Leaders whose `set_code` is `None` (placeholders from restored backups)
  appear only under "All sets".
- Text search, colors and set combine with AND. Search order (most-played
  first, from `LeaderRepository.all()`) is kept.
- When nothing matches, the existing "No leader matches" text shows.
- Filters reset every time the sheet opens (not remembered): the sheet is
  opened for different purposes (own leader vs opponent) and a stale filter
  would hide the leader the user is looking for.
- The list must stay usable at phone width (360 px): the chip row wraps
  (`ft.Row(wrap=True)`), it never scrolls sideways.

### Out of scope
- Filtering on the Stats screen.
- Showing set names (only `set_code` is on the `Leader` value; adding
  `set_name` would touch `to_leader` and every caller).

### Implementation
1. `src/timtapper/catalog/repository.py`: add a pure function
   `filter_leaders(leaders, query, colors: frozenset[str] = frozenset(), set_code: str | None = None) -> list[Leader]`
   that applies `search(leaders, query)` and then the color (subset test:
   `colors <= set(leader.colors)`) and set filters. Keep `search` as is: it is
   called by tests and the text-only behaviour must not change.
2. Same file: add `set_codes(leaders) -> list[str]` returning the sorted
   distinct codes per the ordering rule above (parse with
   `re.fullmatch(r"([A-Z]+)(\d+)", code)`; codes that don't match go last,
   alphabetically).
3. `src/timtapper/ui/leader_picker.py`: keep the picker state (`query`,
   `colors: set[str]`, `set_code`) in the closure of `build_picker`; make
   `render()` read all three and call `filter_leaders`. Add the chip row
   (`data="color-filters"`, each chip `data=f"color-{name}"`) and the set
   `ft.Dropdown` (`data="set-filter"`, dense, `label=_("Set")`) between the
   search field and the results. Use `COLORS` from `db.models` for chip order.
   Log at DEBUG (`_log = get_logger("ui.picker")`) the filter state on each
   change — no `print()`.
4. Same file: the picker sheet height (560) will need ~90 px more for the
   filters; raise it to 640 and check on a 360×740 window that the results list
   still shows at least 5 rows.
5. `tests/ui/uitools.py`: `pick_leader` unpacks
   `_title, field, results = sheet.content.content.controls`; that breaks once
   the column has more children. Change it to find the field and list with
   `by_data` (give the field `data="leader-search"` and the list
   `data="leader-results"` in step 3). Every UI test that adds a round or
   changes a leader goes through this helper.
6. `src/timtapper/i18n/translations.py`: add `"Set"`, `"All sets"` and the six
   color names (`"Red"`, `"Green"`, `"Blue"`, `"Purple"`, `"Black"`,
   `"Yellow"`) to `ES` and `GL` (EN is derived from ES). ES: Rojo, Verde, Azul,
   Morado, Negro, Amarillo, "Set", "Todos los sets". GL: Vermello, Verde, Azul,
   Morado, Negro, Amarelo, "Set", "Todos os sets". `tests/test_i18n.py` fails
   on any missing key.
7. Run `ruff format` then `ruff check` (no `--fix`) on every edited `.py`,
   and `metadata -m` on every edited file.

### Tests
- `tests/catalog/test_catalog_repository.py`:
  - `test_filter_by_one_color`: only leaders containing that color.
  - `test_filter_by_two_colors_is_and`: Red+Green returns only leaders with both.
  - `test_filter_by_set`: only that `set_code`; `None` set never matches a code.
  - `test_filter_combines_query_colors_and_set`.
  - `test_filter_with_nothing_selected_equals_search`.
  - `test_set_codes_order`: `["OP17", "OP01", "EB04", "ST30", "PRB01", "XYZ"]`
    style input comes out OP desc, EB desc, ST desc, PRB, then unparsable.
- `tests/ui/test_leader_picker.py` (new):
  - `test_color_chip_narrows_list` and `test_unselecting_chip_restores_list`.
  - `test_set_dropdown_narrows_list`.
  - `test_filters_and_text_combine`.
  - `test_no_match_shows_message`.
  - `test_filters_reset_on_reopen`.
  - `test_pick_still_calls_on_pick` (with a filter active).
- Existing `tests/ui/test_event_view.py` round/leader tests must pass
  unchanged through the updated `pick_leader`.

### Docs
- `README.md` → Features → **Rounds** / **Leader catalogue**: add "the leader
  picker filters by color and by set". Changelog: "[A] leader picker: filter by
  color (all selected colors) and by set".

### Done when
- [ ] Six color chips and a set dropdown show under the picker search field.
- [ ] Red+Green shows only Red/Green leaders; picking `OP09` shows only OP09.
- [ ] Filters reset when the sheet is reopened.
- [ ] Layout checked at 360 px wide, light and dark theme.
- [ ] New strings in ES and GL; `tests/test_i18n.py` passes.
- [ ] Full test suite, `ruff format`, `ruff check` clean; headers updated.

## 2. Show turn order and die roll on round rows, tap to cycle values

**Why:** on the event screen (`src/timtapper/ui/event_view.py`,
`EventScreen._round_tile`) each round is an `ft.ExpansionTile` whose
collapsed row shows only the round label (`R1`/`TC`), the opponent leader and
the result badge (`result_badge` in `src/timtapper/ui/widgets.py`: a coloured
`W`/`L`/`D` square, `…` when pending). Turn order ("Went 1st/2nd") and die
roll ("Won/Lost die roll") are invisible until the tile is expanded, and
changing any of the three means expanding the tile and using a small
`SegmentedButton`. The user wants to see all three at a glance and change
them with a tap on the row itself.

**Goal:** every collapsed round row shows three compact, tappable indicators
on the right: turn order, die roll and the result badge. Each tap advances
that value to the next possibility and saves it immediately, without
expanding the tile.

### Behaviour
- Result badge cycles `…` (None) → `W` → `L` → `D` → `…`.
- Turn indicator shows `1st` / `2nd` / `—` (muted when unknown) and cycles
  — → 1st → 2nd → —.
- Die indicator shows an `ft.Icons.CASINO` icon followed by a check
  (`ft.Icons.CHECK`, `scheme.success`) when won, a cross (`ft.Icons.CLOSE`,
  `scheme.error`) when lost, or the bare muted icon when unknown. Shape plus
  colour, never colour alone, so it reads for colour-blind users. Cycles
  unknown → won → lost → unknown.
- Each tap saves through `_save_round` (so repository validation and the
  "Could not save" snackbar on `EventError` still apply) and refreshes the
  screen.
- Tapping an indicator must **not** toggle the tile's expansion. Tapping
  anywhere else on the row still expands/collapses it.
- Cycling the result from the row does not change the expanded state (unlike
  the segmented button, which collapses the tile once a result is set — keep
  that behaviour for the segmented button).
- The segmented buttons inside the expanded tile stay as they are: they are
  the explicit way to set a value without cycling through others.
- Each indicator has a tooltip: "Result — tap to change", "Turn order — tap
  to change", "Die roll — tap to change".
- Each indicator is at least 40×36 px (touch target), and the opponent name
  ellipsizes (`leader_row` already does) so the row fits at 360 px wide.

### Out of scope
- Long-press or swipe gestures.
- Changing the share card or stats.

### Implementation
1. `src/timtapper/ui/event_view.py`: add a module-level helper
   `_next(value, cycle: tuple)` returning the element after `value` in
   `cycle` (wrapping). Cycles: `RESULT_CYCLE = (None, "W", "L", "D")` (use
   `RESULTS` from `db.models` to build it), `TRISTATE_CYCLE = (None, True, False)`.
   One helper for all three (DRY).
2. `src/timtapper/ui/widgets.py`: add `turn_badge(went_first, scheme)` and
   `die_badge(won_die_roll, scheme)` next to `result_badge`, same height (36)
   and radius so the three line up.
3. `src/timtapper/ui/event_view.py` `_round_tile`: replace
   `trailing=result_badge(...)` with an `ft.Row(spacing=6, tight=True)` of
   three `ft.Container`s wrapping turn, die and result badges, each with
   `on_click`, `ink=True`, a tooltip, and `data="turn-cycle"`,
   `"die-cycle"`, `"result-cycle"`. Their handlers call
   `self._save_round(r.id, <field>=_next(current, cycle))`.
4. Verify in the running app that a tap on a trailing container does not
   also toggle the `ExpansionTile`. If it does, move the three indicators out
   of `trailing` into the `title` row (after `leader_row`) wrapped in an
   `ft.GestureDetector(on_tap=...)`, and check again. Record which one
   worked in the code comment above the row.
5. `src/timtapper/i18n/translations.py`: `"1st"` and `"2nd"` already exist
   (share cards) — reuse them. Add `"Result — tap to change"`, `"Turn order — tap to change"`,
   `"Die roll — tap to change"` to `ES` ("Resultado — toca para
   cambiar", "Orden de turno — toca para cambiar", "Dado — toca para
   cambiar") and `GL` ("Resultado — toca para cambiar", "Orde de
   quenda — toca para cambiar", "Dado — toca para cambiar").
6. Log each cycle at INFO via the existing `_log` (`"round %d: %s -> %s"`).
7. `ruff format`, `ruff check` (no `--fix`), `metadata -m` on every edited
   file.

### Tests
- `tests/ui/test_event_view.py`:
  - `test_result_cycles_through_all_values`: four taps on `result-cycle` of
    `round-4` (pending) give W, L, D, None in the DB.
  - `test_turn_cycles`: None → True → False → None.
  - `test_die_cycles`: None → True → False → None.
  - `test_cycling_keeps_expansion_state`: an expanded tile stays expanded
    and a collapsed one stays collapsed after a result tap.
  - `test_cycle_rejected_edit_shows_error`: monkeypatch
    `ctx.events.update_round` to raise `EventError`; the error snackbar
    appears and nothing crashes.
  - `test_collapsed_row_shows_turn_and_die`: `texts(tile)` includes `1st`
    for a round with `went_first=True`.
- `tests/ui/test_widgets.py`: `turn_badge` and `die_badge` render each of
  the three states (text/icon present, colours as specified).
- Existing segmented-button tests stay green.

### Docs
- `README.md` → Features → **Rounds**: "turn order, die roll and result show
  on each round row; tap one to cycle its value". Changelog: "[A] round rows
  show turn order and die roll; tap result/turn/die to cycle values".

### Done when
- [ ] Collapsed rows show turn, die and result side by side.
- [ ] Each tap advances and saves the value; the tile doesn't expand or
      collapse.
- [ ] Checked at 360 px wide, light and dark theme, with a long leader name.
- [ ] New strings in ES and GL; `tests/test_i18n.py` passes.
- [ ] Full test suite, `ruff format`, `ruff check` clean; headers updated.

## 3. Move "Delete event" into an overflow menu

**Why:** on the event screen the app bar
(`src/timtapper/ui/app.py`, `build_view`, the `/event/` branch) has a bare
trash `ft.IconButton(ft.Icons.DELETE_OUTLINE, data="delete-event")` always
visible top-right, one tap from a destructive action. It is too prominent for
something done rarely.

**Goal:** the app bar shows a `⋮` (`ft.Icons.MORE_VERT`) menu instead; the
menu contains "Delete event" (trash icon, error colour). Choosing it opens the
same confirmation dialog as today.

### Behaviour
- Tap `⋮` → menu with one item, "Delete event". Tap it → existing
  `EventScreen.delete_event()` confirmation ("Delete this event?") → Delete
  removes the event and returns to `/events`; Cancel keeps it.
- Dismissing the menu without choosing does nothing.
- The menu is a `PopupMenuButton` so later event actions (duplicate,
  share…) have a home.

### Out of scope
- Deleting rounds (stays inside the expanded round tile).
- Changing the confirmation dialog.

### Implementation
1. `src/timtapper/ui/app.py`: replace the `ft.IconButton` in the event
   `AppBar.actions` with
   `ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, tooltip=_("More options"), data="event-menu", items=[ft.PopupMenuItem(content=ft.Text(_("Delete event"), color=ft.Colors.ERROR), icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _e: screen.delete_event(), data="delete-event")])`.
   Keep `data="delete-event"` on the item so tests can still find it.
2. `src/timtapper/i18n/translations.py`: add `"More options"` to `ES`
   ("Más opciones") and `GL` ("Máis opcións").
3. `ruff format`, `ruff check` (no `--fix`), `metadata -m` on edited files.

### Tests
- `tests/ui/test_app_context.py` line 35 asserts
  `view.appbar.actions[0].data == "delete-event"`; change it to assert the
  action is a `PopupMenuButton` with `data == "event-menu"` whose single item
  has `data == "delete-event"`.
- Add `test_event_menu_delete_confirms_and_deletes`: fire the item's
  `on_click`, confirm the dialog, assert the event is gone.
- Add `test_event_menu_delete_cancel_keeps_event`.

### Docs
- No README change (the feature list doesn't mention the button).
  Changelog: "[R] event screen: delete moved into the ⋮ menu".

### Done when
- [ ] No trash icon in the event app bar; `⋮` menu shows "Delete event".
- [ ] Delete still asks for confirmation and works; Cancel keeps the event.
- [ ] New string in ES and GL; full test suite, ruff clean; headers updated.
