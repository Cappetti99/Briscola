"""Versioned JSON snapshots. Only explicitly registered game types are decoded."""
import json
from collections import Counter
from dataclasses import fields, is_dataclass
from pathlib import Path
from .storage import backup_once
from .cards import Card, new_deck, burraco_deck
from .match import Match
from .briscola import engine as briscola
from .burraco import engine as burraco
from .scopa import engine as scopa
from .tressette import engine as tressette

TYPES = {f'{cls.__module__}.{cls.__name__}': cls for cls in (
    Card, Match, briscola.Game, briscola.TrickResult, burraco.Game,
    burraco.Meld, burraco.Turn, scopa.Game, scopa.Play,
    tressette.Game, tressette.TrickResult, tressette.Declaration)}
ENGINES = {'briscola': briscola.Game, 'burraco': burraco.Game,
           'scopa': scopa.Game, 'tressette': tressette.Game}
VERSION = 2


def encode(value):
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, tuple):
        return {'tuple': [encode(v) for v in value]}
    if isinstance(value, dict):
        return {'dict': [[encode(k), encode(v)] for k, v in value.items()]}
    name = f'{type(value).__module__}.{type(value).__name__}'
    if name not in TYPES:
        raise ValueError(f'Unsupported snapshot type: {name}')
    return {'type': name, 'fields': {k: encode(v) for k, v in vars(value).items()}}


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {'tuple'}:
        return tuple(decode(v) for v in value['tuple'])
    if set(value) == {'dict'}:
        return {decode(k): decode(v) for k, v in value['dict']}
    if set(value) != {'type', 'fields'} or value['type'] not in TYPES:
        raise ValueError('Unknown snapshot type')
    cls = TYPES[value['type']]
    expected = ({field.name for field in fields(cls)} if is_dataclass(cls)
                else set(vars(cls())))
    if set(value['fields']) != expected:
        raise ValueError('Invalid snapshot fields')
    obj = cls.__new__(cls)
    for key, val in value['fields'].items():
        if key.startswith('_'):
            raise ValueError('Invalid snapshot field')
        object.__setattr__(obj, key, decode(val))
    return obj


class SessionStore:
    def __init__(self, path):
        self.path = Path(path)
        self._last = None

    def save(self, state):
        text = json.dumps({'version': VERSION, 'state': encode(state)}, ensure_ascii=False)
        if text == self._last and self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(text, encoding='utf-8')
        tmp.replace(self.path)
        self._last = text

    def load(self):
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            version = raw['version']
            if version not in (1, VERSION):
                raise ValueError('Unsupported save version')
            state = decode(raw['state'])
            if version == 1:
                # v1 predates the training marker and hand-order preference.
                state.setdefault('training_used', False)
                state.setdefault('sort_mode', 'suit')
                backup_once(self.path, '.v1.bak')
            required = {'game', 'game_kind', 'match', 'player', 'difficulty',
                        'target', 'next_leader', 'recorded', 'log_lines', 'training_used'}
            if not isinstance(state, dict) or not required <= state.keys():
                raise ValueError('Incomplete session')
            from .catalog import spec_for
            spec = spec_for(state['game_kind'])
            if state['difficulty'] not in spec.levels:
                raise ValueError('Invalid difficulty')
            if type(state['recorded']) is not bool or type(state['training_used']) is not bool:
                raise ValueError('Invalid session flags')
            if state['next_leader'] not in (0, 1) or type(state['target']) is not int:
                raise ValueError('Invalid match settings')
            if not isinstance(state['log_lines'], list) or any(
                    not isinstance(line, (tuple, list)) or len(line) != 2
                    or not all(isinstance(part, str) for part in line)
                    for line in state['log_lines']):
                raise ValueError('Invalid move log')
            game = state['game']
            cls = ENGINES[state['game_kind']]
            if type(game) is not cls or set(vars(game)) != set(vars(cls())):
                raise ValueError('Invalid game state')
            if game.turn not in (0, 1) or len(game.hands) != 2:
                raise ValueError('Invalid players')
            if not isinstance(state['player'], str) or not state['player']:
                raise ValueError('Invalid player')
            physical = list(game.stock) + [card for hand in game.hands for card in hand]
            if state['game_kind'] == 'burraco':
                physical += game.discards + [card for pot in game.pots for card in pot]
                physical += [card for side in game.melds for meld in side for card in meld.cards]
                deck = burraco_deck()
            else:
                physical += [card for pile in game.captured for card in pile]
                physical += (list(game.table) if state['game_kind'] == 'scopa'
                             else [card for _, card in game.table])
                if state['game_kind'] == 'briscola' and game.trump_card is not None:
                    physical.append(game.trump_card)
                deck = new_deck()
            if Counter(physical) != Counter(deck):
                raise ValueError('Invalid card inventory')
            # Exercise the core state properties before handing it to the UI.
            game.game_over
            if state['match'] is not None and type(state['match']) is not Match:
                raise ValueError('Invalid match')
            match = state['match']
            if state['game_kind'] != 'briscola' and match is None:
                raise ValueError('Missing match')
            if match is not None and (type(match.target) is not int or match.target < 0
                    or type(match.hands) is not int or match.hands < 0
                    or len(match.totals) != 2 or any(type(n) is not int for n in match.totals)):
                raise ValueError('Invalid scores')
            if version == 1:
                self.save(state)
            return state
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, AttributeError, ValueError, OSError, IndexError) as exc:
            raise ValueError('The saved game cannot be read.') from exc

    def clear(self):
        self.path.unlink(missing_ok=True)
        self._last = None
