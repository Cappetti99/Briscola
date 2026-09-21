"""Regression checks for saves, filters, preferences and fair training hints."""
import copy
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cardgames import records, training, i18n
from cardgames.preferences import Preferences
from cardgames.session import SessionStore, ENGINES, encode
from cardgames.briscola import engine as briscola
from cardgames.burraco import engine as burraco
from cardgames.scopa import ai as scopa_ai
from cardgames.tressette import engine as tressette
from cardgames.match import Match
from cardgames.replay import Replay


def snapshot(kind, game):
    return dict(game_kind=kind, game=game, player='tester', match=Match(11),
                difficulty='normal', target=11, next_leader=1, recorded=False,
                log_lines=[], training_used=False)


def test_roundtrip_all_games_with_noninitial_state():
    with tempfile.TemporaryDirectory() as folder:
        store = SessionStore(Path(folder) / 'session.json')
        for kind, cls in ENGINES.items():
            game = cls(seed=32)
            if kind in ('briscola', 'tressette'):
                for _ in range(4):
                    for _ in range(2):
                        legal = game.legal_cards(game.turn) if kind == 'tressette' else [0]
                        game.play_card(game.turn, legal[0])
                    game.resolve_trick()
            elif kind == 'scopa':
                for _ in range(7):
                    scopa_ai.take_turn(game, game.turn, 'normal')
            else:
                from cardgames.burraco import ai
                for _ in range(4):
                    ai.take_turn(game, game.turn)
                game.draw(game.turn)
            before = snapshot(kind, game)
            store.save(before)
            after = store.load()
            assert encode(before) == encode(after), kind
            # The restored object retains executable engine behaviour.
            resumed = after['game']
            if kind == 'burraco':
                resumed.discard(resumed.turn, resumed.hands[resumed.turn][0])
            elif kind == 'scopa':
                scopa_ai.take_turn(resumed, resumed.turn, 'normal')
            else:
                index = resumed.legal_cards(resumed.turn)[0] if kind == 'tressette' else 0
                resumed.play_card(resumed.turn, index)


def test_invalid_save_is_preserved():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'session.json'
        path.write_text('{broken')
        try:
            SessionStore(path).load()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid save accepted')
        assert path.read_text() == '{broken'


def test_stats_filters_do_not_mix_scales():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        store = records.Records(path / 'records.json', path / 'records.txt')
        store.add_match('a', 80, 40, 'normal', 'you', 'briscola')
        store.add_match('a', 1400, 500, 'normal', 'you', 'burraco')
        store.add_match('a', 40, 80, 'hard', 'you', 'briscola')
        assert store.stats('a', 'briscola').avg_points == 60
        assert store.stats('a', 'briscola', 'normal').won == 1
        assert store.stats('a', 'burraco', 'hard').played == 0
        assert store.stats('a').played == 3


def test_preferences_roundtrip_and_bad_values():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'preferences.json'
        pref = Preferences(path)
        pref.data.update(language='it', speed='fast', deck='italian')
        pref.save()
        assert Preferences(path).data == pref.data
        path.write_text(json.dumps({'language': 'invalid', 'speed': [], 'target': -5}))
        restored = Preferences(path)
        assert restored.data['language'] == 'en'
        assert restored.data['speed'] == 'normal'


def test_hints_ignore_hidden_identities_and_do_not_mutate():
    for kind, cls in ENGINES.items():
        game = cls(seed=17)
        before = encode(game)
        hint = training.suggest(kind, game)
        assert encode(game) == before
        other = copy.deepcopy(game)
        # Preserve public sizes, but replace ALL hidden identities.
        other.hands[1] = [game.hands[0][0]] * len(other.hands[1])
        other.stock = [game.hands[0][0]] * len(other.stock)
        if kind == 'burraco':
            other.pots = [[game.hands[0][0]] * len(pot) for pot in other.pots]
        assert training.suggest(kind, other) == hint, kind


def test_burraco_hint_after_draw_is_legal_and_private():
    for seed in range(12):
        game = burraco.Game(seed=seed)
        game.draw(0)
        before = encode(game)
        result = training.suggest('burraco', game)
        assert result and before == encode(game)
        other = copy.deepcopy(game)
        other.hands[1].reverse()
        other.stock.reverse()
        assert training.suggest('burraco', other) == result


def test_italian_cards_and_training_messages():
    assert i18n.translate('Play Ace of Diamonds.', 'it', True) == 'Gioca Asso di denari.'
    assert i18n.translate('Start game', 'en') == 'Start game'
    assert i18n.translate('Start game', 'it') == 'Inizia partita'
    assert set(i18n.RULES_IT) == set(ENGINES)



def test_invalid_card_inventory_is_rejected():
    with tempfile.TemporaryDirectory() as folder:
        store = SessionStore(Path(folder) / 'session.json')
        game = briscola.Game(seed=12)
        game.hands[0][0] = game.hands[0][1]
        store.save(snapshot('briscola', game))
        try:
            store.load()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid card inventory accepted')


def test_v1_session_is_migrated_and_backed_up():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'session.json'
        game = briscola.Game(seed=12)
        payload = snapshot('briscola', game)
        payload.pop('training_used')
        path.write_text(json.dumps({'version': 1, 'state': encode(payload)}))
        store = SessionStore(path)
        restored = store.load()
        assert restored['training_used'] is False
        assert restored['sort_mode'] == 'suit'
        assert json.loads(path.read_text())['version'] == 2
        assert path.with_name('session.json.v1.bak').exists()


def test_v1_preferences_and_records_are_migrated_with_backups():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        preferences_path = path / 'preferences.json'
        preferences_path.write_text(json.dumps({'language': 'it', 'speed': 'fast'}))
        preferences = Preferences(preferences_path)
        assert preferences.data['language'] == 'it'
        assert json.loads(preferences_path.read_text())['version'] == 2
        assert preferences_path.with_name('preferences.json.v1.bak').exists()

        records_path = path / 'records.json'
        records_path.write_text(json.dumps({'version': 1, 'last_player': 'ada', 'players': {}}))
        records_store = records.Records(records_path, path / 'records.txt')
        assert records_store.current_player == 'ada'
        assert json.loads(records_path.read_text())['version'] == 2
        assert records_path.with_name('records.json.v1.bak').exists()


def test_replay_roundtrip_preserves_only_recorded_public_events():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'replay.json'
        replay = Replay('briscola')
        replay.add('trick', 0, 'A/di vs 2/he', ('A/di', '2/he'), 11)
        replay.save(path)
        loaded = Replay.load(path)
        assert loaded.visible_events() == replay.events
        raw = json.loads(path.read_text())
        raw['events'][0]['cards'].append('hidden-card')
        path.write_text(json.dumps(raw))
        loaded = Replay.load(path)
        assert 'hidden-card' in loaded.events[0].cards


if __name__ == '__main__':
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name, flush=True)
