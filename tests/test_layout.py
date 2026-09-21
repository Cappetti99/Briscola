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
from cardgames.scopa import layout as scopa
from cardgames.tressette import layout as tressette
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
    for count in (1, 3, 11, 22, 28):
        shown = burraco.visible_slots(count)
        left = burraco.hand_x(count, 0)
        right = burraco.hand_x(count, shown - 1) + burraco.HAND_W
        assert abs((left + right) / 2 - burraco.CENTER_X) < 0.5, count
    assert burraco.hand_step(11) < burraco.HAND_W, "the fan is meant to overlap"


def test_a_big_hand_never_runs_off_the_table():
    """Eleven cards plus a pot plus a pile is a wide hand.

    At a fixed step it went off both edges — seventeen cards spanned 1010
    pixels of a 940 pixel table — and the cards on the ends could be neither
    seen nor clicked.
    """
    for count in range(1, 41):
        shown = burraco.visible_slots(count)
        left = burraco.hand_x(count, 0)
        right = burraco.hand_x(count, shown - 1) + burraco.HAND_W
        assert left >= 0, f"{count} cards start off the table at {left}"
        assert right <= TABLE_W, f"{count} cards end off the table at {right}"


def test_the_fan_tightens_before_it_scrolls():
    assert burraco.hand_step(11) == burraco.HAND_STEP_MAX, "a small hand is airy"

    steps = [burraco.hand_step(count) for count in range(1, 41)]
    for wider, tighter in zip(steps, steps[1:]):
        assert tighter <= wider, "the fan only ever closes up"
    assert min(steps) >= burraco.HAND_STEP_MIN, "and never past the floor"

    # Scrolling is the last resort: it starts only once tightening has run out.
    scrolls_at = next(n for n in range(1, 41) if burraco.visible_slots(n) < n)
    assert burraco.hand_step(scrolls_at) < burraco.HAND_STEP_MIN + 3
    assert burraco.visible_slots(scrolls_at - 1) == scrolls_at - 1


def test_the_pointer_finds_each_card_of_a_full_burraco_hand():
    """Every card must be reachable, including under the overlap."""
    for count in (1, 3, 11, 22, 28):
        step = burraco.hand_step(count)
        for index in range(burraco.visible_slots(count)):
            # The visible strip of a card is one step wide, except the last.
            spot = burraco.hand_x(count, index) + step / 2
            found = burraco.hand_slot_at(spot, burraco.HAND_Y + 40, count)
            assert found == index, (count, index, found)


def test_scrolling_walks_the_whole_hand():
    count = 40
    shown = burraco.visible_slots(count)
    step = burraco.hand_step(count)
    reachable = set()
    for first in range(0, count - shown + 1):
        for index in burraco.visible_range(count, first):
            spot = burraco.hand_x(count, index, first) + step / 2
            found = burraco.hand_slot_at(spot, burraco.HAND_Y + 40, count, first)
            assert found == index, (first, index, found)
            reachable.add(index)
    assert reachable == set(range(count)), "every card can be scrolled to"


def test_the_scroll_window_stays_inside_the_hand():
    count = 40
    shown = burraco.visible_slots(count)
    assert burraco.clamp_scroll(count, -5) == 0
    assert burraco.clamp_scroll(count, 999) == count - shown
    assert burraco.clamp_scroll(11, 5) == 0, "a hand that fits never scrolls"
    assert list(burraco.visible_range(11, 3)) == list(range(11))


def test_a_scrolled_card_has_no_place_on_screen():
    assert burraco.hand_x(40, 39, first=0) is None
    assert burraco.hand_x(40, 0, first=10) is None


def test_the_burraco_hit_test_ignores_the_lift():
    spot = burraco.hand_x(11, 4) + burraco.hand_step(11) / 2
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
    (run, other), _scale = burraco.meld_boxes(["run", "set"], [5, 5], 400)
    assert run[4] is True and other[4] is False
    assert run[2] == burraco.MELD_W, "a run is one card wide"
    assert run[3] > other[3], "and taller than a set of the same size"


def test_meld_boxes_do_not_overlap():
    kinds = ["run", "set", "run", "set", "run"]
    sizes = [4, 3, 7, 5, 3]
    boxes, _scale = burraco.meld_boxes(kinds, sizes, 400)
    for first, second in zip(boxes, boxes[1:]):
        same_row = first[1] == second[1]
        if same_row:
            assert first[0] + first[2] <= second[0], (first, second)


def test_a_long_row_of_melds_wraps():
    boxes, _scale = burraco.meld_boxes(["set"] * 8, [4] * 8, 400)
    rows = {box[1] for box in boxes}
    assert len(rows) > 1, "eight melds cannot fit on one row"
    for box in boxes:
        assert box[0] + box[2] <= TABLE_W, "and none runs off the table"


def test_cards_in_a_meld_step_the_right_way():
    box = burraco.meld_boxes(["run"], [4], 400)[0][0]
    first = burraco.card_position(box, 0)
    second = burraco.card_position(box, 1)
    assert first[0] == second[0], "a run steps downward"
    assert second[1] > first[1]

    box = burraco.meld_boxes(["set"], [4], 400)[0][0]
    first = burraco.card_position(box, 0)
    second = burraco.card_position(box, 1)
    assert first[1] == second[1], "a set steps sideways"
    assert second[0] > first[0]


def test_a_meld_shows_enough_of_each_card_to_read_it():
    assert burraco.MELD_VSTEP >= 14, "a run must show its corner index"
    assert burraco.MELD_STEP >= 18, "and a set must show its rank"
    assert burraco.HAND_STEP_MIN >= 28, "a hand card must stay clickable"
    assert burraco.HAND_MARGIN >= 40, "and the fan must not touch the edges"


def feasible_tableaus():
    """Every spread of melds that 108 cards could actually make."""
    for size in range(3, 15):
        for count in range(1, 108 // size + 1):
            for kind in ("set", "run"):
                yield kind, count, size


def test_melds_never_reach_the_hand():
    """Cards under the hand can be neither read nor added to.

    A long row of melds wrapped downward with no limit: ten melds of five ran
    to y=664 with the hand starting at 606, so the last row was buried.
    """
    for kind, count, size in feasible_tableaus():
        boxes, scale = burraco.meld_boxes([kind] * count, [size] * count,
                                          burraco.YOUR_MELD_Y,
                                          burraco.your_meld_room())
        bottom = max(box[1] + box[3] for box in boxes)
        assert bottom <= burraco.HAND_Y, (kind, count, size, bottom, scale)


def test_the_opponents_melds_stay_off_the_stock():
    for kind, count, size in feasible_tableaus():
        boxes, scale = burraco.meld_boxes([kind] * count, [size] * count,
                                          burraco.OPP_MELD_Y,
                                          burraco.OPP_MELD_ROOM)
        bottom = max(box[1] + box[3] for box in boxes)
        assert bottom <= burraco.STOCK_Y, (kind, count, size, bottom, scale)


def test_hiding_the_hand_gives_the_melds_the_room_back():
    """Shrinking is the fallback; putting the hand away is the cure.

    With many melds the cards shrink until they are hard to read, which is
    the wrong trade — so the hand can step aside, and the melds take the
    lower table at full size.
    """
    assert burraco.your_meld_room(True) > burraco.your_meld_room(False)

    for count in (10, 16):
        _boxes, cramped = burraco.meld_boxes(["set"] * count, [5] * count,
                                             burraco.YOUR_MELD_Y,
                                             burraco.your_meld_room(False))
        _boxes, roomy = burraco.meld_boxes(["set"] * count, [5] * count,
                                           burraco.YOUR_MELD_Y,
                                           burraco.your_meld_room(True))
        assert cramped < 1.0, f"{count} melds crowd the hand"
        assert roomy == 1.0, f"{count} melds fit once the hand is away"


def test_melds_shrink_only_as_much_as_they_must():
    _few, roomy = burraco.meld_boxes(["set"] * 3, [4] * 3,
                                     burraco.YOUR_MELD_Y,
                                     burraco.your_meld_room())
    assert roomy == 1.0, "a few melds are drawn full size"

    _many, tight = burraco.meld_boxes(["set"] * 16, [5] * 16,
                                      burraco.YOUR_MELD_Y,
                                      burraco.your_meld_room())
    assert tight < 1.0, "a tableful shrinks"
    assert tight >= burraco.MELD_SCALE_MIN, "but never past the floor"


def test_cards_of_a_shrunken_meld_still_step_apart():
    boxes, scale = burraco.meld_boxes(["run"] * 16, [7] * 16,
                                      burraco.YOUR_MELD_Y,
                                      burraco.your_meld_room())
    first = burraco.card_position(boxes[0], 0, scale)
    second = burraco.card_position(boxes[0], 1, scale)
    assert second[1] - first[1] >= 8, "a shrunken run must still be readable"


# --- Scopa ----------------------------------------------------------------

def test_a_scopa_hand_is_centred():
    for count in (1, 2, 3):
        left = scopa.hand_x(count, 0)
        right = scopa.hand_x(count, count - 1) + scopa.CARD_W
        assert abs((left + right) / 2 - scopa.CENTER_X) < 0.5, count


def test_the_pointer_finds_each_scopa_card():
    for count in (1, 2, 3):
        for index in range(count):
            x = scopa.hand_x(count, index) + scopa.CARD_W / 2
            y = scopa.HAND_Y + scopa.CARD_H / 2
            assert scopa.hand_slot_at(x, y, count) == index
    assert scopa.hand_slot_at(0, scopa.HAND_Y, 3) is None
    assert scopa.hand_slot_at(scopa.CENTER_X, 0, 3) is None


def test_the_scopa_table_stays_on_the_table():
    """However many cards pile up, none of them leaves the felt."""
    for count in range(1, 41):
        boxes = scopa.table_boxes(count)
        assert len(boxes) == count
        for x, y, w, h in boxes:
            assert x >= 0 and x + w <= TABLE_W, count
            assert y >= 0 and y + h <= scopa.HAND_Y - scopa.LIFT, count


def test_the_scopa_table_never_overlaps_itself():
    for count in (2, 5, 9, 14, 22, 33):
        boxes = scopa.table_boxes(count)
        for first in range(len(boxes)):
            for second in range(first + 1, len(boxes)):
                a, b = boxes[first], boxes[second]
                apart = (a[0] + a[2] <= b[0] + 0.01
                         or b[0] + b[2] <= a[0] + 0.01
                         or a[1] + a[3] <= b[1] + 0.01
                         or b[1] + b[3] <= a[1] + 0.01)
                assert apart, f"{count}: {first} overlaps {second}"


def test_the_scopa_table_fills_rows_before_it_shrinks_cards():
    """A smaller card is a last resort: rows come first."""
    for count in (1, 4, 6):
        assert scopa.table_boxes(count)[0][2] == scopa.TABLE_CARD_W, count
        assert len({round(y) for _x, y, _w, _h in scopa.table_boxes(count)}) == 1
    rows = len({round(y) for _x, y, _w, _h in scopa.table_boxes(30)})
    assert rows == scopa.TABLE_ROWS
    assert scopa.table_boxes(30)[0][2] < scopa.TABLE_CARD_W


def test_the_pointer_finds_a_card_on_the_scopa_table():
    for count in (1, 4, 9, 20):
        for index, (x, y, w, h) in enumerate(scopa.table_boxes(count)):
            assert scopa.table_slot_at(x + w / 2, y + h / 2, count) == index
    assert scopa.table_slot_at(2, 2, 6) is None


# --- Tressette ------------------------------------------------------------

def test_a_tressette_hand_is_centred_at_every_size():
    for count in (1, 4, 7, 10):
        left = tressette.hand_x(count, 0)
        right = tressette.hand_x(count, count - 1) + tressette.HAND_W
        assert abs((left + right) / 2 - tressette.CENTER_X) < 0.5, count


def test_ten_cards_still_fit_the_table():
    for count in (1, 5, 10):
        left = tressette.hand_x(count, 0)
        right = tressette.hand_x(count, count - 1) + tressette.HAND_W
        assert left >= 0 and right <= TABLE_W, count


def test_the_tressette_fan_only_tightens_when_it_has_to():
    assert tressette.hand_step(3) == tressette.HAND_STEP_MAX
    assert tressette.hand_step(10) < tressette.HAND_STEP_MAX
    assert tressette.hand_step(10) > tressette.HAND_W / 3, \
        "a card must still show a strip wide enough to read and to click"


def test_the_pointer_finds_each_tressette_card():
    for count in (1, 6, 10):
        for index in range(count):
            x = tressette.hand_x(count, index) + tressette.HAND_W / 2
            y = tressette.HAND_Y + tressette.HAND_H / 2
            assert tressette.hand_slot_at(x, y, count) == index, (count, index)
    assert tressette.hand_slot_at(0, tressette.HAND_Y, 10) is None
    assert tressette.hand_slot_at(tressette.CENTER_X, 0, 10) is None


def test_where_two_tressette_cards_overlap_the_top_one_wins():
    """The cards are drawn left to right, so the right-hand one is on top."""
    count = 10
    left = tressette.hand_x(count, 5)
    strip = left + 2                     # inside card 4 as well as card 5
    assert tressette.hand_slot_at(strip, tressette.HAND_Y + 20, count) == 5


def test_a_forbidden_tressette_card_can_still_be_clicked():
    """It is drawn lower than the rest, and the hit test has to reach it."""
    count = 10
    x = tressette.hand_x(count, 0) + tressette.HAND_W / 2
    foot = tressette.HAND_Y + tressette.HAND_H + tressette.DIM_DROP - 1
    assert tressette.hand_slot_at(x, foot, count) == 0
    assert tressette.hand_slot_at(
        x, tressette.HAND_Y + tressette.HAND_H + tressette.DIM_DROP + 6,
        count) is None


def test_the_tressette_table_stays_clear_of_the_hand():
    for player in (tressette.HUMAN, tressette.AI):
        _x, y = tressette.table_slot(player)
        assert y + tressette.TABLE_CARD_H <= tressette.HAND_Y - tressette.LIFT


def test_the_two_tressette_table_slots_do_not_overlap():
    (ax, ay), (bx, by) = (tressette.table_slot(tressette.AI),
                          tressette.table_slot(tressette.HUMAN))
    assert ax + tressette.TABLE_CARD_W <= bx or bx + tressette.TABLE_CARD_W <= ax


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
