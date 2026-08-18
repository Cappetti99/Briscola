"""The Burraco table: what is drawn, and what a click on it means.

Written as functions over the shell window rather than a class of its own, so
Briscola and Burraco share one window, one menu and one record file.
"""

from .. import cardart
from ..cards import Card
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_DARK, FELT_EDGE,
                  PANEL_BG, PANEL_CARD, TABLE_H, TABLE_W, TEXT, TEXT_DIM)
from . import ai as burraco_ai
from .engine import AI, HUMAN, InvalidMeld, is_wild, wild_stands_for

# Card sizes: hands are eleven cards or more, so they are smaller than in
# Briscola and they overlap.
HAND_W, HAND_H = 82, 124
HAND_STEP = 58
LIFT = 20
MELD_W, MELD_H = 48, 72
MELD_STEP = 21
MELD_VSTEP = 15
BACK_W, BACK_H = 62, 94
BACK_STEP = 30

CENTER_X = TABLE_W // 2
OPP_HAND_Y = 16
OPP_MELD_Y = 128
STOCK_Y = 310
YOUR_MELD_Y = 420
HAND_Y = 616

STOCK_X = 44
MELD_X0 = 240
PILE_X = STOCK_X + 104

ACTIONS = ("draw", "pile", "meld", "swap", "discard", "end")
SORTS = ("suit", "rank")
SORT_LABELS = {"suit": "Sort by suit", "rank": "Sort by rank"}
HOVER_LIFT = 10
ACTION_LABELS = {"draw": "Draw a card", "pile": "Take the pile",
                 "meld": "Lay down", "swap": "Take the pinella",
                 "discard": "Discard", "end": "End turn"}


# --- drawing --------------------------------------------------------------

def draw(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")

    _draw_opponent(app, game)
    _draw_stock(app, game)
    _draw_melds(app, game, HUMAN, YOUR_MELD_Y)
    _draw_hand(app, game)


def _draw_opponent(app, game):
    canvas = app.canvas
    hand = game.hands[AI]
    total = (len(hand) - 1) * BACK_STEP + BACK_W if hand else 0
    start = CENTER_X - total / 2
    for index in range(len(hand)):
        cardart.draw_card_back(canvas, start + index * BACK_STEP, OPP_HAND_Y,
                               BACK_W, BACK_H)
    canvas.create_text(TABLE_W - 12, OPP_HAND_Y + BACK_H / 2,
                       text=f"COMPUTER  {len(hand)} cards", anchor="e",
                       fill=FELT_EDGE, font=("Helvetica", 10, "bold"))
    _draw_melds(app, game, AI, OPP_MELD_Y)


def _draw_stock(app, game):
    canvas = app.canvas
    if game.stock:
        cardart.draw_card_back(canvas, STOCK_X, STOCK_Y, HAND_W, HAND_H)
        canvas.create_text(STOCK_X + HAND_W / 2, STOCK_Y + HAND_H + 14,
                           text=f"{len(game.stock)} in stock", fill=TEXT_DIM,
                           font=("Helvetica", 10))
    else:
        cardart.draw_placeholder(canvas, STOCK_X, STOCK_Y, HAND_W, HAND_H,
                                 "stock\nout")

    if game.discards:
        cardart.draw_card(canvas, PILE_X, STOCK_Y, HAND_W, HAND_H,
                          game.discards[-1])
        canvas.create_text(PILE_X + HAND_W / 2, STOCK_Y + HAND_H + 14,
                           text=f"{len(game.discards)} in the pile",
                           fill=TEXT_DIM, font=("Helvetica", 10))
    else:
        cardart.draw_placeholder(canvas, PILE_X, STOCK_Y, HAND_W, HAND_H,
                                 "discard\npile")

    for player, label, y in ((AI, "their pot", STOCK_Y - 120),
                             (HUMAN, "your pot", STOCK_Y + 150)):
        taken = game.pot_taken[player]
        cardart.draw_placeholder(app.canvas, STOCK_X, y, HAND_W, HAND_H * 0.5,
                                 "taken" if taken else label,
                                 color=ACCENT if taken else FELT_EDGE)


def _draw_melds(app, game, player, top):
    """Sets read across, runs read down.

    A run standing up shows its corner index down one edge, which is the
    order the cards are in — much easier to follow than a long horizontal
    smear, and it leaves room for more melds side by side.
    """
    canvas = app.canvas
    melds = game.melds[player]
    if not melds:
        canvas.create_text(CENTER_X, top + MELD_H / 2, text="no melds yet",
                           fill=FELT_EDGE, font=("Helvetica", 11))
        return

    x, y, row_height = MELD_X0, top, 0
    for index, meld in enumerate(melds):
        vertical = meld.kind == "run"
        if vertical:
            width = MELD_W
            height = (len(meld) - 1) * MELD_VSTEP + MELD_H
        else:
            width = (len(meld) - 1) * MELD_STEP + MELD_W
            height = MELD_H
        if x + width > TABLE_W - 16:
            x, y, row_height = MELD_X0, y + row_height + 14, 0

        tag = f"meld{player}_{index}"
        for offset, card in enumerate(meld.cards):
            cardart.draw_card(canvas,
                              x if vertical else x + offset * MELD_STEP,
                              y + offset * MELD_VSTEP if vertical else y,
                              MELD_W, MELD_H, card, tags=(tag,))
        if meld.is_burraco:
            canvas.create_text(x + width / 2, y - 9,
                               text="BURRACO" + ("" if meld.is_clean else " *"),
                               fill=ACCENT, font=("Helvetica", 9, "bold"))
        if player == HUMAN:
            canvas.tag_bind(tag, "<Button-1>",
                            lambda _e, i=index: click_meld(app, i))
        x += width + 20
        row_height = max(row_height, height)


def _draw_hand(app, game):
    canvas = app.canvas
    hand = game.hands[HUMAN]
    total = (len(hand) - 1) * HAND_STEP + HAND_W if hand else 0
    start = CENTER_X - total / 2
    for index, card in enumerate(hand):
        x = start + index * HAND_STEP
        y = HAND_Y - (LIFT if index in app.selected
                      else HOVER_LIFT if index == app.hovered else 0)
        tag = f"hand{index}"
        cardart.draw_card(canvas, x, y, HAND_W, HAND_H, card, tags=(tag,),
                          highlight=index in app.selected)
        canvas.tag_bind(tag, "<Button-1>",
                        lambda _e, i=index: click_card(app, i))
    canvas.create_text(TABLE_W - 12, HAND_Y + HAND_H / 2,
                       text=f"YOU  {len(hand)} cards", anchor="e",
                       fill=FELT_EDGE, font=("Helvetica", 10, "bold"))


def hand_slot_at(app, x, y):
    """Which hand card the pointer is over, from the fixed fan geometry.

    Like Briscola's, this deliberately ignores where a card has been lifted
    to: an answer that changed as the card moved would have the lift and the
    pointer chasing each other.
    """
    game = app.game
    hand = game.hands[HUMAN] if game else []
    if not hand or app.overlay is not None or game.turn != HUMAN:
        return None
    if not HAND_Y - LIFT <= y <= HAND_Y + HAND_H:
        return None
    total = (len(hand) - 1) * HAND_STEP + HAND_W
    start = CENTER_X - total / 2
    if not start <= x <= start + total:
        return None
    return min(int((x - start) // HAND_STEP), len(hand) - 1)


def on_motion(app, x, y):
    index = hand_slot_at(app, x, y)
    if index == app.hovered:
        return
    for slot, lift in ((app.hovered, HOVER_LIFT), (index, -HOVER_LIFT)):
        if slot is not None and slot not in app.selected:
            app.canvas.move(f"hand{slot}", 0, lift)
    app.hovered = index
    app.canvas.config(cursor="hand2" if index is not None else "")


def sort_hand(app, by):
    """Put the hand in order and forget the selection, which moved with it."""
    app.sort_mode = by
    app.game.sort_hand(HUMAN, by)
    app.selected.clear()
    app.hovered = None


def draw_panel(app):
    """The right-hand column: score, what is left, and the buttons."""
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(TABLE_W, 0, TABLE_W + 292, TABLE_H,
                            fill=PANEL_BG, outline="")
    canvas.create_text(CONTENT_X, 26, text="BURRACO", anchor="w", fill=ACCENT,
                       font=("Helvetica", 19, "bold"))
    canvas.create_text(CONTENT_X, 48, text="you vs. the computer", anchor="w",
                       fill=TEXT_DIM, font=("Helvetica", 11))

    y = 74
    for player, title in ((HUMAN, "YOU"), (AI, "COMPUTER")):
        cardart.round_rect(canvas, CONTENT_X, y, CONTENT_X + CONTENT_W, y + 52,
                           8, fill=PANEL_CARD, outline="")
        canvas.create_text(CONTENT_X + 10, y + 16, text=title, anchor="w",
                           fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
        canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 16,
                           text=str(game.score(player)), anchor="e", fill=TEXT,
                           font=("Helvetica", 15, "bold"))
        burracos = sum(1 for meld in game.melds[player] if meld.is_burraco)
        pot = "pot taken" if game.pot_taken[player] else "pot waiting"
        canvas.create_text(CONTENT_X + 10, y + 38,
                           text=f"{burracos} burraco(s) - {pot}", anchor="w",
                           fill=TEXT_DIM, font=("Helvetica", 10))
        y += 62

    canvas.create_text(CONTENT_X, y + 6,
                       text=f"Selected: {len(app.selected)} card(s)",
                       anchor="w", fill=TEXT_DIM, font=("Helvetica", 10))

    top = y + 26
    for index, key in enumerate(ACTIONS):
        app._button(CONTENT_X, top + index * 38, CONTENT_W, 32,
                    ACTION_LABELS[key], f"burraco_{key}",
                    lambda key=key: click_action(app, key),
                    primary=_is_suggested(app, key))

    sort_top = top + len(ACTIONS) * 38 + 8
    half = (CONTENT_W - 8) / 2
    for index, key in enumerate(SORTS):
        app._button(CONTENT_X + index * (half + 8), sort_top, half, 28,
                    SORT_LABELS[key], f"burraco_sort_{key}",
                    lambda key=key: _sort_and_redraw(app, key),
                    selected=(app.sort_mode == key), font_size=10)

    canvas.create_text(CONTENT_X, sort_top + 50, text="LAST MOVES", anchor="w",
                       fill=TEXT, font=("Helvetica", 9, "bold"))
    for row, line in enumerate(app.log_lines[:8]):
        canvas.create_text(CONTENT_X, sort_top + 68 + row * 16,
                           text=line[0] if isinstance(line, tuple) else line,
                           anchor="w", fill=TEXT_DIM, font=("Helvetica", 9))


def _sort_and_redraw(app, by):
    sort_hand(app, by)
    app.render()


def _is_suggested(app, key):
    """Highlight the button the rules are waiting for."""
    game = app.game
    if game.turn != HUMAN or game.game_over:
        return False
    if not game.phase.drawn:
        # Only one button is lit at a time: two gold buttons read as a fault.
        return key == "draw"
    if not game.hands[HUMAN]:
        return key == "end"
    return key == "discard" and len(app.selected) == 1


# --- clicks ---------------------------------------------------------------

def click_card(app, index):
    if app.game.turn != HUMAN or app.game.game_over:
        return
    if index in app.selected:
        app.selected.discard(index)
    else:
        app.selected.add(index)
    app.render()


def click_meld(app, index):
    """Grow one of your melds with what you have selected, or buy a wild back."""
    game = app.game
    if game.turn != HUMAN or not game.phase.drawn or game.game_over:
        return
    meld = game.melds[HUMAN][index]
    cards = _selected_cards(app)
    if not cards:
        app.say("Pick the cards to add first.")
        return

    # Clicking a meld only ever adds to it. Buying the wild card back is a
    # move of its own, on its own button: doing it as a side effect of adding
    # a card meant the same click sometimes grew the meld and sometimes
    # quietly pulled the wild out of it.
    try:
        game.extend_meld(HUMAN, meld, cards)
    except (InvalidMeld, RuntimeError) as exc:
        app.say(str(exc))
        return
    app.note(f"You add {len(cards)} card(s) to a {meld.kind}")
    app.selected.clear()
    sort_hand(app, app.sort_mode)
    app.after_move()


def click_action(app, key):
    game = app.game
    if game.game_over or game.turn != HUMAN:
        return
    try:
        if key == "draw":
            card = game.draw(HUMAN)
            app.note(f"You draw {card}")
            sort_hand(app, app.sort_mode)
        elif key == "pile":
            taken = game.take_discards(HUMAN)
            app.note(f"You take the pile ({len(taken)} cards)")
            sort_hand(app, app.sort_mode)
        elif key == "meld":
            cards = _selected_cards(app)
            meld = game.lay_meld(HUMAN, cards)
            app.note(f"You lay down a {meld.kind} of {len(meld)}")
            app.selected.clear()
            sort_hand(app, app.sort_mode)
        elif key == "discard":
            cards = _selected_cards(app)
            if len(cards) != 1:
                app.say("Select exactly one card to discard.")
                return
            game.discard(HUMAN, cards[0])
            app.note(f"You discard {cards[0]}")
            app.selected.clear()
        elif key == "swap":
            cards = _selected_cards(app)
            if len(cards) != 1:
                app.say("Select the one card the pinella is standing in for.")
                return
            for meld in game.melds[HUMAN]:
                if cards[0] in wild_stands_for(meld):
                    wild = game.substitute_wild(HUMAN, meld, cards[0])
                    app.note(f"You put the {cards[0]} in and take the {wild}")
                    app.selected.clear()
                    sort_hand(app, app.sort_mode)
                    break
            else:
                app.say(f"No meld of yours is standing on a wild card that "
                        f"the {cards[0]} could replace.")
                return
        elif key == "end":
            game.end_turn(HUMAN)
            app.note("You end the turn with an empty hand")
    except InvalidMeld as exc:
        app.say(f"Not a meld: {exc}")
        return
    except RuntimeError as exc:
        app.say(str(exc))
        return
    app.after_move()


def _selected_cards(app) -> list[Card]:
    hand = app.game.hands[HUMAN]
    return [hand[i] for i in sorted(app.selected) if i < len(hand)]


def computer_turn(app):
    """Let the opponent play its whole turn, and report it."""
    moves = burraco_ai.take_turn(app.game, AI, app.difficulty)
    for move in moves:
        app.note(f"Computer {move}")
