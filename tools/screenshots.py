"""Render the screenshots used by README.md.

The game table is drawn on a Tkinter Canvas, so the images come
straight from the real code (the native toolbar is not included): each canvas is exported to PostScript and
converted to PNG with Ghostscript (`gs`, e.g. `brew install ghostscript`).

    conda run -n briscola python tools/screenshots.py
"""

import os
import subprocess
import sys
import time
import tempfile
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cardgames import cardart, records                # noqa: E402
from cardgames.briscola import ai, gui                 # noqa: E402
from cardgames.cards import BRISCOLA_RANKS, SUITS, Card   # noqa: E402
from cardgames.briscola.engine import AI, HUMAN                   # noqa: E402

DOCS = ROOT / "docs"
DPI = 110


def export(canvas, width, height, name):
    """Canvas -> PostScript -> PNG."""
    DOCS.mkdir(exist_ok=True)
    target = DOCS / f"{name}.png"
    canvas.update()
    with tempfile.TemporaryDirectory() as tmp:
        ps_file = Path(tmp) / f"{name}.ps"
        canvas.postscript(file=str(ps_file), colormode="color",
                          x=0, y=0, width=width, height=height)
        subprocess.run(
            ["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop",
             "-sDEVICE=png16m", f"-r{DPI}", "-dGraphicsAlphaBits=4",
             "-dTextAlphaBits=4", f"-sOutputFile={target}", str(ps_file)],
            check=True)
    print(f"wrote {target.relative_to(ROOT)}")
    return target


def sample_records(path: Path) -> records.Records:
    """A throwaway record file with a plausible history, for the screenshot."""
    store = records.Records(path=path / "records.json",
                            text_path=path / "records.txt")
    store.set_player("lorenzo")
    played = [(78, 42, ai.NORMAL, "you"), (64, 56, ai.NORMAL, "computer"),
              (51, 69, ai.HARD, "you"), (72, 48, ai.NORMAL, "you"),
              (46, 74, ai.HARD, "computer"), (85, 35, ai.EASY, "you"),
              (61, 59, ai.NORMAL, "computer"), (39, 81, ai.HARD, "you"),
              (66, 54, ai.NORMAL, "you")]
    start = datetime.now() - timedelta(days=3)
    for index, (you, them, level, opened) in enumerate(played):
        match = store.add_match("lorenzo", you, them, level, opened)
        # Backdate the rows so the table shows a spread of dates.
        when = start + timedelta(hours=6 * index)
        store.data["players"]["lorenzo"]["matches"][index]["date"] = \
            when.isoformat(timespec="seconds")
    store.save()
    return store


def shot_menu(store):
    """The opening screen."""
    app = gui.BriscolaApp(records_store=store, scale=1.0)
    # Show the path a real install would use, not the temporary one.
    app.records.path = Path("~/.briscola/records.json")
    app.set_difficulty(ai.HARD)
    settle(app, 0.2)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "menu")
    app.destroy()


def shot_table(store):
    """The main window a few tricks into a game, with a card hovered."""
    app = gui.BriscolaApp(records_store=store, scale=1.0)
    app.difficulty = ai.HARD
    gui.AI_DELAY = 10
    gui.TRICK_DELAY = 10
    app.start_game()

    # Play a handful of tricks, then stop with the computer's card on the table.
    for _ in range(400):
        app.update()
        if app.state == gui.S_HUMAN:
            if app.game.tricks_played >= 4 and app.game.lead_card is not None:
                break
            app._play_human(0)
    app._set_hover_index(1)
    settle(app)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "table")
    app.destroy()


def settle(app, seconds=0.6):
    """Let the card animation finish before exporting."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.update()
        time.sleep(0.02)


def shot_rules(store):
    """The rules panel, drawn inside the window rather than as a dialog."""
    app = gui.BriscolaApp(records_store=store, scale=1.0)
    gui.AI_DELAY = gui.TRICK_DELAY = 10
    app.start_game()
    for _ in range(400):
        app.update()
        if app.state == gui.S_HUMAN:
            if app.game.tricks_played >= 2 and app.game.lead_card is not None:
                break
            app._play_human(0)
    app.show_rules()
    settle(app, 0.3)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "rules")
    app.destroy()


def shot_burraco(store):
    """The Burraco table, a few turns in, with two cards picked."""
    from cardgames import ui
    from cardgames.burraco import ai as burraco_ai
    from cardgames.burraco.engine import HUMAN as B_HUMAN

    app = gui.BriscolaApp(records_store=store, scale=1.0)
    gui.AI_DELAY = 5
    app.set_game(ui.BURRACO)
    app.update()
    app.start_game()

    turns = 0
    while turns < 12 and not app.game.game_over:
        settle(app, 0.05)
        if app.state != gui.S_HUMAN:
            continue
        burraco_ai.take_turn(app.game, B_HUMAN, app.difficulty)
        app.selected.clear()
        app.after_move()
        turns += 1

    settle(app, 0.3)
    app.selected = {0, 2}
    app.render()
    settle(app, 0.2)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "burraco")
    app.destroy()


def shot_scopa(store):
    """The Scopa table a few cards in, with a take picked out on the table."""
    from cardgames import ui
    from cardgames.scopa import ai as scopa_ai
    from cardgames.scopa import view as scopa_view
    from cardgames.scopa.engine import HUMAN as S_HUMAN

    app = gui.BriscolaApp(records_store=store, scale=1.0)
    gui.AI_DELAY = 5
    app.set_game(ui.SCOPA)
    app.update()
    app.start_game()

    played = 0
    while played < 9 and not app.game.game_over:
        settle(app, 0.05)
        if app.state != gui.S_HUMAN:
            continue
        # Played through the view, so both sides show up in the move log.
        index, taking = scopa_ai.choose_move(app.game, S_HUMAN, app.difficulty)
        app.table_pick = {app.game.table.index(one) for one in taking}
        scopa_view.click_card(app, index)
        played += 1

    settle(app, 0.3)
    app.table_pick = {0} if app.game.table else set()
    app.render()
    settle(app, 0.2)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "scopa")
    app.destroy()


def shot_tressette(store):
    """The Tressette table with the computer's lead down, so the cards the
    obligation rules out are shown greyed."""
    from cardgames import ui
    from cardgames.tressette import ai as tressette_ai
    from cardgames.tressette.engine import HUMAN as T_HUMAN

    app = gui.BriscolaApp(records_store=store, scale=1.0)
    gui.AI_DELAY = gui.TRICK_DELAY = 5
    app.set_game(ui.TRESSETTE)
    app.update()
    app.start_game()

    for _ in range(3000):
        settle(app, 0.01)
        game = app.game
        if game.game_over:
            break
        if app.state != gui.S_HUMAN:
            continue
        legal = game.legal_cards(T_HUMAN)
        # Stop on a position that shows the rule: a lead down, and cards in
        # hand the player is not allowed to answer with.
        if game.tricks_played >= 5 and len(legal) < len(game.hands[T_HUMAN]):
            break
        index = tressette_ai.choose_card(game, T_HUMAN, app.difficulty)
        game.play_card(T_HUMAN, index)
        app.tressette_advance()

    app.hovered = None
    app.render()
    settle(app, 0.3)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "tressette")
    app.destroy()


def shot_statistics(store):
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=gui.STATS_W, height=gui.STATS_H,
                       bg=gui.PANEL_BG, highlightthickness=0)
    canvas.pack()
    # Show the paths a real install would use, not the temporary ones.
    gui.draw_statistics(canvas, "lorenzo", store.stats("lorenzo"),
                        store.matches("lorenzo"),
                        Path("~/.briscola/records.json"),
                        Path("~/.briscola/records.txt"))
    export(canvas, gui.STATS_W, gui.STATS_H, "statistics")
    root.destroy()


def shot_deck():
    """All 40 cards, plus a card back and an empty slot."""
    w, h, gap = 84, 128, 12
    width = 10 * (w + gap) + gap
    height = 5 * (h + gap) + gap
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=width, height=height, bg=gui.FELT,
                       highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(0, 0, width, height, fill=gui.FELT, outline="")
    for row, suit in enumerate(SUITS):
        for col, rank in enumerate(BRISCOLA_RANKS):
            cardart.draw_card(canvas, gap + col * (w + gap),
                              gap + row * (h + gap), w, h, Card(rank, suit),
                              highlight=(row == 0 and col == 0))
    y = gap + 4 * (h + gap)
    cardart.draw_card_back(canvas, gap, y, w, h)
    cardart.draw_placeholder(canvas, gap + (w + gap), y, w, h, "empty\nslot")
    canvas.create_text(gap + 2.4 * (w + gap), y + h / 2,
                       text="card back and empty table slot;\n"
                            "the gold frame on the Ace marks the card\n"
                            "that wins a trick",
                       anchor="w", fill=gui.TEXT_DIM, font=("Helvetica", 12))
    export(canvas, width, height, "deck")
    root.destroy()



def shot_training(store):
    """Italian suits and an explainable Scopa hint."""
    from cardgames.scopa.engine import Game
    app = gui.BriscolaApp(records_store=store, scale=1.0)
    app.language = "it"
    app.deck_style = "italian"
    app.set_game("scopa")
    app.start_game()
    app._cancel_pending()
    app.game = Game(seed=17)
    app.after_move()
    app.show_hint()
    settle(app, 0.1)
    export(app.canvas, gui.WIN_W, gui.WIN_H, "italian-training")
    app.destroy()


SHOTS = {
    "menu": shot_menu,
    "table": shot_table,
    "burraco": shot_burraco,
    "scopa": shot_scopa,
    "tressette": shot_tressette,
    "statistics": shot_statistics,
    "deck": lambda _store: shot_deck(),
    "italian-training": shot_training,
}


def main(argv=None):
    """Render every shot, each in its own process.

    Opening and destroying several Tk roots inside one process is flaky on
    macOS — it segfaulted once during a run — so each shot gets a fresh
    interpreter. The sample records are written once and shared by path.
    """
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == "--shot":
        name = argv[1]
        store = records.Records(path=Path(os.environ["BRISCOLA_RECORDS"]),
                                text_path=Path(os.environ["BRISCOLA_RECORDS_TXT"]))
        SHOTS[name](store)
        return

    with tempfile.TemporaryDirectory() as tmp:
        store = sample_records(Path(tmp))
        env = dict(os.environ,
                   BRISCOLA_RECORDS=str(store.path),
                   BRISCOLA_RECORDS_TXT=str(store.text_path))
        for name in SHOTS:
            result = subprocess.run([sys.executable, __file__, "--shot", name],
                                    env=env)
            if result.returncode != 0:
                raise SystemExit(f"{name} shot failed "
                                 f"(exit {result.returncode})")


if __name__ == "__main__":
    main()
