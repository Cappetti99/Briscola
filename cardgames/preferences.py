"""Validated, atomic, local user preferences."""
import json
from pathlib import Path

DEFAULTS = {'language': 'en', 'speed': 'normal', 'deck': 'french',
            'game': 'briscola', 'difficulty': 'normal', 'target': 11,
            'sort': 'suit'}
CHOICES = {'language': ('it', 'en'), 'speed': ('slow', 'normal', 'fast'),
           'deck': ('french', 'italian'),
           'game': ('briscola', 'burraco', 'scopa', 'tressette'),
           'difficulty': ('easy', 'normal', 'hard'), 'sort': ('suit', 'rank')}
SPEEDS = {'slow': 1.6, 'normal': 1.0, 'fast': 0.35}


class Preferences:
    def __init__(self, path):
        self.path = Path(path)
        self.data = dict(DEFAULTS)
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                for key, choices in CHOICES.items():
                    if raw.get(key) in choices:
                        self.data[key] = raw[key]
                if type(raw.get('target')) is int and raw['target'] >= 0:
                    self.data['target'] = raw['target']
        except (OSError, ValueError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
        tmp.replace(self.path)
