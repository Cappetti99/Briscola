"""Checks on the match records: json store plus the readable text log."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames import records


def fresh(tmp: Path) -> records.Records:
    return records.Records(path=tmp / "records.json", text_path=tmp / "records.txt")


def test_match_is_stored_and_reloaded():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        store = fresh(tmp)
        store.set_player("ada")
        store.add_match("ada", 73, 47, "normal", "you")

        again = fresh(tmp)
        assert again.current_player == "ada"
        matches = again.matches("ada")
        assert len(matches) == 1
        assert matches[0].you == 73 and matches[0].ai == 47
        assert matches[0].result == records.WIN


def test_text_log_is_appended():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        store = fresh(tmp)
        store.add_match("ada", 61, 59, "hard", "you")
        store.add_match("ada", 30, 90, "easy", "computer")

        lines = (tmp / "records.txt").read_text(encoding="utf-8").splitlines()
        body = [line for line in lines if not line.startswith("#")]
        assert len(body) == 2, lines
        assert "WIN" in body[0] and "61" in body[0] and "hard" in body[0]
        assert "LOSS" in body[1] and "easy" in body[1]


def test_results_and_stats():
    with tempfile.TemporaryDirectory() as tmp:
        store = fresh(Path(tmp))
        for you, ai_points in ((70, 50), (80, 40), (20, 100), (60, 60)):
            store.add_match("bob", you, ai_points, "normal", "you")

        stats = store.stats("bob")
        assert (stats.played, stats.won, stats.lost, stats.drawn) == (4, 2, 1, 1)
        assert stats.best == 80
        assert round(stats.win_rate) == 50
        assert stats.best_streak == 2
        assert stats.streak == 0            # last game was a draw
        assert stats.by_difficulty == {"normal": (2, 4)}


def test_streaks():
    with tempfile.TemporaryDirectory() as tmp:
        store = fresh(Path(tmp))
        for _ in range(3):
            store.add_match("cy", 70, 50, "normal", "you")
        assert store.stats("cy").streak == 3
        store.add_match("cy", 10, 110, "normal", "you")
        store.add_match("cy", 20, 100, "normal", "you")
        stats = store.stats("cy")
        assert stats.streak == -2
        assert stats.best_streak == 3


def test_players_are_separate():
    with tempfile.TemporaryDirectory() as tmp:
        store = fresh(Path(tmp))
        store.add_match("ada", 70, 50, "normal", "you")
        store.add_match("bob", 10, 110, "hard", "computer")
        assert store.players() == ["ada", "bob"]
        assert store.stats("ada").won == 1
        assert store.stats("bob").won == 0


def test_corrupt_file_does_not_crash():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "records.json").write_text("{not json", encoding="utf-8")
        store = fresh(tmp)
        assert store.players() == []
        store.add_match("ada", 70, 50, "normal", "you")
        assert len(fresh(tmp).matches("ada")) == 1


def test_empty_stats_are_safe():
    with tempfile.TemporaryDirectory() as tmp:
        stats = fresh(Path(tmp)).stats("nobody")
        assert stats.played == 0
        assert stats.win_rate == 0.0
        assert stats.avg_points == 0.0
        assert stats.summary() == "no games yet"
        assert stats.streak_text() == "-"


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
