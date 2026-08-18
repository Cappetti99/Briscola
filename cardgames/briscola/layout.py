"""Where things sit on the Briscola table, and what the pointer is over.

Plain arithmetic, no Tkinter: the window draws from these numbers and the
tests can check them without opening anything.
"""

from ..ui import TABLE_W

CARD_W, CARD_H = 106, 162
HAND_GAP = 18
LIFT = 22
CENTER_X = TABLE_W // 2
AI_HAND_Y = 24
TABLE_Y = 250
PLAYER_HAND_Y = 580
STOCK_X, STOCK_Y = 26, 300
LOG_LINES = 10

HUMAN, AI = 0, 1


def hand_x(count: int, index: int) -> float:
    """Left edge of the index-th card in a hand of `count`, centred."""
    total = count * CARD_W + (count - 1) * HAND_GAP
    return CENTER_X - total / 2 + index * (CARD_W + HAND_GAP)


def table_slot(player: int) -> tuple[float, float]:
    if player == AI:
        return CENTER_X - CARD_W - 18, TABLE_Y - 10
    return CENTER_X + 18, TABLE_Y + 26


def hand_slot_at(x: float, y: float, count: int) -> int | None:
    """Which card the pointer is over, lifted or not.

    Deliberately independent of the hover lift. An answer that changed as a
    card moved would have the lift and the pointer chasing each other: the
    card rises out from under the pointer, Tk reports a leave, the card drops
    back under it, and the two spin at full tilt while clicks go unheard.
    """
    if count <= 0:
        return None
    if not PLAYER_HAND_Y - LIFT <= y <= PLAYER_HAND_Y + CARD_H:
        return None
    for index in range(count):
        left = hand_x(count, index)
        if left <= x <= left + CARD_W:
            return index
    return None
