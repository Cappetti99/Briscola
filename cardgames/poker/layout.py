"""Where things sit on the poker table, and what the pointer is over.

Plain arithmetic, no Tkinter. Two cards in hand and five in the middle is
all the shape this game has: the board has to stay clear of both seats, the
pot and the bets have to stay readable between them, and the cards a hover
refers to are found from this file alone, never from where a card has been
moved to.
"""

from ..ui import TABLE_W

HUMAN, AI = 0, 1

CENTER_X = TABLE_W // 2

# Cards. Yours and the opponent's are the same size; the board cards are a
# little larger, because five of them have to read at a glance.
HOLE_W, HOLE_H = 78, 118
HOLE_GAP = 12
BOARD_W, BOARD_H = 86, 130
BOARD_GAP = 14
BOARD_SLOTS = 5

# Rows, top to bottom. Everything else is placed against them, and the
# gaps between them are what keeps the pot, the bets and the street label
# from landing on a card.
NAME_AI_Y = 26
HOLE_AI_Y = 44
BET_AI_Y = 196
POT_Y = 240
BOARD_Y = 264
BET_YOU_Y = 430
STREET_Y = 492
HOLE_YOU_Y = 556
NAME_YOU_Y = 700

# How far a card rises under the pointer, and how far the hit test reaches
# up to meet it there.
LIFT = 20

LOG_LINES = 9


def hole_x(index: int) -> float:
    """Left edge of the index-th card of a two-card hand, centred."""
    left = CENTER_X - (2 * HOLE_W + HOLE_GAP) / 2
    return left + index * (HOLE_W + HOLE_GAP)


def board_x(index: int) -> float:
    """Left edge of the index-th slot of the five in the middle."""
    total = BOARD_SLOTS * BOARD_W + (BOARD_SLOTS - 1) * BOARD_GAP
    return (TABLE_W - total) / 2 + index * (BOARD_W + BOARD_GAP)


def hole_slot_at(x: float, y: float, count: int, top: int) -> int | None:
    """Which of your cards the pointer is over, lifted or not.

    The band covers the lift as well as the resting place: an answer that
    moved with the card would have the lift and the pointer chasing each
    other, which is the deadlock the other tables were written to avoid.
    """
    if count <= 0 or not top - LIFT <= y <= top + HOLE_H:
        return None
    for index in reversed(range(count)):
        left = hole_x(index)
        if left <= x <= left + HOLE_W:
            return index
    return None


def bet_slot(player: int) -> tuple[float, float]:
    """Where a player's chips for this street are stacked."""
    return CENTER_X, BET_AI_Y if player == AI else BET_YOU_Y


def dealer_button(player: int) -> tuple[float, float]:
    """The button sits beside the cards of whoever holds it."""
    x = hole_x(1) + HOLE_W + 26
    return x, (HOLE_AI_Y if player == AI else HOLE_YOU_Y) + 20
