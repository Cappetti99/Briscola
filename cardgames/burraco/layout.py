"""Where things sit on the Burraco table.

Plain arithmetic, no Tkinter. Burraco lays out eleven overlapping cards and a
row of melds of differing shapes, so the sums are worth checking on their own.
"""

from ..ui import TABLE_W

HAND_W, HAND_H = 82, 124

# The fan tightens as the hand grows, down to a floor that still leaves a
# strip wide enough to read a card's corner and to click it. Past the point
# where even that floor no longer fits the table, the hand scrolls.
# Kept well clear of the window edge and of the panel: at a hairline margin
# the fan reads as though it were spilling out of the table.
HAND_MARGIN = 56
HAND_STEP_MAX = 58
HAND_STEP_MIN = 30
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
HAND_Y = 606
STOCK_X = 44
MELD_X0 = 240
PILE_X = STOCK_X + 104

RUN = "run"


def _room() -> float:
    """Table width a fan may use, once one whole card is allowed for."""
    return TABLE_W - 2 * HAND_MARGIN - HAND_W


def visible_slots(count: int) -> int:
    """How many cards can be on screen at once."""
    if count <= 1:
        return max(count, 0)
    return min(count, int(_room() // HAND_STEP_MIN) + 1)


def hand_step(count: int) -> float:
    """Gap between card left edges: as wide as the table allows."""
    shown = visible_slots(count)
    if shown <= 1:
        return HAND_STEP_MAX
    return max(HAND_STEP_MIN, min(HAND_STEP_MAX, _room() / (shown - 1)))


def clamp_scroll(count: int, first: int) -> int:
    """Keep the window of visible cards inside the hand."""
    return max(0, min(int(first), count - visible_slots(count)))


def visible_range(count: int, first: int = 0) -> range:
    first = clamp_scroll(count, first)
    return range(first, first + visible_slots(count))


def hand_x(count: int, index: int, first: int = 0) -> float | None:
    """Left edge of a card, or None when it is scrolled out of sight.

    `index` counts into the whole hand, not into what is on screen, so a
    selection survives scrolling.
    """
    shown = visible_slots(count)
    first = clamp_scroll(count, first)
    if not first <= index < first + shown:
        return None
    step = hand_step(count)
    total = (shown - 1) * step + HAND_W
    return CENTER_X - total / 2 + (index - first) * step


def hand_slot_at(x: float, y: float, count: int,
                 first: int = 0) -> int | None:
    """Which card the pointer is over, from the fan's fixed geometry.

    Only the last visible card shows its whole width; the others show one
    step of it, which is the strip a click has to land in.
    """
    if count <= 0:
        return None
    if not HAND_Y - LIFT <= y <= HAND_Y + HAND_H:
        return None
    shown = visible_slots(count)
    first = clamp_scroll(count, first)
    step = hand_step(count)
    total = (shown - 1) * step + HAND_W
    start = CENTER_X - total / 2
    if not start <= x <= start + total:
        return None
    return first + min(int((x - start) // step), shown - 1)


# Melds may not grow past their band: below it lies the hand, and cards on the
# table that a hand covers can be neither read nor added to.
MELD_SCALE_MIN = 0.55
YOUR_MELD_ROOM = HAND_Y - 20 - YOUR_MELD_Y
OPP_MELD_ROOM = STOCK_Y - 20 - OPP_MELD_Y


def _place(kinds: list[str], sizes: list[int], top: float,
           scale: float) -> list[tuple]:
    width_of = MELD_W * scale
    height_of = MELD_H * scale
    step, vstep = MELD_STEP * scale, MELD_VSTEP * scale

    boxes = []
    x, y, row_height = MELD_X0, top, 0
    for kind, size in zip(kinds, sizes):
        vertical = kind == RUN
        if vertical:
            width, height = width_of, (size - 1) * vstep + height_of
        else:
            width, height = (size - 1) * step + width_of, height_of
        if x + width > TABLE_W - 16:
            x, y, row_height = MELD_X0, y + row_height + 14 * scale, 0
        boxes.append((x, y, width, height, vertical))
        x += width + 20 * scale
        row_height = max(row_height, height)
    return boxes


def meld_boxes(kinds: list[str], sizes: list[int], top: float,
               room: float | None = None) -> tuple[list[tuple], float]:
    """Place a row of melds, and say how much they had to shrink to fit.

    Runs stand up and sets lie down, so the boxes differ in shape and the row
    wraps when it runs out of table. If the whole lot is taller than the band
    allows, the cards shrink until it fits — smaller cards also fit more to a
    row, so a second pass often wins back a row as well.
    """
    scale = 1.0
    boxes = _place(kinds, sizes, top, scale)
    if not room or not boxes:
        return boxes, scale

    for _pass in range(3):
        needed = max(box[1] + box[3] for box in boxes) - top
        if needed <= room:
            break
        scale = max(MELD_SCALE_MIN, scale * room / needed)
        boxes = _place(kinds, sizes, top, scale)
    return boxes, scale


def card_position(box: tuple, offset: int,
                  scale: float = 1.0) -> tuple[float, float]:
    """Where the offset-th card of a meld goes inside its box."""
    x, y, _width, _height, vertical = box
    if vertical:
        return x, y + offset * MELD_VSTEP * scale
    return x + offset * MELD_STEP * scale, y
