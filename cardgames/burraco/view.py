"""The Burraco table: what is drawn, and what a click on it means.

Written as functions over the shell window rather than a class of its own, so
Briscola and Burraco share one window, one menu and one record file.
"""

from .. import cardart
from ..cards import Card
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_EDGE, PANEL_BG,
                  PANEL_CARD, TABLE_H, TABLE_W, TEXT, TEXT_DIM)
from . import ai as burraco_ai
from .engine import (AI, HUMAN, InvalidMeld, Stranded, is_wild,
                     wild_stands_for)

from .layout import (BACK_H, BACK_STEP, BACK_W, CENTER_X, HAND_H, HAND_W,
                     HAND_Y, HOVER_LIFT, LIFT, MELD_H, MELD_W, MELD_X0,
                     OPP_HAND_Y, OPP_MELD_Y, PILE_X, STOCK_X, STOCK_Y,
                     OPP_MELD_ROOM, YOUR_MELD_ROOM, YOUR_MELD_Y,
                     card_position, clamp_scroll, hand_slot_at, hand_x,
                     meld_boxes, visible_range, visible_slots)

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
    _draw_melds(app, game, HUMAN, YOUR_MELD_Y, YOUR_MELD_ROOM)
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
    _draw_melds(app, game, AI, OPP_MELD_Y, OPP_MELD_ROOM)


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


def _draw_melds(app, game, player, top, room):
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

    boxes, scale = meld_boxes([meld.kind for meld in melds],
                              [len(meld) for meld in melds], top, room)
    for index, (meld, box) in enumerate(zip(melds, boxes)):
        x, y, width, _height, _vertical = box
        tag = f"meld{player}_{index}"
        for offset, card in enumerate(meld.cards):
            card_x, card_y = card_position(box, offset, scale)
            cardart.draw_card(canvas, card_x, card_y,
                              MELD_W * scale, MELD_H * scale, card, tags=(tag,))
        if meld.is_burraco:
            canvas.create_text(x + width / 2, y - 7,
                               text="BURRACO" + ("" if meld.is_clean else " *"),
                               fill=ACCENT,
                               font=("Helvetica", max(7, int(9 * scale)), "bold"))
        if player == HUMAN:
            canvas.tag_bind(tag, "<Button-1>",
                            lambda _e, i=index: click_meld(app, i))


def _draw_hand(app, game):
    canvas = app.canvas
    hand = game.hands[HUMAN]
    count = len(hand)
    app.hand_first = clamp_scroll(count, app.hand_first)

    for index in visible_range(count, app.hand_first):
        x = hand_x(count, index, app.hand_first)
        card = hand[index]
        y = HAND_Y - (LIFT if index in app.selected
                      else HOVER_LIFT if index == app.hovered else 0)
        tag = f"hand{index}"
        cardart.draw_card(canvas, x, y, HAND_W, HAND_H, card, tags=(tag,),
                          highlight=index in app.selected)
        canvas.tag_bind(tag, "<Button-1>",
                        lambda _e, i=index: click_card(app, i))

    if visible_slots(count) < count:
        _draw_scroll_arrows(app, count)

    canvas.create_text(TABLE_W - 12, HAND_Y - 14,
                       text=f"YOU  {count} cards", anchor="e",
                       fill=FELT_EDGE, font=("Helvetica", 10, "bold"))


def _draw_scroll_arrows(app, count):
    """Only drawn when the hand is too wide to show at once."""
    canvas = app.canvas
    shown = visible_slots(count)
    middle = HAND_Y + HAND_H / 2
    for key, x, direction in (("left", 16, -1), ("right", TABLE_W - 46, 1)):
        first = app.hand_first
        spent = (direction < 0 and first == 0) or \
                (direction > 0 and first + shown >= count)
        colour = FELT_EDGE if spent else ACCENT
        tag = f"scroll_{key}"
        tip = x if direction < 0 else x + 30
        back = x + 30 if direction < 0 else x
        canvas.create_polygon(tip, middle, back, middle - 22, back, middle + 22,
                              fill=colour, outline=colour, tags=(tag,))
        if not spent:
            canvas.tag_bind(tag, "<Button-1>",
                            lambda _e, d=direction: scroll_hand(app, d * 3))
    canvas.create_text(CENTER_X, HAND_Y + HAND_H + 14,
                       text=f"cards {app.hand_first + 1}-"
                            f"{app.hand_first + shown} of {count}"
                            "   -   drag the wheel or the arrows",
                       fill=TEXT_DIM, font=("Helvetica", 10))


def pointed_card(app, x, y):
    """The card under the pointer, once the window agrees we may pick one."""
    game = app.game
    if not game or app.overlay is not None or game.turn != HUMAN:
        return None
    return hand_slot_at(x, y, len(game.hands[HUMAN]), app.hand_first)


def on_motion(app, x, y):
    """Lift the card under the pointer, and put the last one back down."""
    index = pointed_card(app, x, y)
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
    app.hand_first = 0


def scroll_hand(app, by):
    count = len(app.game.hands[HUMAN])
    moved = clamp_scroll(count, app.hand_first + by)
    if moved != app.hand_first:
        app.hand_first = moved
        app.hovered = None
        app.render()


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
    except (InvalidMeld, Stranded, RuntimeError) as exc:
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
    except Stranded as exc:
        app.say(str(exc).capitalize() + ".")
        return
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
