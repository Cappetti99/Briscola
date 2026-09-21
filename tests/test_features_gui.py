"""Integration checks for the new UI features (requires a desktop session)."""
import copy
import sys
import tempfile
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_gui import app_with_records
from cardgames import app as gui, records, ui
from cardgames.session import encode
from cardgames.match import Match


def pump(app, until, timeout=3):
    deadline = time.monotonic() + timeout
    while not until() and time.monotonic() < deadline:
        app.update()
        time.sleep(.005)
    assert until(), 'UI operation timed out'


def test_resume_all_games_after_returning_to_menu():
    for kind in ui.GAMES:
        with app_with_records(start=False) as (app, store, tmp):
            app.set_game(kind)
            app.start_game()
            app._cancel_pending()
            state = encode(app.game)
            app.show_menu()
            app.resume_game()
            app._cancel_pending()
            assert encode(app.game) == state
            assert app.game_kind == kind
            assert not store.matches(app.player)


def test_resume_after_window_recreation():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        store = records.Records(path / 'records.json', path / 'records.txt')
        first = gui.BriscolaApp(store, scale=1)
        first.start_game()
        first._play_human(0)
        state = encode(first.game)
        first.destroy()
        second = gui.BriscolaApp(store, scale=1)
        try:
            assert second.state == 'menu'
            second.resume_game()
            second._cancel_pending()
            assert encode(second.game) == state
        finally:
            second.destroy()


def test_worker_keeps_ui_responsive_and_discards_stale_result():
    with app_with_records() as (app, _, _tmp):
        app._cancel_pending()
        gate = threading.Event()
        applied = []
        def slow(snapshot):
            gate.wait(2)
            snapshot.points[0] = 999
            return 42
        app.compute_ai(slow, applied.append)
        tick = []
        app.after(1, lambda: tick.append(True))
        pump(app, lambda: bool(tick))
        assert app.game.points[0] != 999
        app.show_menu()
        gate.set()
        for _ in range(5):
            app.update()
            time.sleep(.01)
        assert applied == []
        assert app.state == 'menu'


def test_worker_applies_once_and_skip_does_not_duplicate_it():
    with app_with_records() as (app, _, _tmp):
        app._cancel_pending()
        applied = []
        app.state = 'ai'
        app.compute_ai(lambda game: 12, applied.append)
        app._skip_wait()
        pump(app, lambda: not app._worker_busy)
        assert applied == [12]


def test_training_match_is_not_recorded_and_new_game_resets_training():
    with app_with_records() as (app, store, _tmp):
        app._cancel_pending()
        app.show_hint()
        assert app._training_used
        app.close_overlay()
        game = app.game
        game.hands = [[], []]
        game.stock = []
        game.trump_card = None
        game.table = []
        game.points = [80, 40]
        app._advance()
        assert not store.matches(app.player)
        assert not app.sessions.path.exists()
        app.new_game()
        assert not app._training_used


def test_completed_series_is_recorded_only_once():
    with app_with_records(start=False) as (app, store, _tmp):
        app.set_game('scopa')
        app.start_game()
        app._cancel_pending()
        app.match = Match(target=0)
        app._finish_match_hand('Finished', 0)
        app._finish_match_hand('Finished', 0)
        assert len(store.matches(app.player)) == 1


def test_statistics_filters_and_settings_switch_language():
    with app_with_records(start=False) as (app, store, _tmp):
        store.add_match(app.player, 80, 40, 'normal', 'you', 'briscola')
        store.add_match(app.player, 1200, 600, 'normal', 'you', 'burraco')
        app.language = 'it'
        app.deck_style = 'italian'
        app.render()
        texts = [app.canvas.itemcget(item, 'text') for item in app.canvas.find_all()
                 if app.canvas.type(item) == 'text']
        assert 'Inizia partita' in texts
        app.show_statistics()
        app.stats_game.set('all')
        app._refresh_stats_window()
        texts = [app.stats_canvas.itemcget(item, 'text') for item in app.stats_canvas.find_all()
                 if app.stats_canvas.type(item) == 'text']
        assert texts.count('—') == 2
        app.stats_game.set('burraco')
        app._refresh_stats_window()
        texts = [app.stats_canvas.itemcget(item, 'text') for item in app.stats_canvas.find_all()
                 if app.stats_canvas.type(item) == 'text']
        assert '1200' in texts and '80 - 40' not in texts
        app.show_settings()
        app._settings_window.destroy()
        app._settings_window = None


def test_italian_rules_and_hints_fit_the_canvas():
    for kind in ui.GAMES:
        with app_with_records(start=False) as (app, _, _tmp):
            app.language = 'it'
            app.deck_style = 'italian'
            app.set_game(kind)
            app.show_rules()
            for item in app.canvas.find_all():
                if app.canvas.type(item) == 'text':
                    box = app.canvas.bbox(item)
                    assert box[0] >= 0 and box[2] <= gui.WIN_W, (kind, box)
                    assert box[1] >= 0 and box[3] <= gui.WIN_H, (kind, box)
            app.close_overlay()
            app.start_game()
            app._cancel_pending()
            app.show_hint()
            assert app.overlay and app._training_used



def test_resume_between_hands_does_not_score_the_hand_twice():
    from cardgames.scopa import ai
    with app_with_records(start=False) as (app, store, _tmp):
        app.set_game('scopa')
        app.start_game()
        app._cancel_pending()
        app.match = Match(target=100)
        while not app.game.game_over:
            ai.take_turn(app.game, app.game.turn, 'normal')
        app.after_move()
        totals = list(app.match.totals)
        assert app.match.hands == 1 and app.sessions.path.exists()
        app.show_menu()
        app.resume_game()
        assert app.match.hands == 1
        assert app.match.totals == totals
        assert not store.matches(app.player)
        assert app.overlay[0] == 'Hand over'


def test_burraco_computer_draw_is_not_exposed_in_log():
    from cardgames.burraco import view
    with app_with_records(start=False) as (app, _, _tmp):
        app.set_game('burraco')
        app.start_game()
        app._cancel_pending()
        app.game.turn = 1
        original = view.burraco_ai.take_turn
        try:
            view.burraco_ai.take_turn = lambda *args: ['draws Ace of Diamonds']
            view.computer_turn(app)
            assert app.log_lines[0][0] == 'Computer draws a card'
        finally:
            view.burraco_ai.take_turn = original



def test_real_expert_moves_apply_for_all_search_games():
    for kind in ('briscola', 'scopa', 'tressette'):
        with app_with_records(start=False) as (app, _, _tmp):
            app.set_game(kind)
            app.difficulty = 'hard'
            app.next_leader = 1
            app.start_game()
            count = len(app.game.hands[1])
            app._skip_wait()
            pump(app, lambda: app.state == 'human', timeout=5)
            assert len(app.game.hands[1]) == count - 1
            assert app.sessions.load()['game_kind'] == kind


def test_tutorial_advances_without_touching_the_game():
    with app_with_records(start=False) as (app, _, _tmp):
        app.set_game('briscola')
        app.start_game()
        app._cancel_pending()
        before = app.game
        app.show_tutorial()
        assert app.overlay[0].startswith('Tutorial')
        app._next_tutorial()
        assert app._tutorial_index == 1
        assert app.game is before


if __name__ == '__main__':
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name, flush=True)
