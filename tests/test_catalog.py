"""Display-free checks for the shared game catalogue."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames import catalog, ui


def test_every_game_has_complete_menu_metadata():
    assert set(catalog.GAMES) == {
        ui.BRISCOLA, ui.BURRACO, ui.SCOPA, ui.TRESSETTE
    }
    for kind, spec in catalog.GAMES.items():
        assert spec.key == kind
        assert spec.levels
        assert set(spec.levels) <= set(spec.level_labels)
        assert set(spec.levels) <= set(spec.level_blurbs)
        assert spec.rules
        assert isinstance(spec.play_keys, str)


def test_only_series_games_offer_targets():
    assert catalog.spec_for(ui.BRISCOLA).targets == ()
    assert catalog.spec_for(ui.BURRACO).targets
    assert catalog.spec_for(ui.SCOPA).targets
    assert catalog.spec_for(ui.TRESSETTE).targets


def test_unknown_game_is_rejected_early():
    try:
        catalog.spec_for("not-a-game")
    except ValueError as exc:
        assert "not-a-game" in str(exc)
    else:
        raise AssertionError("unknown games must raise ValueError")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok   {name}")
