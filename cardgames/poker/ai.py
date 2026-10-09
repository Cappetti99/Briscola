"""How the computer plays Texas Hold'em.

Three levels, along the lines the other games use. `EASY` plays its own two
cards and little else. `NORMAL` works from what it is entitled to see — its
own hand, the board and the price of the next card — and never from the
opponent's hand or the deck, which is also what makes it safe to offer as a
training hint. `HARD` deals the cards it cannot see out again and again,
counts how often each of them wins, and plays the pot against that equity.
"""

import math
import random
import time
from collections import Counter
from itertools import combinations

from ..cards import ACE, Card
from .engine import (BIG_BLIND, FULL_HOUSE, FLUSH, FOUR, HIGH_CARD, PAIR,
                     PLAYERS, STRAIGHT, STRAIGHT_FLUSH, THREE, TWO_PAIR,
                     best_hand, poker_deck)

EASY, NORMAL, HARD = "easy", "normal", "hard"
LEVELS = (EASY, NORMAL, HARD)
LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal", HARD: "Expert"}

# What a made hand is roughly worth against a hand not yet seen, used by the
# level that may not look. It is an estimate, and deliberately coarser than
# the expert's counting: that difference is where the two levels differ.
CATEGORY_EQUITY = {
    HIGH_CARD: 0.34, PAIR: 0.52, TWO_PAIR: 0.72, THREE: 0.84, STRAIGHT: 0.90,
    FLUSH: 0.90, FULL_HOUSE: 0.97, FOUR: 0.99, STRAIGHT_FLUSH: 0.99,
}

# The expert's sampling: bounded by both, because a decision the window
# waits for is a decision it should not have to wait long for.
WORLDS = 900
TIME_BUDGET = 0.45


# --- what the normal level may see ---------------------------------------

def _preflop_strength(cards: list[Card]) -> float:
    """A Chen-style score for two cards, scaled to about the right equity.

    Points for the high card, doubled for a pair, two more for suited, less
    the gap between the ranks — the arithmetic behind starting-hand charts.
    """
    values = sorted((14 if card.rank == ACE else card.rank
                     for card in cards), reverse=True)
    base = {14: 10, 13: 8, 12: 7, 11: 6}
    points = [base.get(rank, rank / 2) for rank in values]
    if values[0] == values[1]:
        score = max(2 * max(points), 5)
    else:
        score = max(points)
        gap = values[0] - values[1] - 1
        score -= (0, 1, 2, 4)[gap] if gap <= 3 else 5
        # A little extra when the two can make a straight: it is the gap
        # that decides that, not the size of the cards.
        score += 1 if gap == 0 and values[0] <= 13 else 0
        score += 1 if gap == 1 and values[0] <= 12 else 0
        if len({card.suit for card in cards}) == 1:
            score += 2
    return max(0.0, min(1.0, (score + 1) / 21))


def _made_strength(game, player: int) -> float:
    """How the hand stands now, from the cards this player may look at."""
    key = best_hand(game.hands[player] + game.table)
    value = CATEGORY_EQUITY[key[0]]
    top = key[1]
    if key[0] in (HIGH_CARD, PAIR, TWO_PAIR, THREE):
        value += (top - 2) * 0.004
    if key[0] == PAIR and game.table:
        board_top = max(14 if card.rank == ACE else card.rank
                        for card in game.table)
        # A pair that sits above the board plays far better than one that
        # is counterfeited by every overcard still to come.
        value += 0.05 if top > board_top else 0.02 if top == board_top else 0.0
    return min(value, 0.97)


def _strength(game, player: int) -> float:
    """The normal level's whole world: own cards, board, nothing hidden."""
    if game.phase == "preflop":
        return _preflop_strength(game.hands[player])
    return _made_strength(game, player)


# --- sizes ----------------------------------------------------------------

def _size_to(game, player: int, target: int) -> int:
    """Clamp a wanted raise-to into the legal range: minimum, then all in."""
    return min(max(target, game.min_to(player)), game.max_to(player))


def _pot_raise(game, player: int) -> int:
    return _size_to(game, player, max(game.committed) + game.pot)


# --- the levels -----------------------------------------------------------

def choose_action(game, player: int, level: str,
                  rng: random.Random | None = None,
                  *, expert_budget: float = TIME_BUDGET
                  ) -> tuple[str, int | None]:
    """A legal action for this player at this level: (kind, raise size).

    Nothing here mutates the game — the expert runs on a copy of the state
    on a worker thread, and a hint must leave the table exactly as it found
    it.
    """
    rng = rng if rng is not None else random
    legal = game.legal_actions(player)
    if not legal:
        raise RuntimeError("no action is available here")
    if level == EASY:
        return _easy(game, player, legal, rng)
    if level == HARD:
        if not math.isfinite(expert_budget) or expert_budget <= 0:
            raise ValueError("expert_budget must be a finite positive number")
        return _expert(game, player, legal, rng, expert_budget)
    return _normal(game, player, legal, rng)


def take_turn(game, player: int, level: str,
              rng: random.Random | None = None,
              *, expert_budget: float = TIME_BUDGET) -> str:
    """Choose, play, and return the line for the move log.

    ``expert_budget`` is a keyword-only override used by benchmarks and
    simulations; normal game play keeps the production time limit.
    """
    action, amount = choose_action(game, player, level, rng,
                                   expert_budget=expert_budget)
    return game.act(player, action, amount)


def _easy(game, player, legal, rng):
    """Plays its cards, folds when it feels like it, and little else."""
    weights = {"fold": 3, "call": 4, "check": 6, "bet": 2, "raise": 2}
    kinds = sorted(legal)                      # a stable order to weigh by
    kind = rng.choices(kinds, weights=[weights.get(k, 1) for k in kinds])[0]
    if kind in ("bet", "raise"):
        return kind, _easy_size(game, player, rng)
    return kind, None


def _easy_size(game, player, rng):
    top = game.max_to(player)
    options = {game.min_to(player), _pot_raise(game, player)}
    if rng.random() < 0.10:                    # the occasional shove
        options.add(top)
    return rng.choice(sorted(options))


def _normal(game, player, legal, rng):
    """Prices its hand against the pot, from public information only.

    The one deliberate asymmetry: it never folds away a call that costs the
    minimum. Heads-up, one chip into a live pot is right with any two
    cards, and a bot that folds those is a bot you can steal from.
    """
    owed = game.to_call(player)
    strength = _strength(game, player)
    if owed > 0:
        if "raise" in legal and strength >= 0.72:
            return "raise", (_pot_raise(game, player) if strength >= 0.80
                             else game.min_to(player))
        price = owed / (game.pot + owed)
        if strength >= price + 0.05 or owed <= BIG_BLIND:
            return "call", None
        return ("fold", None) if "fold" in legal else ("call", None)
    if "bet" in legal and strength >= 0.60:
        return "bet", _size_to(game, player,
                               max(game.committed) + int(game.pot * 0.66))
    if "bet" in legal and strength >= 0.34 and rng.random() < 0.18:
        return "bet", game.min_to(player)      # a stab at a pot nobody wants
    return "check", None


def _expert(game, player, legal, rng, budget):
    """Estimate equity against the betting range and choose the best EV action."""
    won, _opponent_strength, opponent_hands = _equity_estimate(
        game, player, rng, budget)
    owed = game.to_call(player)
    pot = game.pot
    if owed > 0:
        price = min(owed, game.stacks[player])
        # Chips already committed are sunk. A call's return includes the
        # existing pot and the chips paid to call.
        candidates = [(0.0, "fold", None)] if "fold" in legal else []
        if "call" in legal:
            uncalled = owed - price
            final_pot = pot + price - uncalled
            candidates.append((won * final_pot - price, "call", None))
        if "raise" in legal:
            targets = {
                game.min_to(player),
                _pot_raise(game, player),
                game.max_to(player),
            }
            for target in sorted(targets):
                if target <= max(game.committed):
                    continue
                ev = _raise_ev(game, player, target, opponent_hands)
                candidates.append((ev, "raise", target))
        _ev, action, amount = max(candidates, key=lambda item: item[0])
        return action, amount

    candidates = [(won * pot, "check", None)]
    if "bet" in legal:
        targets = {
            game.min_to(player),
            _size_to(game, player,
                     max(game.committed) + int(pot * 0.66)),
            game.max_to(player),
        }
        for target in sorted(targets):
            if target <= max(game.committed):
                continue
            ev = _raise_ev(game, player, target, opponent_hands)
            candidates.append((ev, "bet", target))
    _ev, action, amount = max(candidates, key=lambda item: item[0])
    return action, amount


def _aggression_likelihood(strength: float, wager_fraction: float) -> float:
    """Likelihood that Normal bets or raises with a hand of this strength."""
    threshold = 0.60 + 0.04 * min(max(wager_fraction, 0.0), 2.0)
    exponent = max(-30.0, min(30.0, 9.0 * (strength - threshold)))
    return 0.04 + 0.92 / (1.0 + math.exp(-exponent))


def _normal_continues(game, player: int, target: int,
                      strength: float) -> bool:
    """Whether a Normal opponent continues with this holding and bet size."""
    opponent = 1 - player
    cost = target - game.committed[player]
    owed = max(0, target - game.committed[opponent])
    if owed == 0:
        return True
    price = owed / max(1, game.pot + cost + owed)
    can_raise = (game.stacks[opponent] > owed and not game.all_in[player])
    return (owed <= BIG_BLIND or strength >= price + 0.05
            or (can_raise and strength >= 0.72))


def _raise_ev(game, player: int, target: int,
              opponent_hands: tuple[tuple[float, float, float], ...]) -> float:
    """Approximate raise EV, including folds and called pots, net of new chips."""
    opponent = 1 - player
    cost = target - game.committed[player]
    opponent_call = min(max(0, target - game.committed[opponent]),
                        game.stacks[opponent])
    existing_gap = max(0, game.total[opponent] - game.total[player])
    matched_cost = min(cost, existing_gap + opponent_call)
    called_pot = game.pot + matched_cost + opponent_call
    total_weight = 0.0
    fold_weight = 0.0
    called_weight = 0.0
    called_wins = 0.0
    for strength, weight, outcome in opponent_hands:
        total_weight += weight
        if _normal_continues(game, player, target, strength):
            called_weight += weight
            called_wins += weight * outcome
        else:
            fold_weight += weight
    if total_weight == 0:
        return 0.0
    # Use equity conditional on the opponent continuing: a caller's range is
    # stronger than its full range. Unmatched chips are refunded on a fold,
    # so folding wins the existing pot without charging the new bet.
    return (fold_weight / total_weight * game.pot
            + called_wins / total_weight * called_pot
            - called_weight / total_weight * matched_cost)


# --- the expert's counting ------------------------------------------------

def unseen_cards(game, player: int) -> list[Card]:
    """Everything this player is not entitled to look at."""
    known = set(game.hands[player]) | set(game.table)
    return [card for card in poker_deck() if card not in known]


def _visible_strength(cards: list[Card], board: list[Card]) -> float:
    """Estimate a hand's current strength using only its cards and the board."""
    if not board:
        return _preflop_strength(cards)
    key = best_hand(cards + board)
    value = CATEGORY_EQUITY[key[0]]
    if key[0] in (HIGH_CARD, PAIR, TWO_PAIR, THREE):
        value += (key[1] - 2) * 0.004
    if key[0] == PAIR:
        board_top = max(14 if card.rank == ACE else card.rank for card in board)
        value += 0.05 if key[1] > board_top else 0.02 if key[1] == board_top else 0.0

    combined = cards + board
    if len(board) < 5:
        if max(Counter(card.suit for card in combined).values()) >= 4:
            value += 0.08
        ranks = {14 if card.rank == ACE else card.rank for card in combined}
        if 14 in ranks:
            ranks.add(1)
        if any(sum(rank in ranks for rank in range(low, low + 5)) == 4
               for low in range(1, 11)):
            value += 0.05
    return min(value, 0.99)


def _equity_estimate(game, player: int, rng: random.Random,
                     budget: float
                     ) -> tuple[float, float,
                                tuple[tuple[float, float, float], ...]]:
    """Return equity, mean opponent strength, and weighted sampled holdings."""
    unseen = unseen_cards(game, player)
    mine = game.hands[player]
    needed = 5 - len(game.table)
    opponent = 1 - player
    facing_wager = (game.to_call(player) > 0 and game.acted[opponent])
    wager_fraction = (game.to_call(player) /
                      max(1, game.pot - game.to_call(player)))
    weighted_wins = 0.0
    total_weight = 0.0
    weighted_strength = 0.0
    opponent_hands = []

    # The river has no future cards to sample. Enumerating all possible
    # opponent holdings is both exact and fast after direct hand evaluation.
    if needed == 0:
        worlds = ((list(hand), []) for hand in combinations(unseen, 2))
    else:
        deadline = time.perf_counter() + budget

        def sampled_worlds():
            for _ in range(WORLDS):
                if time.perf_counter() >= deadline:
                    return
                picked = rng.sample(unseen, 2 + needed)
                yield picked[:2], picked[2:]

        worlds = sampled_worlds()

    for opponent_hand, future_board in worlds:
        strength = _visible_strength(opponent_hand, game.table)
        weight = (_aggression_likelihood(strength, wager_fraction)
                  if facing_wager else 1.0)
        board = game.table + future_board
        mine_key = best_hand(mine + board)
        their_key = best_hand(opponent_hand + board)
        outcome = 1.0 if mine_key > their_key else 0.5 if mine_key == their_key else 0.0
        weighted_wins += outcome * weight
        weighted_strength += strength * weight
        total_weight += weight
        opponent_hands.append((strength, weight, outcome))

    if total_weight == 0:
        return 0.5, 0.5, ()
    return (weighted_wins / total_weight,
            weighted_strength / total_weight,
            tuple(opponent_hands))


def equity(game, player: int, rng: random.Random | None = None,
           budget: float = TIME_BUDGET) -> float:
    """How often this hand wins out to the river, over sampled worlds.

    Unknown opponent holdings are weighted by the likelihood of the action
    they just took. Future cards are sampled; on the river every opponent
    holding is evaluated. Hidden cards are never read from the game state.
    """
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("budget must be a finite positive number")
    rng = rng if rng is not None else random.Random(0)
    return _equity_estimate(game, player, rng, budget)[0]
