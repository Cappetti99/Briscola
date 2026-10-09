"""How the computer plays Texas Hold'em.

Three levels, along the lines the other games use. `EASY` plays its own two
cards and little else. `NORMAL` works from what it is entitled to see — its
own hand, the board and the price of the next card — and never from the
opponent's hand or the deck, which is also what makes it safe to offer as a
training hint. `HARD` deals the cards it cannot see out again and again,
counts how often each of them wins, and plays the pot against that equity.
"""

import random
import time

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
                  rng: random.Random | None = None) -> tuple[str, int | None]:
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
        return _expert(game, player, legal, rng)
    return _normal(game, player, legal, rng)


def take_turn(game, player: int, level: str,
              rng: random.Random | None = None) -> str:
    """Choose, play, and return the line for the move log."""
    action, amount = choose_action(game, player, level, rng)
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


def _expert(game, player, legal, rng):
    """Counts the unseen cards, then plays the price against the equity."""
    won = equity(game, player, rng)
    owed = game.to_call(player)
    pot = game.pot
    if owed > 0:
        price = min(owed, game.stacks[player])
        # A call wins the whole pot with the hand it holds and pays its own
        # way in chips not yet in; the chips already committed are spent
        # either way and do not enter the decision.
        ev_call = won * (pot + price) - price
        if won >= 0.72 and "raise" in legal:
            return "raise", _pot_raise(game, player)
        if ev_call > 0 and "call" in legal:
            return "call", None
        if ("raise" in legal and 0.42 <= won < 0.72
                and rng.random() < 0.12):
            return "raise", game.min_to(player)   # a semi-bluff with a draw
        return ("fold", None) if "fold" in legal else ("call", None)
    if "bet" in legal and won >= 0.62:
        return "bet", _size_to(game, player,
                               max(game.committed) + int(pot * 0.66))
    if "bet" in legal and won >= 0.30 and rng.random() < 0.15:
        return "bet", game.min_to(player)         # a bluff at the pot
    return "check", None


# --- the expert's counting ------------------------------------------------

def unseen_cards(game, player: int) -> list[Card]:
    """Everything this player is not entitled to look at."""
    known = set(game.hands[player]) | set(game.table)
    return [card for card in poker_deck() if card not in known]


def equity(game, player: int, rng: random.Random | None = None,
           budget: float = TIME_BUDGET) -> float:
    """How often this hand wins out to the river, over sampled worlds.

    The opponent's cards and the cards still to come are dealt from what
    cannot be seen, so no hidden identity is ever read — only counted over,
    the way the other games' experts sample the hands they are dealt.
    """
    rng = rng if rng is not None else random.Random(0)
    unseen = unseen_cards(game, player)
    needed = 5 - len(game.table)
    mine = game.hands[player]
    wins = 0.0
    samples = 0
    deadline = time.perf_counter() + budget
    while samples < WORLDS and time.perf_counter() < deadline:
        picked = rng.sample(unseen, 2 + needed)
        board = game.table + picked[2:]
        if not board:
            break
        their_key = best_hand(picked[:2] + board)
        my_key = best_hand(mine + board)
        wins += 1.0 if my_key > their_key else 0.5 if my_key == their_key else 0.0
        samples += 1
    return wins / samples if samples else 0.5
