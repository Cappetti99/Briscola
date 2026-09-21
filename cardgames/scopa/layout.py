"""Where things sit on the Scopa table, and what the pointer is over.

Plain arithmetic, no Tkinter. Three cards in hand are easy; the table is not,
because it grows as cards are left on it and has to stay readable and
clickable however many end up there.
"""

from ..ui import TABLE_W

CARD_W, CARD_H = 104, 158
BACK_W, BACK_H = 78, 118
HAND_GAP = 22
LIFT = 22
HOVER_LIFT = 10
# How far a picked table card rises. It is drawn lifted and hit-tested
# where it was, so the lift can never move it out of its own click zone.
PICK_LIFT = 8

CENTER_X = TABLE_W // 2
OPP_HAND_Y = 22
HAND_Y = 566

# The table sits between the two hands, with the capture piles either side.
TABLE_MID = 348
TABLE_CARD_W, TABLE_CARD_H = 78, 118
TABLE_GAP = 12
TABLE_ROW_GAP = 14
TABLE_MARGIN = 168          # room for a pile on the left and one on the right
TABLE_ROWS = 3

PILE_X = 26
PILE_W, PILE_H = 76, 116
OPP_PILE_Y = 96
YOUR_PILE_Y = 396

HUMAN, AI = 0, 1


def _room() -> float:
    return TABLE_W - 2 * TABLE_MARGIN


def hand_x(count: int, index: int) -> float:
    """Left edge of the index-th card in a hand of `count`, centred."""
    total = count * CARD_W + (count - 1) * HAND_GAP
    return CENTER_X - total / 2 + index * (CARD_W + HAND_GAP)


def hand_slot_at(x: float, y: float, count: int) -> int | None:
    """Which card in your hand the pointer is over, lifted or not.

    Worked out from the fixed slots rather than from where a card has been
    moved to, so a lifted card cannot move out from under the pointer and
    start a fight between the lift and the hover.
    """
    if count <= 0:
        return None
    if not HAND_Y - LIFT <= y <= HAND_Y + CARD_H:
        return None
    for index in range(count):
        left = hand_x(count, index)
        if left <= x <= left + CARD_W:
            return index
    return None


def opponent_hand_x(count: int, index: int) -> float:
    total = count * BACK_W + (count - 1) * HAND_GAP
    return CENTER_X - total / 2 + index * (BACK_W + HAND_GAP)


def table_boxes(count: int) -> list[tuple[float, float, float, float]]:
    """Where the table cards sit: rows first, and only then a smaller card.

    The table usually holds four to eight cards, which fit across in one row.
    It can climb much higher when neither side can take anything, so the rows
    fill up to a limit and after that the cards shrink — the same order of
    preference the melds in Burraco use, and for the same reason: a smaller
    card is still readable, a card off the edge of the table is not.
    """
    if count <= 0:
        return []
    per_row = min(count, int((_room() + TABLE_GAP) // (TABLE_CARD_W + TABLE_GAP)))
    per_row = max(1, per_row)
    rows = -(-count // per_row)
    if rows > TABLE_ROWS:
        rows = TABLE_ROWS
        per_row = -(-count // rows)

    # The gaps keep their size when the cards shrink, so the card width is
    # what is left of the room once they are paid for. Scaling both together
    # overshot: the row still ran off the table it was meant to fit.
    card_w = min(TABLE_CARD_W,
                 (_room() - (per_row - 1) * TABLE_GAP) / per_row)
    card_h = TABLE_CARD_H * card_w / TABLE_CARD_W

    block_h = rows * card_h + (rows - 1) * TABLE_ROW_GAP
    top = TABLE_MID - block_h / 2

    boxes = []
    for index in range(count):
        row, column = divmod(index, per_row)
        in_row = min(per_row, count - row * per_row)
        row_w = in_row * card_w + (in_row - 1) * TABLE_GAP
        x = CENTER_X - row_w / 2 + column * (card_w + TABLE_GAP)
        y = top + row * (card_h + TABLE_ROW_GAP)
        boxes.append((x, y, card_w, card_h))
    return boxes


def table_slot_at(x: float, y: float, count: int) -> int | None:
    """Which table card the pointer is over, for picking what to take."""
    for index, (left, top, width, height) in enumerate(table_boxes(count)):
        if left <= x <= left + width and top <= y <= top + height:
            return index
    return None
