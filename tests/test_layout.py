"""Table geometry, checked without opening a window.

Everything here is plain arithmetic imported from the layout modules, so this
suite needs no display and runs in a blink. It covers what used to need a Tk
window: where a card sits, which card the pointer is over, and how a row of
melds is placed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.briscola import layout as briscola
from cardgames.burraco import layout as burraco
from cardgames.ui import TABLE_W


# --- Briscola -------------------------------------------------------------

def test_a_briscola_hand_is_centred():
    for count in (1, 2, 3):
        left = briscola.hand_x(count, 0)
        right = briscola.hand_x(count, count - 1) + briscola.CARD_W
        assert abs((left + right) / 2 - briscola.CENTER_X) < 0.5, count


def test_the_pointer_finds_each_briscola_card():
    for count in (1, 2, 3):
        for index in range(count):
            middle = briscola.hand_x(count, index) + briscola.CARD_W / 2
            found = briscola.hand_slot_at(middle, briscola.PLAYER_HAND_Y + 40,
                                          count)
            assert found == index, (count, index, found)


def test_the_gaps_between_briscola_cards_belong_to_nobody():
    left = briscola.hand_x(3, 0) + briscola.CARD_W + briscola.HAND_GAP / 2
    assert briscola.hand_slot_at(left, briscola.PLAYER_HAND_Y + 40, 3) is None


def test_the_briscola_hit_test_ignores_the_lift():
    """The regression that once locked the window up.

    If the answer changed as a card rose, the lift and the pointer would
    chase each other: the card leaves the pointer, drops back under it, and
    the two spin at full tilt while clicks go unheard.
    """
    for offset in (0, 4, briscola.CARD_H - 1, -briscola.LIFT + 1):
        y = briscola.PLAYER_HAND_Y + offset
        middle = briscola.hand_x(3, 1) + briscola.CARD_W / 2
        assert briscola.hand_slot_at(middle, y, 3) == 1, offset


def test_above_and_below_the_briscola_hand_is_nothing():
    middle = briscola.hand_x(3, 1) + briscola.CARD_W / 2
    above = briscola.PLAYER_HAND_Y - briscola.LIFT - 1
    below = briscola.PLAYER_HAND_Y + briscola.CARD_H + 1
    assert briscola.hand_slot_at(middle, above, 3) is None
    assert briscola.hand_slot_at(middle, below, 3) is None


def test_the_two_table_slots_do_not_overlap():
    (ai_x, _ai_y) = briscola.table_slot(briscola.AI)
    (you_x, _you_y) = briscola.table_slot(briscola.HUMAN)
    assert ai_x + briscola.CARD_W <= you_x


# --- Burraco --------------------------------------------------------------

def test_a_burraco_fan_is_centred_and_overlaps():
    for count in (1, 3, 11, 22):
        left = burraco.hand_x(count, 0)
        right = burraco.hand_x(count, count - 1) + burraco.HAND_W
        assert abs((left + right) / 2 - burraco.CENTER_X) < 0.5, count
    assert burraco.HAND_STEP < burraco.HAND_W, "the fan is meant to overlap"


def test_the_pointer_finds_each_card_of_a_full_burraco_hand():
    """Every card must be reachable, including under the overlap."""
    for count in (1, 3, 11, 22):
        for index in range(count):
            # The visible strip of a card is one step wide, except the last.
            spot = burraco.hand_x(count, index) + burraco.HAND_STEP / 2
            found = burraco.hand_slot_at(spot, burraco.HAND_Y + 40, count)
            assert found == index, (count, index, found)


def test_the_burraco_hit_test_ignores_the_lift():
    spot = burraco.hand_x(11, 4) + burraco.HAND_STEP / 2
    for offset in (0, 4, burraco.HAND_H - 1, -burraco.LIFT + 1):
        assert burraco.hand_slot_at(spot, burraco.HAND_Y + offset, 11) == 4


def test_off_the_burraco_fan_is_nothing():
    assert burraco.hand_slot_at(0, burraco.HAND_Y + 40, 11) is None
    assert burraco.hand_slot_at(TABLE_W, burraco.HAND_Y + 40, 11) is None
    spot = burraco.hand_x(11, 4)
    assert burraco.hand_slot_at(spot, burraco.HAND_Y - burraco.LIFT - 1, 11) is None


def test_an_empty_hand_has_no_slots():
    assert burraco.hand_slot_at(burraco.CENTER_X, burraco.HAND_Y, 0) is None
    assert briscola.hand_slot_at(briscola.CENTER_X, briscola.PLAYER_HAND_Y,
                                 0) is None


# --- melds on the table ---------------------------------------------------

def test_runs_stand_up_and_sets_lie_down():
    (run, other) = burraco.meld_boxes(["run", "set"], [5, 5], 400)
    assert run[4] is True and other[4] is False
    assert run[2] == burraco.MELD_W, "a run is one card wide"
    assert run[3] > other[3], "and taller than a set of the same size"


def test_meld_boxes_do_not_overlap():
    kinds = ["run", "set", "run", "set", "run"]
    sizes = [4, 3, 7, 5, 3]
    boxes = burraco.meld_boxes(kinds, sizes, 400)
    for first, second in zip(boxes, boxes[1:]):
        same_row = first[1] == second[1]
        if same_row:
            assert first[0] + first[2] <= second[0], (first, second)


def test_a_long_row_of_melds_wraps():
    boxes = burraco.meld_boxes(["set"] * 8, [4] * 8, 400)
    rows = {box[1] for box in boxes}
    assert len(rows) > 1, "eight melds cannot fit on one row"
    for box in boxes:
        assert box[0] + box[2] <= TABLE_W, "and none runs off the table"


def test_cards_in_a_meld_step_the_right_way():
    box = burraco.meld_boxes(["run"], [4], 400)[0]
    first = burraco.card_position(box, 0)
    second = burraco.card_position(box, 1)
    assert first[0] == second[0], "a run steps downward"
    assert second[1] > first[1]

    box = burraco.meld_boxes(["set"], [4], 400)[0]
    first = burraco.card_position(box, 0)
    second = burraco.card_position(box, 1)
    assert first[1] == second[1], "a set steps sideways"
    assert second[0] > first[0]


def test_a_meld_shows_enough_of_each_card_to_read_it():
    assert burraco.MELD_VSTEP >= 14, "a run must show its corner index"
    assert burraco.MELD_STEP >= 18, "and a set must show its rank"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print("\nall good" if not failures else f"\n{failures} test(s) failed")
    sys.exit(1 if failures else 0)
