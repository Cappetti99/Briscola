"""Interface smoke tests: they open real (short-lived) Tk windows.

Run them like the others:

    conda run -n briscola python tests/test_gui.py
"""

import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames import records
from cardgames.briscola import ai, gui
from cardgames.briscola.engine import AI, HUMAN, TOTAL_POINTS


@contextmanager
def app_with_records(difficulty=ai.NORMAL, start=True):
    """A fresh app writing to a throwaway record store, dialogs stubbed out.

    The app opens on the menu, so `start=True` presses Start for you; pass
    `start=False` to test the menu itself.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        store = records.Records(path=tmp / "records.json",
                               text_path=tmp / "records.txt")
        store.set_player("tester")

        ask_string = gui.simpledialog.askstring
        delays = (gui.AI_DELAY, gui.TRICK_DELAY)
        worlds = (ai.WORLDS_EARLY, ai.WORLDS_LATE)
        gui.simpledialog.askstring = lambda *a, **kw: "someone else"
        gui.AI_DELAY = gui.TRICK_DELAY = 5
        ai.WORLDS_EARLY, ai.WORLDS_LATE = 8, 12

        app = gui.BriscolaApp(records_store=store)
        # Park the window off screen. It has to stay mapped — Tk will not
        # deliver synthetic pointer events to an unmapped window — but out
        # there the real mouse cannot land a click inside a running test.
        app.geometry("+3000+3000")
        app.difficulty = difficulty
        if start:
            app.start_game()
        try:
            yield app, store, tmp
        finally:
            app.destroy()
            gui.simpledialog.askstring = ask_string
            gui.AI_DELAY, gui.TRICK_DELAY = delays
            ai.WORLDS_EARLY, ai.WORLDS_LATE = worlds


def play_to_the_end(app, limit=4000):
    """Drive the interface as a player who always plays their first card."""
    for _ in range(limit):
        app.update()
        if app.state == gui.S_OVER:
            return True
        if app.state == gui.S_HUMAN:
            app._play_human(0)
    return False


def settle(app, seconds=0.4):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.update()
        time.sleep(0.01)


def wait_for(app, predicate, seconds=15.0):
    """Pump the event loop until `predicate` holds.

    Tk timers need real time to fire, so a burst of update() calls is not
    enough to move the game on by itself. The timeout is only a limit on
    patience, not part of what is being asserted, so it is generous: a tight
    one turns a loaded machine into a failing test.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.update()
        if predicate():
            return True
        time.sleep(0.005)
    return False


def test_app_opens_on_the_menu():
    with app_with_records(start=False) as (app, _store, _tmp):
        app.update()
        assert app.state == gui.S_MENU
        assert app.game is None
        # The menu offers a way in and a way to look around.
        for key in ("menu_start", "menu_stats", "menu_rules",
                    "level_easy", "level_normal", "level_hard"):
            assert key in app._buttons, key

        _rect, start = app._buttons["menu_start"]
        start()
        app.update()
        assert app.state in (gui.S_HUMAN, gui.S_AI)
        assert app.game is not None


def test_menu_pills_pick_the_difficulty():
    with app_with_records(start=False) as (app, _store, _tmp):
        for level in ai.LEVELS:
            _rect, choose = app._buttons[f"level_{level}"]
            choose()
            app.update()
            assert app.difficulty == level
            assert app.state == gui.S_MENU, "picking a level must not start a game"


def test_returning_to_the_menu_drops_the_game_unrecorded():
    with app_with_records() as (app, store, _tmp):
        def a_couple_of_tricks():
            if app.state == gui.S_HUMAN:
                app._play_human(0)
            return app.game.tricks_played >= 2

        assert wait_for(app, a_couple_of_tricks), "the game did not start"
        app.show_menu()
        app.update()
        assert app.state == gui.S_MENU
        assert store.matches("tester") == []
        app.start_game()
        app.update()
        assert app.state in (gui.S_HUMAN, gui.S_AI)


def test_a_full_game_is_playable_and_recorded():
    with app_with_records() as (app, store, tmp):
        assert play_to_the_end(app), f"stuck in state {app.state}"
        game = app.game
        assert game.tricks_played == 20
        assert sum(game.points) == TOTAL_POINTS

        settle(app)
        matches = store.matches("tester")
        assert len(matches) == 1, matches
        assert matches[0].you == game.points[HUMAN]
        assert matches[0].ai == game.points[AI]
        assert (tmp / "records.json").exists()
        assert (tmp / "records.txt").exists()
        # The result is shown in-window, not in a native dialog that could
        # open behind the game.
        assert app.overlay is not None
        title, body, actions = app.overlay
        assert str(game.points[HUMAN]) in body and str(game.points[AI]) in body
        assert [label for label, _cmd in actions] == ["New game", "Statistics",
                                                     "Menu"]


def test_abandoned_game_is_not_recorded():
    with app_with_records() as (app, store, _tmp):
        def a_few_tricks_played():
            if app.state == gui.S_HUMAN:
                app._play_human(0)
            return app.game.tricks_played >= 3

        assert wait_for(app, a_few_tricks_played), "the game did not start"
        app.new_game()
        app.update()
        assert store.matches("tester") == []


def test_two_games_alternate_the_opening_lead():
    with app_with_records() as (app, store, _tmp):
        leaders = []
        for _ in range(2):
            leaders.append(app.game.first_leader)
            assert play_to_the_end(app)
            settle(app)
            app.close_overlay()
            app.new_game()
        assert leaders[0] != leaders[1], leaders
        assert len(store.matches("tester")) == 2


def test_played_card_lands_on_its_slot():
    """Regression: a stale animation step used to leave the card off-slot."""
    with app_with_records() as (app, _store, _tmp):
        seen = 0
        for _ in range(400):
            app.update()
            if app.state == gui.S_HUMAN and app.game.lead_card is not None:
                settle(app, 0.3)
                box = app.canvas.bbox(f"table{AI}")
                slot_x, slot_y = app._table_slot(AI)
                assert box is not None, "no card drawn in the computer's slot"
                assert abs(box[0] - slot_x) <= 6, (box, slot_x)
                assert abs(box[1] - slot_y) <= 6, (box, slot_y)
                seen += 1
                if seen == 3:
                    return
            if app.state == gui.S_HUMAN:
                app._play_human(0)
        assert seen, "the computer never led a card"


def test_every_difficulty_can_finish_a_game():
    for level in ai.LEVELS:
        with app_with_records(difficulty=level) as (app, store, _tmp):
            assert play_to_the_end(app), f"{level} stuck in {app.state}"
            settle(app)
            assert store.matches("tester")[0].difficulty == level


def test_difficulty_button_cycles():
    with app_with_records() as (app, _store, _tmp):
        seen = [app.difficulty]
        for _ in range(len(ai.LEVELS)):
            app.cycle_difficulty()
            seen.append(app.difficulty)
        assert set(seen) == set(ai.LEVELS), seen
        assert seen[0] == seen[-1], "cycling should come back around"


def click_card(app, index=0):
    """A real Tk mouse click on a hand card, like a player would."""
    x = int(app._hand_x(len(app.game.hands[HUMAN]), index) + gui.CARD_W / 2)
    y = int(gui.PLAYER_HAND_Y + gui.CARD_H / 2)
    app.canvas.event_generate("<Button-1>", x=x, y=y)
    app.update()


def test_clicking_a_card_plays_it_without_skipping_the_pause():
    """Regression: one click used to play the card *and* eat the next pause.

    The card handler and the canvas-wide skip handler both fire for the same
    click, so a single click played a card and immediately skipped the wait
    after it — and the following click was swallowed by a pause instead of
    playing a card.
    """
    with app_with_records() as (app, _store, _tmp):
        gui.AI_DELAY = gui.TRICK_DELAY = 3000
        try:
            assert wait_for(app, lambda: app.state == gui.S_HUMAN)
            before_cards = len(app.game.table)
            before_tricks = app.game.tricks_played

            click_card(app)

            assert len(app.game.table) == before_cards + 1, \
                "exactly one card should reach the table"
            assert app.game.tricks_played == before_tricks, \
                "the trick pause was skipped by the same click"
            assert app.state in (gui.S_AI, gui.S_SHOW)
        finally:
            gui.AI_DELAY = gui.TRICK_DELAY = 5


def test_clicking_the_felt_does_skip_the_pause():
    with app_with_records() as (app, _store, _tmp):
        gui.AI_DELAY = gui.TRICK_DELAY = 3000
        try:
            def reach_a_pause():
                if app.state == gui.S_HUMAN:
                    click_card(app)
                return app.state in (gui.S_AI, gui.S_SHOW)

            assert wait_for(app, reach_a_pause)
            before = (app.game.tricks_played, len(app.game.table))
            app.canvas.event_generate("<Button-1>", x=10, y=620)  # bare felt
            app.update()
            after = (app.game.tricks_played, len(app.game.table))
            assert after != before, f"the click did not carry on ({before})"
        finally:
            gui.AI_DELAY = gui.TRICK_DELAY = 5


def test_hover_cannot_chase_itself():
    """Regression: the hover lift used to lock the whole window up.

    Lifting a card moved it out from under a pointer resting near its bottom
    edge, so Tk sent <Leave>, the card dropped back under the pointer, <Enter>
    fired, and the pair chased each other forever at full CPU — the window
    stayed on screen but stopped answering clicks. The hit test must therefore
    give the same answer whether or not the card is currently lifted.
    """
    with app_with_records() as (app, _store, _tmp):
        assert wait_for(app, lambda: app.state == gui.S_HUMAN)
        x = app._hand_x(len(app.game.hands[HUMAN]), 1) + gui.CARD_W / 2

        # Right along the bottom edge, the worst case for the old code.
        for y in (gui.PLAYER_HAND_Y + gui.CARD_H - 1,
                  gui.PLAYER_HAND_Y + gui.CARD_H - 3,
                  gui.PLAYER_HAND_Y + 4,
                  gui.PLAYER_HAND_Y - gui.LIFT + 1):
            app._set_hover_index(None)
            first = app._hand_slot_at(x, y)
            app._set_hover_index(first)          # the card is now lifted
            assert app._hand_slot_at(x, y) == first, (
                f"y={y}: the answer changed once the card moved")

        # And a stream of real pointer motion settles instead of oscillating.
        y = int(gui.PLAYER_HAND_Y + gui.CARD_H - 2)
        for _ in range(30):
            app.canvas.event_generate("<Motion>", x=int(x), y=y)
            app.update()
        assert app.hover == {1}, app.hover
        for _ in range(10):
            app.canvas.event_generate("<Motion>", x=int(x), y=y)
            app.update()
        assert app.hover == {1}, f"hover flipped: {app.hover}"


DWELL_SECONDS = 5.0
DWELL_MOVES = 4


def test_playing_at_human_pace_stays_responsive():
    """Play like a person: rest the pointer on a card, think, then click.

    That pause is what locked the window up. The hover lift and Tk's
    <Enter>/<Leave> chased each other while the pointer sat still on a card,
    burning a core and starving the click queue, so nothing ever surfaced in a
    test that clicked as fast as it could. Here the pointer rests on the worst
    spot — a card's bottom edge — for five seconds before each click, and the
    check is the one that matters: an idle window must cost almost no CPU, and
    the click afterwards must land.
    """
    with app_with_records() as (app, _store, _tmp):
        # Real pacing, so the pauses between moves are the real ones too.
        gui.AI_DELAY, gui.TRICK_DELAY = 550, 1000
        try:
            plays = 0
            deadline = time.time() + 90
            while plays < DWELL_MOVES and time.time() < deadline:
                if app.state == gui.S_OVER:
                    break
                if app.state != gui.S_HUMAN:
                    settle(app, 0.1)
                    continue

                count = len(app.game.hands[HUMAN])
                x = int(app._hand_x(count, count - 1) + gui.CARD_W / 2)
                y = int(gui.PLAYER_HAND_Y + gui.CARD_H - 2)   # the worst spot

                # Sweep the pointer across every card a couple of times, along
                # their bottom edge, then rest on the last one — all inside the
                # five seconds. Crossing between cards is its own hazard: each
                # crossing drops one card and lifts another.
                cpu_before = time.process_time()
                end = time.time() + DWELL_SECONDS
                sweeps = 0
                while time.time() < end:
                    if sweeps < 2:
                        for index in list(range(count)) + list(range(count - 2, -1, -1)):
                            step = int(app._hand_x(count, index) + gui.CARD_W / 2)
                            for offset in (-gui.LIFT + 2, 20, gui.CARD_H - 2):
                                app.canvas.event_generate(
                                    "<Motion>", x=step,
                                    y=int(gui.PLAYER_HAND_Y + offset))
                                app.update()
                                time.sleep(0.01)
                        sweeps += 1
                        app.canvas.event_generate("<Motion>", x=x, y=y)
                    app.update()
                    time.sleep(0.01)
                cpu = time.process_time() - cpu_before
                assert cpu < 0.2 * DWELL_SECONDS, (
                    f"an idle window burnt {cpu:.1f}s of CPU while the pointer "
                    f"rested on a card for {DWELL_SECONDS:.0f}s - "
                    "the hover is chasing itself")
                assert app.state == gui.S_HUMAN, \
                    f"the game moved on by itself while we waited ({app.state})"

                # Put the pointer back (the real mouse may have wandered over
                # the window during the wait) and play.
                app.canvas.event_generate("<Motion>", x=x, y=y)
                app.update()
                before = (app.game.tricks_played, len(app.game.table))
                app.canvas.event_generate("<Button-1>", x=x, y=y)
                app.update()
                assert (app.game.tricks_played, len(app.game.table)) != before, \
                    f"the click after a {DWELL_SECONDS:.0f}s pause did nothing"
                plays += 1

            assert plays == DWELL_MOVES, f"only got {plays} moves in"
        finally:
            gui.AI_DELAY = gui.TRICK_DELAY = 5


def test_hover_follows_the_pointer():
    with app_with_records() as (app, _store, _tmp):
        assert wait_for(app, lambda: app.state == gui.S_HUMAN)
        count = len(app.game.hands[HUMAN])
        for index in range(count):
            x = int(app._hand_x(count, index) + gui.CARD_W / 2)
            app.canvas.event_generate("<Motion>", x=x,
                                      y=int(gui.PLAYER_HAND_Y + 40))
            app.update()
            assert app.hover == {index}, (index, app.hover)
        # Off the cards entirely.
        app.canvas.event_generate("<Motion>", x=20, y=20)
        app.update()
        assert app.hover == set()


def test_a_click_skips_the_pause():
    """The waits are there to be readable, not to be endured."""
    with app_with_records() as (app, _store, _tmp):
        gui.AI_DELAY = gui.TRICK_DELAY = 4000     # long enough to rule out luck
        try:
            def reach_a_pause():
                if app.state == gui.S_HUMAN:
                    app._play_human(0)
                return app.state in (gui.S_AI, gui.S_SHOW)

            assert wait_for(app, reach_a_pause), f"state stayed {app.state}"
            waiting_on = app.state
            before = (app.game.tricks_played, len(app.game.table))
            app._skip_wait()
            app.update()
            after = (app.game.tricks_played, len(app.game.table))
            assert after != before, f"{waiting_on}: nothing moved ({before})"
        finally:
            gui.AI_DELAY = gui.TRICK_DELAY = 5


def test_statistics_window_draws():
    with app_with_records() as (app, _store, _tmp):
        assert play_to_the_end(app)
        settle(app)
        app.show_statistics()
        app.update()
        assert app.stats_window is not None
        assert len(app.stats_canvas.find_all()) > 20
        app.show_statistics()          # a second click must not open a twin
        app.update()
        app._close_stats_window()
        app.update()
        assert app.stats_window is None


def test_changing_player_switches_the_record():
    with app_with_records() as (app, store, _tmp):
        app._change_player()
        app.update()
        assert app.player == "someone else"
        assert store.current_player == "someone else"
        assert play_to_the_end(app)
        settle(app)
        assert len(store.matches("someone else")) == 1
        assert store.matches("tester") == []


def test_keyboard_shortcuts_play_cards():
    class Key:
        def __init__(self, char):
            self.char = char

    with app_with_records() as (app, _store, _tmp):
        assert wait_for(app, lambda: app.state == gui.S_HUMAN), "never our turn"
        # Check the card left the hand, not the hand size: the trick may
        # resolve straight away and hand a fresh card back.
        card = app.game.hands[HUMAN][0]
        app._on_key(Key("1"))
        app.update()
        assert card not in app.game.hands[HUMAN]
        app._on_key(Key("d"))
        assert app.difficulty != ai.NORMAL





# --- Burraco through the same window --------------------------------------

def test_the_menu_offers_both_games():
    from cardgames import ui

    with app_with_records(start=False) as (app, _store, _tmp):
        app.update()
        for kind in ui.GAMES:
            assert f"game_{kind}" in app._buttons, kind

        _rect, choose = app._buttons["game_burraco"]
        choose()
        app.update()
        assert app.game_kind == ui.BURRACO
        assert app.state == gui.S_MENU, "picking a game must not deal one"


def test_a_burraco_hand_plays_to_the_end_and_is_recorded():
    from cardgames import ui
    from cardgames.burraco import ai as burraco_ai
    from cardgames.burraco.engine import HUMAN as B_HUMAN

    with app_with_records(start=False) as (app, store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()

        turns = 0
        while not app.game.game_over and turns < 300:
            app.update()
            if app.state != gui.S_HUMAN:
                time.sleep(0.005)
                continue
            # Play our seat with the same policy the opponent uses.
            burraco_ai.take_turn(app.game, B_HUMAN, app.difficulty)
            app.selected.clear()
            app.after_move()
            turns += 1

        assert app.game.game_over, f"still going after {turns} turns"
        settle(app)
        matches = store.matches("tester")
        assert len(matches) == 1, matches
        assert matches[0].game == ui.BURRACO
        assert matches[0].you == app.game.scores()[0]
        assert app.overlay is not None


def test_clicking_a_burraco_card_selects_it():
    from cardgames import ui

    with app_with_records(start=False) as (app, _store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()
        app.update()
        assert app.selected == set()

        from cardgames.burraco import view
        view.click_card(app, 0)
        assert app.selected == {0}
        view.click_card(app, 0)
        assert app.selected == set(), "clicking again puts the card back down"


def test_burraco_refuses_an_illegal_meld_without_losing_cards():
    from cardgames import ui
    from cardgames.burraco import view
    from cardgames.burraco.engine import HUMAN as B_HUMAN

    with app_with_records(start=False) as (app, _store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()
        while app.state != gui.S_HUMAN:
            app.update()
            time.sleep(0.005)

        view.click_action(app, "draw")
        before = sorted(map(str, app.game.hands[B_HUMAN]))
        app.selected = {0, 1, 2}
        view.click_action(app, "meld")       # almost certainly not a meld
        after = sorted(map(str, app.game.hands[B_HUMAN]))
        if app.game.melds[B_HUMAN]:
            return                           # it happened to be a real meld
        assert after == before, "a refused meld must leave the hand alone"


def _select(app, cards):
    """Select exactly these cards in hand, duplicates and all."""
    from cardgames.burraco.engine import HUMAN as B_HUMAN

    hand = app.game.hands[B_HUMAN]
    chosen = set()
    for card in cards:
        for index, held in enumerate(hand):
            if held == card and index not in chosen:
                chosen.add(index)
                break
    app.selected = chosen
    return chosen


def _play_a_turn_through_the_buttons(app):
    """A turn played only by clicking, the way a person plays it."""
    from cardgames.burraco import ai as burraco_ai
    from cardgames.burraco import view
    from cardgames.burraco.engine import HUMAN as B_HUMAN, can_extend

    game = app.game
    view.click_action(app, "pile" if len(game.discards) >= 6 else "draw")
    if game.game_over or not game.phase.drawn:
        return

    for _ in range(6):                       # lay down what the hand holds
        melds = burraco_ai._find_melds(list(game.hands[B_HUMAN]))
        if not melds:
            break
        before = len(game.melds[B_HUMAN])
        _select(app, melds[0])
        view.click_action(app, "meld")
        if len(game.melds[B_HUMAN]) == before:
            app.selected.clear()
            break

    for index, meld in enumerate(list(game.melds[B_HUMAN])):
        for card in list(game.hands[B_HUMAN]):
            if can_extend(meld, card):
                _select(app, [card])
                view.click_meld(app, index)
                break

    if game.game_over:
        return
    if game.hands[B_HUMAN]:
        app.selected = {0}
        view.click_action(app, "discard")
    else:
        view.click_action(app, "end")


def test_a_burraco_hand_played_only_by_clicking():
    """Drive the interface itself: every move goes through a real control.

    The end-to-end test above drives the engine for our seat, so it says
    nothing about the buttons. This one draws, lays down, extends and
    discards by clicking, which is the path a player actually takes.
    """
    from cardgames import ui
    from cardgames.burraco.engine import HUMAN as B_HUMAN
    from cardgames.cards import burraco_deck
    from collections import Counter

    with app_with_records(start=False) as (app, store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()

        turns = 0
        while not app.game.game_over and turns < 300:
            app.update()
            if app.state != gui.S_HUMAN:
                time.sleep(0.005)
                continue
            hand_before = len(app.game.hands[B_HUMAN])
            _play_a_turn_through_the_buttons(app)
            turns += 1
            assert app.game.turn != B_HUMAN or app.game.game_over, (
                f"turn {turns}: the turn never passed "
                f"(hand {hand_before} -> {len(app.game.hands[B_HUMAN])})")

        assert app.game.game_over, f"still going after {turns} turns"
        assert turns >= 5, "the hand ended suspiciously early"

        # Nothing was lost or conjured up along the way.
        game = app.game
        everywhere = Counter(game.hands[0] + game.hands[1] + game.stock
                             + game.discards + game.pots[0] + game.pots[1])
        for melds in game.melds:
            for meld in melds:
                everywhere.update(meld.cards)
        assert everywhere == Counter(burraco_deck())

        settle(app)
        assert store.matches("tester")[0].game == ui.BURRACO


def test_clicking_a_meld_extends_it():
    from cardgames import ui
    from cardgames.burraco import view
    from cardgames.burraco.engine import HUMAN as B_HUMAN, build_meld
    from cardgames.cards import Card

    with app_with_records(start=False) as (app, _store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()
        while app.state != gui.S_HUMAN:
            app.update()
            time.sleep(0.005)

        view.click_action(app, "draw")
        app.game.melds[B_HUMAN] = [build_meld([Card(5, "Hearts"),
                                               Card(6, "Hearts"),
                                               Card(7, "Hearts")])]
        app.game.hands[B_HUMAN] = [Card(8, "Hearts"), Card(2, "Clubs")]
        _select(app, [Card(8, "Hearts")])
        view.click_meld(app, 0)

        assert len(app.game.melds[B_HUMAN][0]) == 4
        assert Card(8, "Hearts") not in app.game.hands[B_HUMAN]
        assert app.selected == set(), "the selection is cleared after the move"


def test_the_pinella_comes_back_on_its_own_button():
    from cardgames import ui
    from cardgames.burraco import view
    from cardgames.burraco.engine import HUMAN as B_HUMAN, build_meld
    from cardgames.cards import JOKER_RANK, Card

    joker = Card(JOKER_RANK, "Joker")
    with app_with_records(start=False) as (app, _store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()
        while app.state != gui.S_HUMAN:
            app.update()
            time.sleep(0.005)

        view.click_action(app, "draw")
        app.game.melds[B_HUMAN] = [build_meld([Card(5, "Hearts"), joker,
                                               Card(7, "Hearts")])]
        app.game.hands[B_HUMAN] = [Card(6, "Hearts")]
        _select(app, [Card(6, "Hearts")])
        view.click_action(app, "swap")

        assert joker in app.game.hands[B_HUMAN], "the joker comes back to hand"
        meld = app.game.melds[B_HUMAN][0]
        assert meld.wilds == 0
        assert [card.rank for card in meld.cards] == [5, 6, 7], "and in order"


def test_adding_a_card_never_pulls_the_wild_out():
    """Clicking a meld grows it. It must not quietly reclaim the pinella."""
    from cardgames import ui
    from cardgames.burraco import view
    from cardgames.burraco.engine import HUMAN as B_HUMAN, build_meld
    from cardgames.cards import JOKER_RANK, Card

    joker = Card(JOKER_RANK, "Joker")
    with app_with_records(start=False) as (app, _store, _tmp):
        app.set_game(ui.BURRACO)
        app.start_game()
        while app.state != gui.S_HUMAN:
            app.update()
            time.sleep(0.005)

        view.click_action(app, "draw")
        app.game.melds[B_HUMAN] = [build_meld([Card(5, "Hearts"), joker,
                                               Card(7, "Hearts")])]
        app.game.hands[B_HUMAN] = [Card(6, "Hearts")]
        _select(app, [Card(6, "Hearts")])
        view.click_meld(app, 0)

        meld = app.game.melds[B_HUMAN][0]
        assert joker in meld.cards, "the joker stays on the table"
        assert joker not in app.game.hands[B_HUMAN]
        assert len(meld) == 4


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
