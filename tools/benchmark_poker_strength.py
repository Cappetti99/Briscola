"""Compare Poker AI levels over reproducible, position-balanced hands.

Run with ``conda run -n briscola python tools/benchmark_poker_strength.py``.
The Expert's equity sampler has a shorter budget here than in the app so a
large sample finishes in a reasonable time. Increase ``--expert-budget`` for
more accurate Expert decisions, or ``--hands`` for a larger comparison.
"""

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.poker import ai, engine


LEVELS = (ai.EASY, ai.NORMAL, ai.HARD)


def play_hand(seed, first_player, levels, rng, expert_budget):
    game = engine.Game(seed=seed, first_player=first_player)
    original_equity = ai.equity

    def bounded_equity(state, player, decision_rng=None, budget=ai.TIME_BUDGET):
        return original_equity(
            state, player, decision_rng,
            budget=min(budget, expert_budget),
        )

    ai.equity = bounded_equity
    try:
        for _ in range(100):
            if game.game_over:
                break
            player = game.turn
            ai.take_turn(game, player, levels[player], rng)
        if not game.game_over:
            raise RuntimeError(f"hand did not finish (seed={seed})")
    finally:
        ai.equity = original_equity
    return game.stacks


def compare(level_a, level_b, hands, expert_budget, base_seed):
    outcomes = []
    chip_deltas = []
    chips_a = 0
    chips_b = 0
    a_wins = b_wins = ties = 0

    for index in range(hands):
        seed = base_seed + index
        # Play the same shuffled deal with the level assignments swapped.
        # The button alternates between the paired hands as an additional
        # balance against first-to-act advantage.
        for swap in (False, True):
            a_player = (index + int(swap)) % 2
            assignment = [None, None]
            assignment[a_player] = level_a
            assignment[1 - a_player] = level_b
            button = (index + int(swap)) % 2
            rng = random.Random(seed * 2 + int(swap) + 100_000)
            stacks = play_hand(seed, button, assignment, rng, expert_budget)
            a_stack = stacks[a_player]
            b_stack = stacks[1 - a_player]
            delta = a_stack - b_stack
            chips_a += a_stack
            chips_b += b_stack
            chip_deltas.append(delta)
            if delta > 0:
                a_wins += 1
            elif delta < 0:
                b_wins += 1
            else:
                ties += 1
            outcomes.append(delta)

    total = len(outcomes)
    score_share = chips_a / (chips_a + chips_b) * 100
    mean_delta = statistics.mean(chip_deltas)
    sd = statistics.stdev(chip_deltas) if total > 1 else 0.0
    margin = 1.96 * sd / total ** 0.5
    print(
        f"{ai.LEVEL_LABELS[level_a]:6} vs {ai.LEVEL_LABELS[level_b]:6} | "
        f"{a_wins:3}-{b_wins:3}-{ties:3} wins/ties | "
        f"stack {chips_a / total:.1f}-{chips_b / total:.1f} | "
        f"score share {score_share:.1f}% | "
        f"mean chip margin {mean_delta:+.1f} "
        f"(95% CI {mean_delta - margin:+.1f} to {mean_delta + margin:+.1f})"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hands', type=int, default=100,
                        help='paired deals per matchup (default: 100)')
    parser.add_argument('--expert-budget', type=float, default=0.02,
                        help='seconds per Expert equity decision (default: 0.02)')
    parser.add_argument('--seed', type=int, default=20261006,
                        help='first deterministic deal seed')
    args = parser.parse_args()
    if args.hands < 1:
        parser.error('--hands must be positive')
    if args.expert_budget <= 0:
        parser.error('--expert-budget must be positive')

    print(f"{args.hands * 2} hands per matchup; Expert budget "
          f"{args.expert_budget * 1000:.0f} ms per decision")
    started = time.perf_counter()
    for first, second in ((ai.EASY, ai.NORMAL), (ai.EASY, ai.HARD),
                          (ai.NORMAL, ai.HARD)):
        compare(first, second, args.hands, args.expert_budget, args.seed)
    print(f"Elapsed: {time.perf_counter() - started:.1f} s")


if __name__ == '__main__':
    main()
