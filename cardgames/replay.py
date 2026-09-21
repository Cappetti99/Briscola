"""Public move recordings that can be reviewed without revealing hidden cards."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

VERSION = 1


@dataclass(frozen=True)
class Event:
    kind: str
    player: int
    text: str
    cards: tuple[str, ...] = ()
    value: int = 0


@dataclass
class Replay:
    game: str
    date: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    events: list[Event] = field(default_factory=list)

    def add(self, kind: str, player: int, text: str,
            cards: tuple[str, ...] = (), value: int = 0) -> None:
        self.events.append(Event(kind, player, text, tuple(cards), value))

    def visible_events(self) -> list[Event]:
        return list(self.events)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": VERSION, "game": self.game, "date": self.date,
                   "events": [asdict(event) for event in self.events]}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Replay":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("version") != VERSION or not isinstance(raw.get("game"), str):
            raise ValueError("Unsupported replay version")
        events = []
        for item in raw.get("events", []):
            if not isinstance(item, dict) or item.get("player") not in (0, 1):
                raise ValueError("Invalid replay event")
            cards = item.get("cards", [])
            if not isinstance(cards, list) or not all(isinstance(card, str) for card in cards):
                raise ValueError("Invalid replay cards")
            events.append(Event(item.get("kind", "move"), item["player"],
                                item.get("text", ""), tuple(cards), item.get("value", 0)))
        return cls(raw["game"], raw.get("date", ""), events)


def replay_path(records_path: Path) -> Path:
    return Path(records_path).with_name("last-replay.json")
