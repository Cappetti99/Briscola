"""The Tressette table: what is drawn, and what a click on it means.

Functions over the shell window, the way Burraco and Scopa are written. The
one thing this table has to say that the others do not is which cards you are
allowed to play: following suit is compulsory, so the cards that would break
that rule are drawn greyed out rather than being refused after the fact.
"""

from .. import cardart, ui
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_DARK, FELT_EDGE,
                  PANEL_BG, PANEL_CARD, TABLE_H, TABLE_W, TEXT, TEXT_DIM)
from . import ai as tressette_ai
from .engine import (AI, HUMAN, TOTAL_THIRDS, TRICKS_PER_GAME, MustFollowSuit)

from .layout import (BACK_H, BACK_W, CENTER_X, DRAWN_H, DRAWN_W, HAND_H,
                     HAND_W, HAND_Y, HOVER_LIFT, LOG_LINES, OPP_HAND_Y,
                     DIM_DROP, STOCK_X, STOCK_Y, TABLE_CARD_H, TABLE_CARD_W,
                     TABLE_Y,
                     drawn_slot, hand_slot_at, hand_x, opponent_x, table_slot)

SORTS = ("suit", "rank")
SORT_LABELS = {"suit": "Sort by suit", "rank": "Sort by rank"}


# --- drawing --------------------------------------------------------------

def draw(app):
    game = app.game
    canvas = app.canvas
    canvas.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")
    canvas.create_oval(CENTER_X - 210, TABLE_Y - 54, CENTER_X + 210,
                       TABLE_Y + TABLE_CARD_H + 116, fill=FELT_DARK,
                       outline="")

    _draw_opponent(app, game)
    _draw_stock(app, game)
    _draw_table(app, game)
    _draw_hand(app, game)


def _draw_opponent(app, game):
    canvas = app.canvas
    count = len(game.hands[AI])
    for index in range(count):
        cardart.draw_card_back(canvas, opponent_x(count, index), OPP_HAND_Y,
                               BACK_W, BACK_H)
    canvas.create_text(TABLE_W - 12, OPP_HAND_Y + BACK_H / 2,
                       text=f"COMPUTER  {count} cards", anchor="e",
                       fill=FELT_EDGE, font=ui.font(10, "bold"))


def _draw_stock(app, game):
    canvas = app.canvas
    if game.stock:
        cardart.draw_card_back(canvas, STOCK_X, STOCK_Y, HAND_W, HAND_H)
        canvas.create_text(STOCK_X + HAND_W / 2, STOCK_Y + HAND_H + 16,
                           text=f"{game.cards_left} in stock", fill=TEXT_DIM,
                           font=ui.font(10))
    else:
        cardart.draw_placeholder(canvas, STOCK_X, STOCK_Y, HAND_W, HAND_H,
                                 "stock\nempty")

    # Both draws are face up: with a stock this small, what the other side
    # picked up is part of what either player is entitled to count.
    for player, label in ((AI, "they drew"), (HUMAN, "you drew")):
        x, y = drawn_slot(player)
        card = game.drawn.get(player)
        if card is None:
            continue
        cardart.draw_card(app.canvas, x, y, DRAWN_W, DRAWN_H, card)
        canvas.create_text(x + DRAWN_W / 2, y - 10, text=label,
                           fill=TEXT_DIM, font=ui.font(9))


def _draw_table(app, game):
    canvas = app.canvas
    played = {player for player, _card in game.table}
    for player in (AI, HUMAN):
        if player not in played:
            x, y = table_slot(player)
            cardart.draw_placeholder(canvas, x, y, TABLE_CARD_W, TABLE_CARD_H)
    if not game.table:
        return

    winner = game.trick_winner() if game.trick_complete else None
    for order, (player, card) in enumerate(game.table):
        x, y = table_slot(player)
        cardart.draw_card(canvas, x, y, TABLE_CARD_W, TABLE_CARD_H, card,
                          tags=(f"table{player}",),
                          highlight=(player == winner))
        if order == 0 and not game.trick_complete:
            canvas.create_text(x + TABLE_CARD_W / 2, y - 14, text="led",
                               fill=TEXT_DIM, font=ui.font(10))


def _draw_hand(app, game):
    canvas = app.canvas
    hand = game.hands[HUMAN]
    count = len(hand)
    legal = set(game.legal_cards(HUMAN)) if game.turn == HUMAN else set(
        range(count))
    for index in range(count):
        x = hand_x(count, index)
        y = HAND_Y - (HOVER_LIFT if index == app.hovered
                      and index in legal else 0)
        cardart.draw_card(canvas, x, y, HAND_W, HAND_H, hand[index],
                          tags=(f"hand{index}",))
        if index not in legal:
            # Following suit is the rule of the game, so the cards it rules
            # out are shown as unavailable rather than refused after a click.
            # They are shaded *and* sit lower: shading alone is a pattern that
            # a PostScript export drops, and the drop reads at a glance.
            canvas.create_rectangle(x, y, x + HAND_W, y + HAND_H,
                                    fill="#06251a", stipple="gray50",
                                    outline="", tags=(f"hand{index}",))
            canvas.move(f"hand{index}", 0, DIM_DROP)
    if game.turn == HUMAN and len(legal) < count:
        canvas.create_text(CENTER_X, HAND_Y - 30,
                           text=f"you have to follow {game.lead_card.suit}",
                           fill=ACCENT, font=ui.font(11, "bold"))
    canvas.create_text(TABLE_W - 12, HAND_Y + HAND_H / 2, text="YOU",
                       anchor="e", fill=FELT_EDGE, font=ui.font(10, "bold"))


def pointed_card(app, x, y):
    game = app.game
    if not game or app.overlay is not None or game.turn != HUMAN:
        return None
    return hand_slot_at(x, y, len(game.hands[HUMAN]))


def on_motion(app, x, y):
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
    canvas.create_text(CONTENT_X, 26, text="TRESSETTE", anchor="w",
                       fill=ACCENT, font=ui.font(19, "bold"))
    match = app.match
    if match is None or match.single_hand:
        subtitle = "you vs. the computer  -  one deal"
    else:
        subtitle = f"match to {match.target}  -  deal {match.hands + 1}"
    canvas.create_text(CONTENT_X, 48, text=subtitle, anchor="w", fill=TEXT_DIM,
                       font=ui.font(11))
    app._panel_link(CONTENT_X + CONTENT_W, 26, "menu", "back", app.show_menu)

    y = 74
    for player, title in ((HUMAN, "YOU"), (AI, "COMPUTER")):
        cardart.round_rect(canvas, CONTENT_X, y, CONTENT_X + CONTENT_W, y + 62,
                           8, fill=PANEL_CARD, outline="")
        canvas.create_text(CONTENT_X + 10, y + 16, text=title, anchor="w",
                           fill=TEXT_DIM, font=ui.font(9, "bold"))
        canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 18,
                           text=str(game.points(player)), anchor="e",
                           fill=TEXT, font=ui.font(17, "bold"))
        # The thirds are what the game is actually counted in, and the whole
        # points are what is left once the remainder is thrown away.
        canvas.create_text(CONTENT_X + 10, y + 38,
                           text=f"{game.thirds[player]} thirds"
                                + (f"  +{game.bonus[player]} declared"
                                   if game.bonus[player] else ""),
                           anchor="w", fill=TEXT_DIM, font=ui.font(10))
        if match is not None and not match.single_hand:
            canvas.create_text(CONTENT_X + CONTENT_W - 10, y + 40,
                               text=f"match {match.totals[player]}", anchor="e",
                               fill=ACCENT, font=ui.font(10, "bold"))
        y += 72

    declared = game.declared[HUMAN]
    canvas.create_text(CONTENT_X, y + 6,
                       text=("You declared: "
                             + ", ".join(str(one) for one in declared)
                             if declared else "You declared nothing"),
                       anchor="w", fill=TEXT_DIM, font=ui.font(10),
                       width=CONTENT_W)

    # Counted in thirds, because that is what is actually still on the table:
    # the declarations are already whole points and are not out there to win.
    canvas.create_text(CONTENT_X, y + 40,
                       text=f"Tricks: {game.tricks_played}/{TRICKS_PER_GAME}"
                            f"   Still to win: "
                            f"{TOTAL_THIRDS - sum(game.thirds)} thirds",
                       anchor="w", fill=TEXT_DIM, font=ui.font(10))

    top = y + 68
    half = (CONTENT_W - 8) / 2
    for index, key in enumerate(SORTS):
        app._button(CONTENT_X + index * (half + 8), top, half, 28,
                    SORT_LABELS[key], f"tressette_sort_{key}",
                    lambda key=key: sort_and_redraw(app, key),
                    selected=(app.sort_mode == key), font_size=10)

    top += 40
    app._panel_button(top, "New game", "new", app.new_match, primary=True)
    app._panel_button(top + 40, "Statistics", "stats", app.show_statistics)
    app._panel_button(top + 76,
                      f"Difficulty: {tressette_ai.LEVEL_LABELS[app.difficulty]}",
                      "level", app.cycle_difficulty)
    app._panel_button(top + 112, "Rules", "rules", app.show_rules)

    canvas.create_text(CONTENT_X, top + 162, text="LAST TRICKS", anchor="w",
                       fill=TEXT, font=ui.font(9, "bold"))
    for row, line in enumerate(app.log_lines[:LOG_LINES]):
        left, right = line if isinstance(line, tuple) else (line, "")
        canvas.create_text(CONTENT_X, top + 180 + row * 17, text=left,
                           anchor="w", fill=TEXT_DIM, font=ui.font(10))
        canvas.create_text(CONTENT_X + CONTENT_W, top + 180 + row * 17,
                           text=right, anchor="e", fill=TEXT,
                           font=ui.font(10, "bold"))


# --- clicks ---------------------------------------------------------------

def click_at(app, x, y):
    """Route a click by the fixed slot geometry, never by the item under it."""
    index = pointed_card(app, x, y)
    if index is not None:
        play(app, index)
        return False
    return True             # nothing was hit, so the click can skip a pause


def play(app, index):
    game = app.game
    if game is None or game.game_over or game.turn != HUMAN:
        return
    if app.overlay is not None or index >= len(game.hands[HUMAN]):
        return
    card = game.hands[HUMAN][index]
    try:
        game.play_card(HUMAN, index)
    except MustFollowSuit as exc:
        # Not capitalize(): it would lower-case the name of the suit.
        said = str(exc)
        app.say(said[0].upper() + said[1:] + ".")
        return
    except RuntimeError as exc:
        app.say(str(exc))
        return
    app.hovered = None
    app._set_status(f"You play {card}.")
    app.tressette_advance()


def sort_hand(app, by: str) -> None:
    """Put the hand in order. The card under the pointer has moved, so the
    hover is dropped rather than left pointing at whatever slid into place."""
    app.sort_mode = by
    app.game.sort_hand(HUMAN, by)
    app.hovered = None


def sort_and_redraw(app, by: str) -> None:
    sort_hand(app, by)
    app.render()


def describe_trick(result) -> tuple[str, str]:
    """One line of the trick log: what was played, and what it was worth."""
    lead, follow = result.lead[1], result.follow[1]
    left = f"{lead.short()} / {follow.short()}"
    return left, f"+{result.thirds}"


def computer_card(app):
    """The card the opponent plays, chosen at the level in force."""
    game = app.game
    index = tressette_ai.choose_card(game, AI, app.difficulty)
    card = game.hands[AI][index]
    game.play_card(AI, index)
    return card
