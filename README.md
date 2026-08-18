# Card games

Two Italian card games against the computer, in one Tkinter window: **Briscola**
and **Burraco**. Every card is drawn by the code, so there are no image assets
to install, and the whole window lives on a single Canvas.

![The opening menu](docs/menu.png)

## Contents

- [Install and run](#install-and-run)
- [The menu](#the-menu)
- [Briscola](#briscola)
- [Burraco](#burraco)
- [The cards](#the-cards)
- [Match records](#match-records)
- [Pacing and performance](#pacing-and-performance)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Screenshots](#screenshots)
- [Ideas for later](#ideas-for-later)

## Install and run

The project runs in its own conda environment named `briscola`, not in the base
environment:

```bash
conda env create -f environment.yml
```

Then:

```bash
conda run -n briscola python main.py
```

Nothing outside the standard library is required — only Python 3.10+ (for the
`X | None` type syntax) and Tk, both provided by the environment file.

## The menu

The app opens on a menu. Pick the game, pick the player the results are filed
under, pick the difficulty, and start. `Statistics` and `Rules` are reachable
from here too, and the `menu` link at the top of the side panel brings you back
during a game — an abandoned game is not recorded.

| Action | How |
| --- | --- |
| Start | `Start game`, or Enter |
| Change game | The two pills under `GAME`, or the menu |
| Change difficulty | The pills under `DIFFICULTY`, or `D` |
| Statistics | `Statistics`, or `S` |
| Rules | `Rules`, or `R` |
| Change player name | The `change` link in the player box |

## Briscola

![The Briscola table](docs/table.png)

Trick taking with 40 cards: 20 tricks, 120 points in total, **61 points win**,
and 60–60 is a draw. Full rules: [Wikipedia](https://en.wikipedia.org/wiki/Briscola).

- Point values: Ace 11, Three 10, King 4, Queen 3, Jack 2, everything else 0.
- Strength within a suit: `A > 3 > K > Q > J > 7 > 6 > 5 > 4 > 2`.
- **Following suit is not required.** The responder only wins by playing a
  stronger card of the same suit, or a trump against a non-trump lead;
  otherwise the trick goes to the player who led.
- The trick winner draws first, then the opponent, and leads the next trick.
  The face-up trump card sits at the bottom of the stock, so it is drawn last.

| Action | How |
| --- | --- |
| Play a card | Click it, or press `1`, `2`, `3` |
| Carry on through a pause | Click anywhere, or press space |
| New game | `New game`, or `N` — the opening lead alternates each game |

### Difficulty

| Level | How it plays |
| --- | --- |
| **Easy** | Mostly random, but it will take an obviously valuable trick. |
| **Normal** | Classic heuristics: lead your cheapest card, duck small tricks, spend a trump only when the trick pays for it. |
| **Expert** | Counts cards and searches. Hard to beat. |

The Expert level works on two fronts. It tracks every card it has seen, so as
soon as nothing unknown is left to draw it can deduce the opponent's hand
exactly, and from there it solves the remaining tricks by exhaustive minimax —
if it can still reach 61, it will. Before that it deals the unseen cards into
many plausible opponent hands, plays every candidate card out in each of those
worlds, and keeps the card that wins the most of them (perfect information
Monte Carlo, the standard strong approach for trick-taking games).

Measured over the same deals played from both seats, so neither side gets the
better cards:

| Match-up | Score share of the stronger level | Games |
| --- | --- | --- |
| Normal vs Easy | 58% | 160 |
| Expert vs Normal | **76%** | 96 |
| Expert vs Easy | **83%** | 96 |

## Burraco

![The Burraco table](docs/burraco.png)

Melds, wild cards and the pot, with two 54-card decks — 108 cards. Full rules:
[Wikipedia](https://en.wikipedia.org/wiki/Buraco).

Both players get eleven cards, two pots (*pozzetti*) of eleven are set aside,
and the rest is the stock. On your turn you draw — one card from the stock, or
the whole discard pile — then lay down or extend as many melds as you like, and
finish by discarding one card.

- **Melds** are sets of the same rank, or runs in one suit, of at least three
  cards. An ace runs either below the two or above the king.
- **Wild cards** (*pinelle*) are the jokers and the twos, one per meld at most.
  A two of the run's own suit can serve as itself instead.
- A meld of seven cards or more is a **burraco**: 200 points clean, 100 with a
  wild card in it.
- Running out of cards the first time earns you the pot. After that, running
  out **closes** the hand — which needs a burraco, so any other move that would
  empty your hand is refused.
- Card points: joker 30, two 20, ace 15, K/Q/J/10/9/8 10, 7 down to 3 five.
  Melded cards count for you, cards left in hand count against you, closing is
  worth 100, and never taking your pot costs 100.

| Action | How |
| --- | --- |
| Pick cards | Click them; click again to put one back |
| Draw / take the pile | The two buttons at the top of the panel |
| Lay down a meld | Pick the cards, then `Lay down` |
| Add to a meld | Pick the cards, then click the meld itself |
| Take a pinella back | Pick the card it stands for, then `Take the pinella` |
| Discard | Pick one card, then `Discard` |
| Sort your hand | `Sort by suit` or `Sort by rank` |

The hand is put back in the chosen order after every draw, every pile taken and
every meld laid down, and wild cards sort to the end where they are easy to
find and hard to discard by accident.

A Burraco hand grows: eleven cards, plus a pot of eleven, plus whatever a
taken discard pile adds. The fan tightens as it fills so that it always fits
the table — at a fixed spacing, seventeen cards already spanned 1010 pixels of
a 940 pixel table and the ones on the ends could be neither seen nor clicked.
Past twenty-eight cards, tightening alone is not enough and the hand scrolls
instead, with the mouse wheel or the arrows at either end.

Melds keep the order they are meant to be read in. A run reads along the
sequence with the wild card sitting in the hole it fills — `5 · joker · 7`, not
`5 · 7 · joker` — and cards added later are folded into place rather than tacked
on the end. Runs are drawn standing up and sets lying down, so the two are
told apart at a glance.

Clicking a meld only ever adds to it: buying the wild card back is a move of
its own, on its own button.

The opponent has two levels, Easy and Normal. It counts what it can lay down
before deciding whether the discard pile is worth taking, takes its own
pinelle back when it holds the natural card, and plays to close.

## The cards

![All 40 Briscola cards](docs/deck.png)

Every card is drawn with canvas primitives — no image files, and sharp at any
size: traditional pip layouts for the numerals, a letter plus a pip for the
face cards, and the four French suits built from ovals and polygons rather than
unicode glyphs, which do not survive the PostScript export the screenshots go
through. The joker is a jester's cap.

Briscola plays a French deck with the 8s, 9s and 10s removed, which is how it
is often played in Italy: the remaining 40 cards match an Italian deck one for
one, with the queen standing in for the cavallo. Burraco uses both full decks.

Each suit gets its own colour instead of the usual red and black. Two suits
sharing a colour is fine when you hold thirteen cards and have time; here you
read a hand in a moment, and a glance at the colour is quicker than a glance at
the shape. Set `SUIT_COLORS = TWO_COLOUR` in `cardgames/cardart.py` for the
traditional red and black, or `STYLE = "minimal"` for faces with no pips.

## Match records

Every finished game is recorded against a player name (your system user name by
default), for either game. Records are written to **two files**, side by side:

- `~/.briscola/records.json` — the structured store the app reads back.
- `~/.briscola/records.txt` — a plain-text log, one line per match, appended as
  you play, so the history stays readable without the app:

```
# Briscola match log
# date time        player           game      result   you -  ai   settings
2026-08-18 15:02  lorenzo          briscola  WIN        73 - 47    difficulty=normal opened=you
2026-08-18 15:19  lorenzo          burraco   LOSS      585 - 835   difficulty=normal opened=computer
```

Both paths can be redirected with the `BRISCOLA_RECORDS` and
`BRISCOLA_RECORDS_TXT` environment variables, which is what the tests use.

![The statistics window](docs/statistics.png)

An interrupted game is never recorded — only a finished one is.

## Pacing and performance

Briscola pauses twice per trick — before the computer plays, and again on the
finished trick so you can see what it won — because otherwise cards appear and
vanish faster than you can read them. **Clicking the table or pressing space
carries on immediately**: 550 ms and 1000 ms if you let them run, nothing if you
don't. During your own turn a click on a card only ever plays that card.

Which card a click or the hover lift refers to is worked out from the pointer
position against the fixed slot geometry, never from where the card image
currently sits. That matters more than it sounds: the obvious implementation,
Tk's per-item `<Enter>`/`<Leave>`, deadlocked the window. Lifting a card moved
it out from under a pointer resting near its bottom edge, Tk sent `<Leave>`,
the card dropped back under the pointer, `<Enter>` fired, and the two chased
each other at full CPU while real clicks were never processed.

Measured on an Apple M2, per decision:

| Level | Mean | Worst |
| --- | --- | --- |
| Easy, Normal | under 1 ms | under 1 ms |
| Expert | ~103 ms | ~134 ms |

The Expert search runs in the interface thread, so it is capped by a wall-clock
budget (`ai.TIME_BUDGET`, 120 ms) as well as by a number of sampled worlds,
whichever ends first. On a slower machine it samples fewer worlds instead of
freezing for longer.

Idle — on the menu or waiting for your card — the process measures **0.2% CPU
and about 78 MB resident**. If the interface ever misbehaves, run it with
`BRISCOLA_DEBUG=1` and it traces every turn, click, timer and opponent decision
to stdout; exceptions inside a callback are printed and shown in the status bar
rather than swallowed.

## Project layout

| Path | Contents |
| --- | --- |
| `main.py` | Entry point |
| `cardgames/cards.py` | Cards and decks, shared: real ranks 1–13, jokers |
| `cardgames/cardart.py` | Card drawing on a Canvas |
| `cardgames/records.py` | Per-player records: json store and text log |
| `cardgames/ui.py` | Palette and window geometry |
| `cardgames/briscola/` | `engine.py` rules, `ai.py` opponent, `layout.py` geometry, `gui.py` window |
| `cardgames/burraco/` | `engine.py` rules, `ai.py` opponent, `layout.py` geometry, `view.py` table |
| `tools/screenshots.py` | Regenerates the images in `docs/` |
| `tests/` | See below |

Neither game's rules import Tkinter, so they can be tested and reused without
an interface. The geometry is separate again: `layout.py` is plain arithmetic,
which is why most of what used to need a window does not any more.

## Tests

No test framework needed — each file runs standalone:

```bash
conda run -n briscola python tests/test_burraco.py
```

| File | Tests | Time | Covers |
| --- | --- | --- | --- |
| `test_layout.py` | 21 | 0.08 s | Table geometry, with no window at all |
| `test_records.py` | 7 | 0.05 s | The json store and the text log |
| `test_burraco.py` | 56 | 2.5 s | Burraco rules, melds, wild cards, scoring, the opponent |
| `test_engine.py` | 8 | 12 s | Briscola rules and the relative strength of the levels |
| `test_gui.py` | 22 | 18 s | The window: event routing, turns, records |

`test_gui.py` drives the interface with real Tk mouse events, including a whole
Burraco hand played only by clicking real controls. Its windows are parked off
screen so they neither steal focus nor catch a stray click.

Each file runs as many tests as it defines — worth checking, since appending a
test below the `if __name__ == "__main__"` block that runs them means it never
runs at all, and the suite reports all green without it:

```bash
for f in tests/*.py; do
  echo "$f: $(grep -c '^def test_' $f) defined, $(conda run -n briscola python $f | grep -c '^ok') ran"
done
```

## Screenshots

The images in `docs/` are generated from the real code — the interface is one
Canvas, which is exported to PostScript and converted to PNG with Ghostscript:

```bash
conda run -n briscola python tools/screenshots.py
```

This needs `gs` on the path (`brew install ghostscript` on macOS). Each image is
rendered in its own process, because opening several Tk roots in one process is
flaky on macOS.

## Ideas for later

- Burraco for four players in two pairs, which is how it is usually played.
- A cap on how far a long row of melds may spread down the table.
- Best-of-three Briscola with a running aggregate score.
- A leaderboard across players in the statistics window.
