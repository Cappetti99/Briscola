"""Per-player match records, saved locally.

Two files are written side by side:

* `records.json` - the structured store the app reads back.
* `records.txt`  - a plain-text log, one line per match, appended as you play.

Default folder is `~/.briscola/`. Override with the environment variables
`BRISCOLA_RECORDS` (json) and `BRISCOLA_RECORDS_TXT` (text).
"""

import getpass
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

VERSION = 1

WIN, LOSS, DRAW = "win", "loss", "draw"

RESULT_LABELS = {WIN: "WIN", LOSS: "LOSS", DRAW: "DRAW"}


def default_json_path() -> Path:
    override = os.environ.get("BRISCOLA_RECORDS")
    return Path(override) if override else Path.home() / ".briscola" / "records.json"


def default_text_path() -> Path:
    override = os.environ.get("BRISCOLA_RECORDS_TXT")
    if override:
        return Path(override)
    return default_json_path().with_suffix(".txt")


def default_player() -> str:
    try:
        return getpass.getuser() or "player"
    except Exception:
        return "player"


@dataclass
class Match:
    """One finished game."""

    date: str
    you: int
    ai: int
    result: str
    difficulty: str
    opened: str  # "you" or "computer"
    game: str = "briscola"      # defaulted, so rows written before this load

    @property
    def when(self) -> datetime:
        try:
            return datetime.fromisoformat(self.date)
        except ValueError:
            return datetime.min

    def label(self) -> str:
        return f"{self.when:%d %b %H:%M}"

    def text_line(self, player: str) -> str:
        return (f"{self.when:%Y-%m-%d %H:%M}  {player:<16} {self.game:<9} "
                f"{RESULT_LABELS.get(self.result, self.result):<5} "
                f"{self.you:>4} - {self.ai:<4} "
                f"difficulty={self.difficulty:<6} opened={self.opened}")


@dataclass
class Stats:
    """Summary of a player's matches."""

    played: int = 0
    won: int = 0
    lost: int = 0
    drawn: int = 0
    points_for: int = 0
    points_against: int = 0
    best: int = 0
    streak: int = 0       # >0 wins in a row, <0 losses in a row
    best_streak: int = 0
    by_difficulty: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return 100.0 * self.won / self.played if self.played else 0.0

    @property
    def avg_points(self) -> float:
        return self.points_for / self.played if self.played else 0.0

    def summary(self) -> str:
        if not self.played:
            return "no games yet"
        return (f"{self.played} played - {self.won}W {self.lost}L {self.drawn}D"
                f"  ({self.win_rate:.0f}% won)")

    def streak_text(self) -> str:
        if self.streak > 0:
            return f"{self.streak} win{'s' if self.streak > 1 else ''} in a row"
        if self.streak < 0:
            return f"{-self.streak} loss{'es' if self.streak < -1 else ''} in a row"
        return "-"


class Records:
    """Reads and writes the record files."""

    def __init__(self, path: Path | None = None, text_path: Path | None = None):
        self.path = Path(path) if path else default_json_path()
        self.text_path = Path(text_path) if text_path else default_text_path()
        self.data: dict = {"version": VERSION, "last_player": None, "players": {}}
        self.load()

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            return  # first run, or an unreadable file: start from scratch
        if isinstance(raw, dict) and isinstance(raw.get("players"), dict):
            self.data = {
                "version": raw.get("version", VERSION),
                "last_player": raw.get("last_player"),
                "players": raw["players"],
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.path)

    def append_text(self, player: str, match: Match) -> None:
        """Append one readable line to the .txt log."""
        self.text_path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.text_path.exists()
        with self.text_path.open("a", encoding="utf-8") as handle:
            if new_file:
                handle.write("# Card games match log\n")
                handle.write("# date time        player           game      "
                             "result   you -  ai   settings\n")
            handle.write(match.text_line(player) + "\n")

    # --- players ----------------------------------------------------------

    def players(self) -> list[str]:
        return sorted(self.data["players"])

    @property
    def current_player(self) -> str:
        name = self.data.get("last_player")
        return name if name else default_player()

    def set_player(self, name: str) -> str:
        name = (name or "").strip() or default_player()
        self.data["last_player"] = name
        self._player_entry(name)
        self.save()
        return name

    def _player_entry(self, name: str) -> dict:
        players = self.data["players"]
        if name not in players:
            players[name] = {"created": datetime.now().isoformat(timespec="seconds"),
                             "matches": []}
        return players[name]

    # --- matches ----------------------------------------------------------

    def add_match(self, name: str, you: int, ai: int, difficulty: str,
                  opened: str, game: str = "briscola") -> Match:
        result = WIN if you > ai else LOSS if you < ai else DRAW
        match = Match(date=datetime.now().isoformat(timespec="seconds"),
                      you=you, ai=ai, result=result,
                      difficulty=difficulty, opened=opened, game=game)
        entry = self._player_entry(name)
        entry["matches"].append(asdict(match))
        self.data["last_player"] = name
        self.save()
        self.append_text(name, match)
        return match

    def matches(self, name: str, game: str | None = None,
                difficulty: str | None = None) -> list[Match]:
        entry = self.data["players"].get(name)
        if not entry:
            return []
        out = []
        for raw in entry.get("matches", []):
            try:
                match = Match(**raw)
                if game is not None and match.game != game:
                    continue
                if difficulty is not None and match.difficulty != difficulty:
                    continue
                out.append(match)
            except TypeError:
                continue  # rows written by another version: skip them
        return out

    def stats(self, name: str, game: str | None = None,
              difficulty: str | None = None) -> Stats:
        stats = Stats()
        matches = self.matches(name, game, difficulty)
        for match in matches:
            stats.played += 1
            stats.points_for += match.you
            stats.points_against += match.ai
            stats.best = max(stats.best, match.you)
            if match.result == WIN:
                stats.won += 1
            elif match.result == LOSS:
                stats.lost += 1
            else:
                stats.drawn += 1
            won, total = stats.by_difficulty.get(match.difficulty, (0, 0))
            stats.by_difficulty[match.difficulty] = (
                won + (1 if match.result == WIN else 0), total + 1)

        stats.streak = _current_streak(matches)
        stats.best_streak = _best_streak(matches)
        return stats


def _current_streak(matches: list[Match]) -> int:
    streak = 0
    for match in reversed(matches):
        if match.result == WIN and streak >= 0:
            streak += 1
        elif match.result == LOSS and streak <= 0:
            streak -= 1
        else:
            break
    return streak


def _best_streak(matches: list[Match]) -> int:
    best = run = 0
    for match in matches:
        run = run + 1 if match.result == WIN else 0
        best = max(best, run)
    return best
