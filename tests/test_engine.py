"""Engine and opponent checks: invariants over many simulated games."""

import random
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.briscola import ai
from cardgames.cards import KING, Card, new_deck
from cardgames.briscola.engine import (AI, HUMAN, TOTAL_POINTS, TRICKS_PER_GAME, Game,
                             beats_lead)


def play_full_game(seed: int, level: str = ai.NORMAL,
                   human_level: str = ai.NORMAL,
                   first_leader: int | None = None) -> Game:
    """Play a whole game with a policy on each side."""
    if first_leader is None:
        first_leader = random.Random(seed).choice((HUMAN, AI))
    game = Game(seed=seed, first_leader=first_leader)
    rng = random.Random(seed * 31 + 7)
    while not game.game_over:
        while not game.trick_complete:
            if game.turn == AI:
                index = ai.choose_card(game, level, rng)
            else:
                index = ai.choose_card(mirrored(game), human_level, rng)
            game.play_card(game.turn, index)
        game.resolve_trick()
    return game


def mirrored(game: Game) -> Game:
    """A copy of the position seen from the human seat.

    The opponent code always plays the AI seat, so swapping the seats in a
    copy lets both policies play a game without either one peeking at the
    other's hand. Indices returned for the copy are valid for the original,
    since the hands keep their order.
    """
    view = ai._clone(game)
    view.hands = [list(game.hands[AI]), list(game.hands[HUMAN])]
    view.points = [game.points[AI], game.points[HUMAN]]
    view.captured = [list(game.captured[AI]), list(game.captured[HUMAN])]
    view.table = [(1 - player, card) for player, card in game.table]
    view.turn = 1 - game.turn
    view.leader = 1 - game.leader
    return view


def test_deck_is_valid():
    deck = new_deck()
    assert len(deck) == 40
    assert len(set(deck)) == 40
    assert sum(card.points for card in deck) == TOTAL_POINTS


def test_beats_lead():
    trump = "Hearts"
    # Same suit: the stronger card wins.
    assert beats_lead(Card(7, "Spades"), Card(3, "Spades"), trump)
    assert not beats_lead(Card(1, "Spades"), Card(3, "Spades"), trump)
    # A trump beats another suit.
    assert beats_lead(Card(1, "Spades"), Card(2, "Hearts"), trump)
    # Different suits, no trump: the leader keeps the trick.
    assert not beats_lead(Card(2, "Spades"), Card(1, "Diamonds"), trump)
    # Trump against trump: strength decides.
    assert beats_lead(Card(4, "Hearts"), Card(KING, "Hearts"), trump)
    assert not beats_lead(Card(KING, "Hearts"), Card(4, "Hearts"), trump)


def test_full_games():
    for seed in range(300):
        game = play_full_game(seed)

        assert game.tricks_played == TRICKS_PER_GAME, f"seed {seed}"
        assert sum(game.points) == TOTAL_POINTS, f"seed {seed}: {game.points}"
        assert not game.hands[HUMAN] and not game.hands[AI]
        assert game.cards_left == 0
        assert not game.table

        # No card lost or duplicated.
        seen = Counter(game.captured[HUMAN] + game.captured[AI])
        assert sum(seen.values()) == 40, f"seed {seed}"
        assert set(seen.values()) == {1}, f"seed {seed}: duplicate cards"


def test_every_difficulty_plays_legally():
    # Ten games is four hundred decisions per level: legality is a property of
    # every move, so it does not need hundreds of hands to show up.
    with fewer_worlds():
        for level in ai.LEVELS:
            for seed in range(10):
                game = play_full_game(seed, level=level, human_level=level)
                assert sum(game.points) == TOTAL_POINTS, f"{level} seed {seed}"


def test_expert_is_the_strongest_level():
    """Every deal is played from both seats, so neither policy gets luckier.

    Judged on card points rather than on games won. Briscola is streaky, so
    over the handful of deals a quick test can afford, the win column swings
    far more than the points do — asserting on it would make the suite fail
    now and then for no reason at all.

    Points compress the gap, though: the expert wins about three games in four
    but takes only around 57 points in 100. So what is asserted here is the
    ordering, not its size, with enough room that a loaded machine — which can
    cut the expert's search short on its time budget — does not fail it.

    The cheaper pair gets many more deals, because it costs nothing.
    """
    with fewer_worlds():
        expert = head_to_head(ai.HARD, ai.NORMAL, deals=8)
        normal = head_to_head(ai.NORMAL, ai.EASY, deals=60)
    assert expert > 0.52, f"expert took only {expert:.1%} of the points"
    assert normal > 0.505, f"normal took only {normal:.1%} of the points"


def head_to_head(first: str, second: str, deals: int) -> float:
    """Share of the 120 card points `first` takes against `second`."""
    points = [0, 0]
    for seed in range(deals):
        for leader in (HUMAN, AI):
            for side, (a, b) in enumerate(((first, second), (second, first))):
                game = play_full_game(seed, level=a, human_level=b,
                                      first_leader=leader)
                # `a` sits in the AI seat, so the AI's points are `a`'s.
                points[side] += game.points[AI]
                points[1 - side] += game.points[HUMAN]
    return points[0] / sum(points)


@contextmanager
def fewer_worlds():
    """Shrink the expert's sampling so the test suite stays quick."""
    early, late = ai.WORLDS_EARLY, ai.WORLDS_LATE
    ai.WORLDS_EARLY, ai.WORLDS_LATE = 8, 12
    try:
        yield
    finally:
        ai.WORLDS_EARLY, ai.WORLDS_LATE = early, late


def test_card_counting_knows_the_last_hand():
    game = play_partial_game(seed=11)
    known = ai.known_opponent_hand(game)
    assert known is not None
    assert sorted(known, key=str) == sorted(game.hands[HUMAN], key=str)


def play_partial_game(seed: int) -> Game:
    """Play until the stock is empty, stopping between tricks."""
    game = Game(seed=seed, first_leader=HUMAN)
    while game.cards_left > 0 and not game.game_over:
        while not game.trick_complete:
            game.play_card(game.turn, 0)
        game.resolve_trick()
    return game


def test_hand_sizes_stay_consistent():
    game = Game(seed=7, first_leader=HUMAN)
    while not game.game_over:
        assert len(game.hands[HUMAN]) <= 3 and len(game.hands[AI]) <= 3
        while not game.trick_complete:
            game.play_card(game.turn, 0)
        before = game.cards_left
        game.resolve_trick()
        drawn = before - game.cards_left
        assert drawn in (0, 2), f"unexpected draw count: {drawn}"
        assert len(game.hands[HUMAN]) == len(game.hands[AI])


def test_turn_order_is_enforced():
    game = Game(seed=3, first_leader=HUMAN)
    try:
        game.play_card(AI, 0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("playing out of turn should fail")


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
