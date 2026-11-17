# SafePlay visual system

## Secondary pages

The secondary pages reuse the Dashboard's ticket panels and illustrations, with
scoped styles in `secondary.py`. The Dashboard and navigation are unchanged;
its before/after rendered screenshot was byte-identical during this pass.
Scenes uses compact cream headers, mint alternating rows, cyan selection,
category labels and explicit readiness labels. Native checkboxes, keyboard
selection, editing and manual creation remain functional. Full cell contents
are available in tooltips. Empty lists have an illustrated cue card.
Settings restores the cream connection panel (`#fff3d7`) and mint behavior panel
(`#e3f3f1`) from the retained Dashboard-era theme, with black numbered indicators
and consistent input focus states, while retaining
its single-view desktop layout. Activity uses selectable event entries with
bold titles, full timestamps, colored markers and subtle highlights. All event
text is HTML-escaped before display; no history is removed or rewritten.
The nine unslop passes preserve the established spacing, palette, typography,
copy, and SVG vocabulary; refinement concentrates on hierarchy, table details,
empty states and restrained native interaction feedback.

## Illustrated dashboard refinement

The subsequent polish pass preserves composition and colors, consolidates button
padding and tactile borders in the shared theme, and shortens helper text. Native
numeric inputs and dropdowns have explicit painted arrows with Qt's original
stepping, keyboard and hit-testing behavior. Activity refresh reads SQLite anew,
reports completion and preserves the current list if a read fails. The startup
label explicitly refers to SafePlay; invalid saved values default to a normal window.
Window mode now applies immediately on user selection and saves for future launches;
it does not save unrelated pending form edits. Activity has separate Refresh log
and Clear log actions. Refresh reads SQLite without deleting history; Clear requires
confirmation, then deletes stored activity rows and shows the illustrated empty
state with a zero count. New activity continues to be recorded after clearing.
Tests exercise clicks on numeric arrows, repeated refreshes after external database
writes, read-error recovery, saving startup mode and reopening in both modes.

The Dashboard uses a compact cinema ticket composition at its default 1180 × 800
logical-pixel window size. Its real controls fit without vertical or horizontal
scrolling; a regression test checks scrollbar ranges and every control's viewport bounds,
including a disconnected-player message and TV episode controls. Smaller windows
retain vertical scrolling to keep all controls accessible rather than clip them.

Inline SVGs depict a quirky projector, a guide search card, and filter sliders.
The projector combines irregular outlines, pastel reels, a coral star, a cross,
and a small dotted patch, tying decoration to the projection-booth theme.
Numbered ticket tabs, tactile button edges, a cyan playback surface, cream guide
surface, pink filter surface and individual colored filter strips establish hierarchy.
The main canvas stays warm white. A compact, clickable provider attribution
in the shared footer is visible on every tab, preserving the guide panels and
single-screen composition. Backend behavior is unchanged.

SafePlay is a native PySide6 desktop application. `gui.py` owns screen composition
and UI signals; `theme.py` owns presentation tokens and adaptive containers.
The provider, IPC, skip engine, data models and SQLite storage retain their existing
responsibilities. No browser interface or mobile app is introduced.

## Direction

- Product: parental scene filtering for mpv and Syncplay viewers
- Character: bold, precise, hands-on
- World: film editing desks and printed cue sheets
- Moments: playback time and explicit skip readiness
- Signature: numbered cue headings with monospaced timecodes

## Tokens

Dominant paper canvas `#faf9f6`, white panels `#ffffff`, ink `#20201e`, secondary ink `#595951`.
Mustard `#e8bd42` marks actions, cyan `#8cdee8` marks selected navigation,
and green `#a7d9ad` marks checked controls. Pink `#f4bfd0` and coral `#f27b69`
appear in small geometric playback illustrations. A pale pink `#fff0f3` filter
section is the occasional colored surface. Dotted patterns stay within the
112 × 64 header illustrations, never behind readable content. Yellow never
fills the main background. Two-pixel borders, square corners and five-pixel
black offset shadows with zero blur. Segoe UI for Windows text, Consolas for
timecodes and logs. Display headings use 40px bold text. Body text is 14px.
Spacing uses a four-pixel scale, with 12px within groups and 20–24px between groups.

Wide panels use a 3:2 split and stack below 820px of available panel width.
Dashboard and Settings fit within the default 1180 × 800 desktop viewport without
scrolling. In smaller windows, they can scroll vertically to keep every control
accessible. Scene tables scroll horizontally to keep complete interval data readable.
Minimum window size is 560 × 480.
Keyboard focus uses visible borders; hover changes surface color and pressing
a button inverts its colors. There is no looping animation.

## Audit and passes

The original interface had uniformly blue actions, little typographic hierarchy,
unstructured stacks, and unused screen space. The redesign groups related controls,
restricts the accent to actions and status, avoids decorative icons, clarifies
empty-state copy, establishes display/body/timecode typography, introduces adaptive
columns, and gives forms, tables and dialogs the same borders and interaction states.
Its visual content is real playback and guide state; no generated images or fake
media data ship with the app.

Rendered checks covered all four screens, the scene editor, a loaded scene table,
and a 600px-wide window. Regression checks cover settings, per-scene selection,
filter readiness and episode isolation. Live Syncplay playback was not exercised
as part of this visual redesign; existing IPC and engine tests remain the functional gate.

Design workflow informed by **unslop**, by [Damir Sokolovsky](https://x.com/heydamir),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The explicit Neo-Brutalist brief overrides the skill's default soft borders,
rounded corners and lighter heading weights.
