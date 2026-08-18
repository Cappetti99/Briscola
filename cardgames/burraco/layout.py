"""Where things sit on the Burraco table.

Plain arithmetic, no Tkinter. Burraco lays out eleven overlapping cards and a
row of melds of differing shapes, so the sums are worth checking on their own.
"""

from ..ui import TABLE_W

HAND_W, HAND_H = 82, 124
HAND_STEP = 58
LIFT = 20
HOVER_LIFT = 10
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

RUN = "run"


def hand_x(count: int, index: int) -> float:
    """Left edge of a card in the fan. Cards overlap, so the step is small."""
    total = (count - 1) * HAND_STEP + HAND_W
    return CENTER_X - total / 2 + index * HAND_STEP


def hand_slot_at(x: float, y: float, count: int) -> int | None:
    """Which card the pointer is over, from the fan's fixed geometry.

    Only the last card shows its whole width; the others show one step of it,
    which is the strip a click has to land in.
    """
    if count <= 0:
        return None
    if not HAND_Y - LIFT <= y <= HAND_Y + HAND_H:
        return None
    total = (count - 1) * HAND_STEP + HAND_W
    start = CENTER_X - total / 2
    if not start <= x <= start + total:
        return None
    return min(int((x - start) // HAND_STEP), count - 1)


def meld_boxes(kinds: list[str], sizes: list[int], top: float) -> list[tuple]:
    """Place a row of melds: (x, y, width, height, vertical) for each.

    Runs stand up and sets lie down, so the boxes differ in shape and the row
    wraps when it runs out of table.
    """
    boxes = []
    x, y, row_height = MELD_X0, top, 0
    for kind, size in zip(kinds, sizes):
        vertical = kind == RUN
        if vertical:
            width, height = MELD_W, (size - 1) * MELD_VSTEP + MELD_H
        else:
            width, height = (size - 1) * MELD_STEP + MELD_W, MELD_H
        if x + width > TABLE_W - 16:
            x, y, row_height = MELD_X0, y + row_height + 14, 0
        boxes.append((x, y, width, height, vertical))
        x += width + 20
        row_height = max(row_height, height)
    return boxes


def card_position(box: tuple, offset: int) -> tuple[float, float]:
    """Where the offset-th card of a meld goes inside its box."""
    x, y, _width, _height, vertical = box
    if vertical:
        return x, y + offset * MELD_VSTEP
    return x + offset * MELD_STEP, y
