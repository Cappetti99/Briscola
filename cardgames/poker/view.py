"""The poker table: what is drawn, and what a button on it means.

Functions over the shell window, the way the other tables are written. The
cards are not clickable — a hand of poker is decided in the panel, not by
pointing at a card — so a click on the felt does only what a click does
everywhere else in this window: carry on through a pause. Your own two
cards still lift under the pointer, because a hand you can read at a
glance is a hand you play better.
"""

from .. import cardart, ui
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_DARK, FELT_EDGE,
                  PANEL_BG, PANEL_CARD, TABLE_H, TABLE_W, TEXT, TEXT_DIM)
from . import ai as poker_ai
from .engine import AI, HUMAN, describe

from .layout import (BOARD_H, BOARD_SLOTS, BOARD_W, BOARD_Y, CENTER_X,
                     HOLE_AI_Y, HOLE_H, HOLE_W, HOLE_YOU_Y, LIFT, LOG_LINES,
                     NAME_AI_Y, NAME_YOU_Y, POT_Y, STREET_Y, bet_slot,
                     board_x, dealer_button, hole_slot_at, hole_x)

# The five things the panel can ask for, in the order the keys reach them.
ACTIONS = ("fold", "call", "raise", "pot", "allin")


# --- drawing --------------------------------------------------------------

def draw(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")
    canvas.create_oval(CENTER_X - 350, 110, CENTER_X + 350, 470,
                       fill=FELT_DARK, outline="")

    _names(app, game)
    _dealer(app, game)
    _seat(app, game, AI, HOLE_AI_Y)
    _seat(app, game, HUMAN, HOLE_YOU_Y)
    _board(app, game)
    _pot(app, game)
    _bets(app, game)


def _names(app, game):
    canvas = app.canvas
    for player, y in ((AI, NAME_AI_Y), (HUMAN, NAME_YOU_Y)):
        title = "COMPUTER" if player == AI else "YOU"
        canvas.create_text(20, y, text=title, anchor="w", fill=FELT_EDGE,
                           font=ui.font(10, "bold"))
        canvas.create_text(TABLE_W - 20, y, text=f"{game.stacks[player]} chips",
                           anchor="e", fill=TEXT_DIM, font=ui.font(10))


def _seat(app, game, player, y):
    canvas = app.canvas
    hand = game.hands[player]
    if not hand:
        # Folded away: the cards are in the muck and the outlines say so.
        for index in range(2):
            cardart.draw_placeholder(canvas, hole_x(index), y, HOLE_W, HOLE_H)
        return
    for index, card in enumerate(hand):
        x = hole_x(index)
        tags = (f"hand{index}",) if player == HUMAN else ()
        if player == HUMAN or game.showdown:
            lift = LIFT if (player == HUMAN and index == app.hovered) else 0
            cardart.draw_card(canvas, x, y - lift, HOLE_W, HOLE_H, card,
                              tags=tags,
                              highlight=(game.game_over and game.showdown
                                         and game.winner == player))
        else:
            cardart.draw_card_back(canvas, x, y, HOLE_W, HOLE_H, tags=tags)


def _board(app, game):
    canvas = app.canvas
    for index in range(BOARD_SLOTS):
        x = board_x(index)
        if index < len(game.table):
            cardart.draw_card(canvas, x, BOARD_Y, BOARD_W, BOARD_H,
                              game.table[index])
        else:
            cardart.draw_placeholder(canvas, x, BOARD_Y, BOARD_W, BOARD_H)


def _pot(app, game):
    canvas = app.canvas
    canvas.create_text(CENTER_X, POT_Y, text=f"Pot {game.pot}", fill=ACCENT,
                       font=ui.font(17, "bold"))
    canvas.create_text(CENTER_X, STREET_Y, text=game.phase, fill=FELT_EDGE,
                       font=ui.font(11, "bold"))


def _bets(app, game):
    """Chips in front of a player, for the street being played."""
    canvas = app.canvas
    for player in (AI, HUMAN):
        if game.committed[player] <= 0:
            continue
        x, y = bet_slot(player)
        for offset in (26, 13, 0):
            canvas.create_oval(x - offset - 13, y - 13, x - offset + 13,
                               y + 13, fill="#e8d7a8", outline="#8a6b2a")
            canvas.create_oval(x - offset - 6, y - 6, x - offset + 6, y + 6,
                               fill=ACCENT, outline="")
        canvas.create_text(x + 18, y, text=str(game.committed[player]),
                           anchor="w", fill=ACCENT, font=ui.font(13, "bold"))


def _dealer(app, game):
    canvas = app.canvas
    for player in (AI, HUMAN):
        x, y = dealer_button(player)
        if game.dealer != player:
            continue
        canvas.create_oval(x - 13, y - 13, x + 13, y + 13,
                           fill="#f4efe2", outline="#3b3428")
        canvas.create_text(x, y, text="D", fill="#3b3428",
                           font=ui.font(11, "bold"))
        canvas.create_text(x, y + 26, text="dealer", fill=FELT_EDGE,
                           font=ui.font(8))


# --- the side panel -------------------------------------------------------

def _labels(game) -> tuple[str, ...]:
    """What the five buttons say, in your wording when it is your move."""
    legal = game.legal_actions(HUMAN)
    if not legal:
        return ("Fold", "Check or call", "Raise", "Pot", "All in")
    owed = game.to_call(HUMAN)
    top = game.max_to(HUMAN)
    call = min(owed, game.stacks[HUMAN])
    return ("Fold",
            "Check" if owed == 0 else f"Call {call}",
            f"{'Bet' if owed == 0 else 'Raise to'} {game.min_to(HUMAN)}",
            f"Pot {min(max(game.committed) + game.pot, top)}",
            f"All in {top}")


def draw_panel(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(TABLE_W, 0, TABLE_W + 320, TABLE_H,
                            fill=PANEL_BG, outline="")
    canvas.create_text(CONTENT_X, 26, text="POKER", anchor="w", fill=ACCENT,
                       font=ui.font(19, "bold"))
    match = app.match
    if match is None or match.single_hand:
        subtitle = "you vs. the computer  -  one hand"
    else:
        subtitle = f"match to {match.target}  -  hand {match.hands + 1}"
    canvas.create_text(CONTENT_X, 48, text=subtitle, anchor="w",
                       fill=TEXT_DIM, font=ui.font(11))
    app._panel_link(CONTENT_X + CONTENT_W, 26, "menu", "back", app.show_menu)

    y = 74
    for player, title in ((HUMAN, "YOU"), (AI, "COMPUTER")):
        cardart.round_rect(canvas, CONTENT_X, y, CONTENT_X + CONTENT_W,
                           y + 62, 8, fill=PANEL_CARD, outline="")
        canvas.create_text(CONTENT_X + 10, y + 16, text=title, anchor="w",
                           fill=TEXT_DIM, font=ui.font(9, "bold"))
        canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 18,
                           text=str(game.stacks[player]), anchor="e",
                           fill=TEXT, font=ui.font(17, "bold"))
        notes = []
        if game.dealer == player:
            notes.append("dealer")
        if game.committed[player] > 0:
            notes.append(f"bet {game.committed[player]}")
        canvas.create_text(CONTENT_X + 10, y + 40, text=", ".join(notes),
                           anchor="w", fill=TEXT_DIM, font=ui.font(10))
        if match is not None and not match.single_hand:
            canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 40,
                               text=f"match {match.totals[player]}",
                               anchor="e", fill=ACCENT, font=ui.font(10, "bold"))
        y += 72

    canvas.create_text(CONTENT_X, y + 6, text=f"Pot {game.pot}", anchor="w",
                       fill=TEXT, font=ui.font(12, "bold"))
    canvas.create_text(CONTENT_X + CONTENT_W, y + 6, text=game.phase,
                       anchor="e", fill=TEXT_DIM, font=ui.font(10))
    canvas.create_text(CONTENT_X, y + 28, text=_hold_line(game), anchor="w",
                       fill=TEXT_DIM, font=ui.font(10), width=CONTENT_W)

    top = y + 48
    half = (CONTENT_W - 8) / 2
    third = (CONTENT_W - 16) / 3
    labels = _labels(game)
    app._button(CONTENT_X, top, half, 34, labels[0], "poker_fold",
                lambda: act(app, "fold"), font_size=12)
    app._button(CONTENT_X + half + 8, top, half, 34, labels[1],
                "poker_call", lambda: act(app, "call"), primary=True,
                font_size=12)
    for slot, kind in enumerate(("raise", "pot", "allin")):
        app._button(CONTENT_X + slot * (third + 8), top + 40, third, 34,
                    labels[2 + slot], f"poker_{kind}",
                    lambda kind=kind: act(app, kind), font_size=11)

    buttons = top + 84
    app._panel_button(buttons, "New game", "new", app.new_match, primary=True)
    app._panel_button(buttons + 38, "Statistics", "stats", app.show_statistics)
    app._panel_button(buttons + 76,
                      f"Difficulty: {poker_ai.LEVEL_LABELS[app.difficulty]}",
                      "level", app.cycle_difficulty)
    app._panel_button(buttons + 114, "Rules", "rules", app.show_rules)

    canvas.create_text(CONTENT_X, buttons + 152, text="LAST MOVES", anchor="w",
                       fill=TEXT, font=ui.font(9, "bold"))
    for row, line in enumerate(app.log_lines[:LOG_LINES]):
        left, right = line if isinstance(line, tuple) else (line, "")
        at = buttons + 170 + row * 17
        canvas.create_text(CONTENT_X, at, text=left, anchor="w",
                           fill=TEXT_DIM, font=ui.font(10))
        canvas.create_text(CONTENT_X + CONTENT_W, at, text=right, anchor="e",
                           fill=TEXT, font=ui.font(10, "bold"))


def _hold_line(game) -> str:
    """What you hold, or what became of it once the hand is finished."""
    if game.showdown and game.names[HUMAN]:
        return f"Your hand: {game.names[HUMAN]}"
    if not game.hands[HUMAN]:
        return "You folded."
    if game.phase == "preflop" or not game.table:
        return "Your cards: " + " / ".join(card.short()
                                           for card in game.hands[HUMAN])
    return f"Your hand: {describe(game.hands[HUMAN] + game.table)}"


# --- clicks, keys and moves ----------------------------------------------

def click_at(app, x, y) -> bool:
    """Nothing on the felt is clickable; say so by letting the click pass."""
    return True


def press(app, index: int) -> None:
    """The number keys, in the panel's own order."""
    if 0 <= index < len(ACTIONS):
        act(app, ACTIONS[index])


def act(app, kind: str) -> None:
    """Carry out one of the five panel actions for the human player."""
    game = app.game
    if game is None or game.game_over or app.overlay is not None:
        return
    if game.turn != HUMAN:
        app.say("Wait for your turn.")
        return
    legal = game.legal_actions(HUMAN)
    if kind == "fold":
        if "fold" not in legal:
            app.say("There is nothing to fold to: check or bet.")
            return
        play(app, "fold")
        return
    if kind == "call":
        if "call" in legal:
            play(app, "call")
        elif "check" in legal:
            play(app, "check")
        return
    if kind not in ("raise", "pot", "allin"):
        return
    if "raise" not in legal and "bet" not in legal:
        app.say("There is nothing to raise: check or call.")
        return
    target = {"raise": game.min_to(HUMAN),
              "pot": min(max(game.committed) + game.pot, game.max_to(HUMAN)),
              "allin": game.max_to(HUMAN)}[kind]
    play(app, "raise" if "raise" in legal else "bet", target)


def play(app, kind: str, amount: int | None = None) -> None:
    """Apply the move, log it publicly, and hand over to the window."""
    line = app.game.act(HUMAN, kind, amount)
    app.note(line)
    app.poker_advance()


# --- hover ----------------------------------------------------------------

def pointed_card(app, x, y):
    game = app.game
    if (game is None or app.overlay is not None or game.game_over
            or game.turn != HUMAN):
        return None
    return hole_slot_at(x, y, len(game.hands[HUMAN]), HOLE_YOU_Y)


def on_motion(app, x, y):
    index = pointed_card(app, x, y)
    if index == app.hovered:
        return
    for slot, lift in ((app.hovered, LIFT), (index, -LIFT)):
        if slot is not None:
            app.canvas.move(f"hand{slot}", 0, lift)
    app.hovered = index
    app.canvas.config(cursor="hand2" if index is not None else "")
