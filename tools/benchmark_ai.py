"""Reproducible expert timing sample: python tools/benchmark_ai.py [--samples 10]."""
import argparse
import random
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cardgames.briscola import ai as briscola_ai, engine as briscola
from cardgames.scopa import ai as scopa_ai, engine as scopa
from cardgames.tressette import ai as tressette_ai, engine as tressette


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=10)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    for name, create, choose in (
        ('Briscola', lambda seed: briscola.Game(seed, first_leader=1),
         lambda game, rng: briscola_ai.choose_card(game, 'hard', rng)),
        ('Scopa', lambda seed: scopa.Game(seed, first_player=1),
         lambda game, rng: scopa_ai.choose_move(game, 1, 'hard', rng)),
        ('Tressette', lambda seed: tressette.Game(seed, first_leader=1),
         lambda game, rng: tressette_ai.choose_card(game, 1, 'hard', rng)),
    ):
        times = []
        for seed in range(args.samples):
            game = create(seed)
            started = time.perf_counter()
            choose(game, random.Random(seed))
            times.append(1000 * (time.perf_counter() - started))
        print(f'{name}: {len(times)} initial positions, mean {statistics.mean(times):.1f} ms, max {max(times):.1f} ms')


if __name__ == '__main__':
    main()
