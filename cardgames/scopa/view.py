"""The Scopa table: what is drawn, and what a click on it means.

Functions over the shell window rather than a class of its own, the same way
Burraco is written, so all three games share one window, one menu and one
record file.
"""

from .. import cardart, ui
from ..cards import Card
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_DARK, FELT_EDGE,
                  PANEL_BG, PANEL_CARD, TABLE_H, TABLE_W, TEXT, TEXT_DIM)
from . import ai as scopa_ai
from .engine import AI, COINS, HUMAN, SETTEBELLO, Ambiguous, IllegalCapture

from .layout import (BACK_H, BACK_W, CARD_H, CARD_W, CENTER_X, HAND_Y,
                     HOVER_LIFT, OPP_HAND_Y, OPP_PILE_Y, PILE_H, PILE_W,
                     PILE_X, TABLE_MID, YOUR_PILE_Y, hand_slot_at, hand_x,
                     PICK_LIFT, opponent_hand_x, table_boxes,
                     table_slot_at)


# --- drawing --------------------------------------------------------------

def draw(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")
    canvas.create_oval(CENTER_X - 330, TABLE_MID - 190, CENTER_X + 330,
                       TABLE_MID + 190, fill=FELT_DARK, outline="")

    _draw_opponent(app, game)
    _draw_piles(app, game)
    _draw_table(app, game)
    _draw_hand(app, game)


def _draw_opponent(app, game):
    canvas = app.canvas
    count = len(game.hands[AI])
    for index in range(count):
        cardart.draw_card_back(canvas, opponent_hand_x(count, index),
                               OPP_HAND_Y, BACK_W, BACK_H)
    canvas.create_text(TABLE_W - 12, OPP_HAND_Y + BACK_H / 2,
                       text=f"COMPUTER  {count} cards", anchor="e",
                       fill=FELT_EDGE, font=ui.font(10, "bold"))


def _draw_piles(app, game):
    """The two capture piles, with what each side has taken so far."""
    for player, y, label in ((AI, OPP_PILE_Y, "their pile"),
                             (HUMAN, YOUR_PILE_Y, "your pile")):
        taken = game.captured[player]
        canvas = app.canvas
        if taken:
            cardart.draw_card_back(canvas, PILE_X, y, PILE_W, PILE_H)
        else:
            cardart.draw_placeholder(canvas, PILE_X, y, PILE_W, PILE_H, label)
        coins = sum(1 for card in taken if card.suit == COINS)
        canvas.create_text(PILE_X + PILE_W / 2, y + PILE_H + 16,
                           text=_count(len(taken), "card"), fill=TEXT_DIM,
                           font=ui.font(10))
        canvas.create_text(PILE_X + PILE_W / 2, y + PILE_H + 32,
                           text=_count(coins, "coin"), fill=TEXT_DIM,
                           font=ui.font(10))
        if SETTEBELLO in taken:
            canvas.create_text(PILE_X + PILE_W / 2, y + PILE_H + 50,
                               text="settebello", fill=ACCENT,
                               font=ui.font(10, "bold"))
        _draw_scope(app, player, y)


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _draw_scope(app, player, y):
    """A gold pip for every scopa, which is the score people watch."""
    canvas = app.canvas
    for index in range(app.game.scope[player]):
        row, column = divmod(index, 4)
        canvas.create_oval(PILE_X + column * 16, y - 22 - row * 16,
                           PILE_X + 10 + column * 16, y - 12 - row * 16,
                           fill=ACCENT, outline="")


def _draw_table(app, game):
    canvas = app.canvas
    boxes = table_boxes(len(game.table))
    if not boxes:
        canvas.create_text(CENTER_X, TABLE_MID, text="the table is empty",
                           fill=FELT_EDGE, font=ui.font(12, "bold"))
        return
    for index, (card, box) in enumerate(zip(game.table, boxes)):
        x, y, width, height = box
        tag = f"table{index}"
        picked = index in app.table_pick
        cardart.draw_card(canvas, x, y - (PICK_LIFT if picked else 0),
                          width, height, card, tags=(tag,), highlight=picked)


def _draw_hand(app, game):
    canvas = app.canvas
    hand = game.hands[HUMAN]
    for index, card in enumerate(hand):
        x = hand_x(len(hand), index)
        y = HAND_Y - (HOVER_LIFT if index == app.hovered else 0)
        tag = f"hand{index}"
        cardart.draw_card(canvas, x, y, CARD_W, CARD_H, card, tags=(tag,))
        canvas.create_text(x + CARD_W / 2, HAND_Y + CARD_H + 16,
                           text=str(index + 1), fill=TEXT_DIM,
                           font=ui.font(10, "bold"))
    canvas.create_text(TABLE_W - 12, HAND_Y + CARD_H / 2, text="YOU",
                       anchor="e", fill=FELT_EDGE, font=ui.font(10, "bold"))


def pointed_card(app, x, y):
    game = app.game
    if not game or app.overlay is not None or game.turn != HUMAN:
        return None
    return hand_slot_at(x, y, len(game.hands[HUMAN]))


def on_motion(app, x, y):
    """Lift the card under the pointer, and put the last one back down."""
    index = pointed_card(app, x, y)
    if index == app.hovered:
        return
    for slot, lift in ((app.hovered, HOVER_LIFT), (index, -HOVER_LIFT)):
        if slot is not None:
            app.canvas.move(f"hand{slot}", 0, lift)
    app.hovered = index
    app.canvas.config(cursor="hand2" if index is not None else "")


# --- the side panel -------------------------------------------------------

def draw_panel(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(TABLE_W, 0, TABLE_W + 320, TABLE_H,
                            fill=PANEL_BG, outline="")
    canvas.create_text(CONTENT_X, 26, text="SCOPA", anchor="w", fill=ACCENT,
                       font=ui.font(19, "bold"))
    match = app.match
    if match is None or match.single_hand:
        subtitle = "you vs. the computer  -  one hand"
    else:
        subtitle = f"match to {match.target}  -  hand {match.hands + 1}"
    canvas.create_text(CONTENT_X, 48, text=subtitle, anchor="w", fill=TEXT_DIM,
                       font=ui.font(11))
    app._panel_link(CONTENT_X + CONTENT_W, 26, "menu", "back", app.show_menu)

    tallies = game.tallies()
    y = 74
    for player, title in ((HUMAN, "YOU"), (AI, "COMPUTER")):
        tally = tallies[player]
        cardart.round_rect(canvas, CONTENT_X, y, CONTENT_X + CONTENT_W,
                           y + 104, 8, fill=PANEL_CARD, outline="")
        canvas.create_text(CONTENT_X + 10, y + 16, text=title, anchor="w",
                           fill=TEXT_DIM, font=ui.font(9, "bold"))
        canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 16,
                           text=str(tally.total), anchor="e", fill=TEXT,
                           font=ui.font(15, "bold"))
        # The four points are only settled when the hand ends, so what is
        # shown while it runs is where they stand right now.
        for row, (name, value) in enumerate(tally.lines()):
            line_y = y + 36 + row * 13
            canvas.create_text(CONTENT_X + 10, line_y, text=name, anchor="w",
                               fill=TEXT if value else TEXT_DIM,
                               font=ui.font(9))
            canvas.create_text(CONTENT_X + CONTENT_W - 10, line_y,
                               text=str(value), anchor="e",
                               fill=ACCENT if value else TEXT_DIM,
                               font=ui.font(9, "bold"))
        if match is not None and not match.single_hand:
            canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 16 - 18,
                               text=f"match {match.totals[player]}", anchor="e",
                               fill=ACCENT, font=ui.font(10, "bold"))
        y += 116

    canvas.create_text(CONTENT_X, y + 4,
                       text=f"Cards still to deal: {game.cards_left}",
                       anchor="w", fill=TEXT_DIM, font=ui.font(10))
    canvas.create_text(CONTENT_X, y + 22,
                       text=_hint(app), anchor="w", fill=TEXT_DIM,
                       font=ui.font(10), width=CONTENT_W)

    top = y + 62
    app._button(CONTENT_X, top, CONTENT_W, 30, "Clear the picks",
                "scopa_clear", lambda: clear_picks(app),
                selected=bool(app.table_pick), font_size=11)
    app._panel_button(top + 42, "New game", "new", app.new_match, primary=True)
    app._panel_button(top + 80, "Statistics", "stats", app.show_statistics)
    app._panel_button(top + 116,
                      f"Difficulty: {scopa_ai.LEVEL_LABELS[app.difficulty]}",
                      "level", app.cycle_difficulty)
    app._panel_button(top + 152, "Rules", "rules", app.show_rules)

    canvas.create_text(CONTENT_X, top + 200, text="LAST MOVES", anchor="w",
                       fill=TEXT, font=ui.font(9, "bold"))
    for row, line in enumerate(app.log_lines[:8]):
        canvas.create_text(CONTENT_X, top + 218 + row * 16,
                           text=line[0] if isinstance(line, tuple) else line,
                           anchor="w", fill=TEXT_DIM, font=ui.font(9))


def _hint(app):
    """What the player is waiting to be told, in one line."""
    game = app.game
    if game.game_over:
        return "The hand is over."
    if game.turn != HUMAN:
        return "The computer is thinking."
    if app.table_pick:
        return f"{_count(len(app.table_pick), 'card')} picked: now play the card that takes them."
    return "Click a card to play it, or 1 / 2 / 3."


# --- clicks ---------------------------------------------------------------

def click_at(app, x, y):
    """Route a click by the fixed slot geometry, not by what item is there.

    A picked card is drawn lifted and a hovered one too, so asking Tk which
    item is under the pointer would leave a dead strip along the bottom edge
    of every lifted card - the fault that once made the Briscola hand
    unclickable. These sums do not move when a card does.
    """
    game = app.game
    if game is None or game.game_over or game.turn != HUMAN:
        return
    index = hand_slot_at(x, y, len(game.hands[HUMAN]))
    if index is not None:
        click_card(app, index)
        return
    slot = table_slot_at(x, y, len(game.table))
    if slot is not None:
        click_table(app, slot)


def click_table(app, index):
    """Pick a table card, for when there is more than one way to take."""
    game = app.game
    if game.game_over or game.turn != HUMAN or app.overlay is not None:
        return
    if index >= len(game.table):
        return
    if index in app.table_pick:
        app.table_pick.discard(index)
    else:
        app.table_pick.add(index)
    app.render()


def clear_picks(app):
    app.table_pick.clear()
    app.render()


def click_card(app, index):
    """Play the index-th card of your hand, taking whatever it must."""
    game = app.game
    if game is None or game.game_over or game.turn != HUMAN:
        return
    if app.overlay is not None or index >= len(game.hands[HUMAN]):
        return

    card = game.hands[HUMAN][index]
    picked = [game.table[i] for i in sorted(app.table_pick)
              if i < len(game.table)]
    options = game.capture_options(card)

    if picked and not any(set(picked) == set(option) for option in options):
        app.say(f"The {card} cannot take those cards. "
                + _why_not(game, card, options))
        return
    if not picked and len(options) > 1:
        app.say(f"The {card} can take in {len(options)} ways: click the cards "
                "you want, then play it again.")
        return

    try:
        play = game.play(HUMAN, index, picked or None)
    except (Ambiguous, IllegalCapture, RuntimeError) as exc:
        app.say(str(exc))
        return

    app.table_pick.clear()
    app.hovered = None
    app.note(scopa_ai.describe(play, you=True))
    if play.swept:
        app.note(f"You take the {_count(len(play.swept), 'card')} left on the table")
    app.after_move()


def _why_not(game, card: Card, options) -> str:
    """The rule that got in the way, which is usually the single-card one."""
    if not options:
        return "It takes nothing, so it stays on the table."
    if len(options[0]) == 1:
        return ("A card of the same value is on the table, and that one has "
                "to be taken.")
    return "Pick cards that add up to it exactly."


def computer_turn(app):
    """Let the opponent play one card, and say what it did."""
    play = scopa_ai.take_turn(app.game, AI, app.difficulty)
    app.note(scopa_ai.describe(play))
    if play.swept:
        app.note(f"The computer takes the {_count(len(play.swept), 'card')} left over")
