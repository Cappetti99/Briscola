"""Where things sit on the Tressette table, and what the pointer is over.

Plain arithmetic, no Tkinter. Ten cards in hand is the shape that drives all
of it: they have to fan, they have to stay clickable, and the two cards on
the table have to stay clear of them.
"""

from ..ui import TABLE_W

HAND_W, HAND_H = 92, 140
BACK_W, BACK_H = 62, 94
TABLE_CARD_W, TABLE_CARD_H = 100, 152
LIFT = 22
HOVER_LIFT = 12
# How far a card the rules forbid sits below the others.
DIM_DROP = 10

CENTER_X = TABLE_W // 2
OPP_HAND_Y = 16
TABLE_Y = 296
HAND_Y = 566
STOCK_X, STOCK_Y = 26, 300
DRAWN_W, DRAWN_H = 58, 88
# On the right, where the felt is empty: beside the stock they landed on its
# own count, and there is no room between the stock and the hand.
DRAWN_X = TABLE_W - 138
DRAWN_Y = (398, 152)          # yours below, theirs above
LOG_LINES = 9

# The fan tightens as the hand grows, but never past the point where a card
# shows less than a readable strip of itself.
HAND_MARGIN = 50
HAND_STEP_MAX = 96
OPP_STEP = 56

HUMAN, AI = 0, 1


def hand_step(count: int) -> float:
    """Gap between the left edges of two cards in hand."""
    if count <= 1:
        return HAND_STEP_MAX
    room = TABLE_W - 2 * HAND_MARGIN - HAND_W
    return min(HAND_STEP_MAX, room / (count - 1))


def hand_x(count: int, index: int) -> float:
    """Left edge of the index-th card of a hand of `count`, centred."""
    step = hand_step(count)
    total = (count - 1) * step + HAND_W
    return CENTER_X - total / 2 + index * step


def hand_slot_at(x: float, y: float, count: int) -> int | None:
    """Which card the pointer is over, lifted or not.

    Scanned from the right, because the cards overlap left to right and the
    one on top is the one a click should reach. Deliberately independent of
    the hover lift: an answer that moved with the card would have the lift
    and the pointer chasing each other.
    """
    if count <= 0:
        return None
    # The band covers the drop as well as the lift: a card the rules forbid
    # is drawn lower, and clicking it has to reach it to say why it cannot
    # be played.
    if not HAND_Y - LIFT <= y <= HAND_Y + HAND_H + DIM_DROP:
        return None
    for index in reversed(range(count)):
        left = hand_x(count, index)
        if left <= x <= left + HAND_W:
            return index
    return None


def opponent_x(count: int, index: int) -> float:
    total = (count - 1) * OPP_STEP + BACK_W
    return CENTER_X - total / 2 + index * OPP_STEP


def table_slot(player: int) -> tuple[float, float]:
    """Where each player's card of the current trick lands."""
    if player == AI:
        return CENTER_X - TABLE_CARD_W - 18, TABLE_Y - 10
    return CENTER_X + 18, TABLE_Y + 26


def drawn_slot(player: int) -> tuple[float, float]:
    """The card each side drew, shown face up because the rules say so."""
    return DRAWN_X, DRAWN_Y[player]
