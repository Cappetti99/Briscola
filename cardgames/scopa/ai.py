"""How the computer plays Scopa.

Three levels, and the two that matter differ in what they can see. `NORMAL`
judges a move by what it takes and by what it leaves on the table for the
other side. `HARD` deals the cards it cannot see, plays each candidate move
out to the end of the hand a number of times, and keeps the one that scores
best on average — the same idea as Briscola's expert, and it works here for
the same reason: a hand of Scopa is short enough to finish quickly.
"""

import random
import time

from ..cards import Card, new_deck
from .engine import (COINS, HAND_SIZE, PLAYERS, PRIME, SETTEBELLO, VALUES,
                     Game, Play)

EASY, NORMAL, HARD = "easy", "normal", "hard"
LEVELS = (EASY, NORMAL, HARD)
LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal", HARD: "Expert"}

# What a captured card is worth to the heuristic. Cards and coins are points
# in their own right; the primiera is folded in at a fraction of its scale,
# which treats it as additive when it is not — a rough guide that costs far
# less than working the real thing out for every candidate move.
CARD_VALUE = 1.0
COIN_VALUE = 1.5
PRIME_VALUE = 0.10
SETTEBELLO_VALUE = 9.0
SCOPA_VALUE = 7.0

# Leaving a table the other side can sweep is the mistake that decides most
# hands between players of the same strength.
RISK_VALUE = 9.0
# A card left on the table is a card offered, but only until someone takes it.
EXPOSURE = 0.55

# The expert's sampling. Deals are cheap here, so the budget is what really
# decides how many get played.
WORLDS = 24
TIME_BUDGET = 0.9


def card_value(card: Card) -> float:
    """What taking this card is worth, before anything else is considered."""
    value = CARD_VALUE + PRIME_VALUE * PRIME[card.rank]
    if card.suit == COINS:
        value += COIN_VALUE
    if card == SETTEBELLO:
        value += SETTEBELLO_VALUE
    return value


def pile_value(cards) -> float:
    return sum(card_value(card) for card in cards)


def clearing_values(table: list[Card]) -> set[int]:
    """The card values that would take the whole table in one move.

    One card can always be taken by its own value. Two or more can only go
    together as a sum, and only when no single card on the table matches that
    sum: the obligation to take the single card first is what keeps a big
    table safe, and a table of one card is the least safe thing there is.
    """
    if not table:
        return set()
    if len(table) == 1:
        return {VALUES[table[0].rank]}
    total = sum(VALUES[card.rank] for card in table)
    if total > 10:
        return set()
    if any(VALUES[card.rank] == total for card in table):
        return set()
    return {total}


def sweep_risk(table: list[Card], unseen: list[Card], hand_size: int) -> float:
    """Roughly the chance the other side can clear this table next move."""
    values = clearing_values(table)
    if not values or not unseen:
        return 0.0
    matching = sum(1 for card in unseen if VALUES[card.rank] in values)
    if not matching:
        return 0.0
    return min(1.0, hand_size * matching / len(unseen))


def unseen_cards(game: Game, player: int) -> list[Card]:
    """Everything this player cannot account for: their hand and the stock."""
    known = set(game.hands[player]) | set(game.table)
    for side in PLAYERS:
        known |= set(game.captured[side])
    return [card for card in new_deck() if card not in known]


def legal_moves(game: Game, player: int) -> list[tuple[int, tuple[Card, ...]]]:
    """Every card that can be played, paired with every way of taking."""
    moves = []
    for index, card in enumerate(game.hands[player]):
        options = game.capture_options(card)
        if options:
            moves.extend((index, option) for option in options)
        else:
            moves.append((index, ()))
    return moves


def move_value(game: Game, player: int, index: int,
               taking: tuple[Card, ...], unseen: list[Card]) -> float:
    """What a move is worth: what it takes, less what it leaves behind."""
    card = game.hands[player][index]
    value = pile_value(taking) + (card_value(card) if taking else 0.0)

    table = [one for one in game.table if one not in taking]
    if taking:
        if not table and not _is_last_card(game, player):
            value += SCOPA_VALUE
    else:
        table = table + [card]
        value -= EXPOSURE * card_value(card)

    left = [one for one in unseen if one != card]
    value -= RISK_VALUE * sweep_risk(table, left, HAND_SIZE)
    return value


def _is_last_card(game: Game, player: int) -> bool:
    """Whether this play empties both hands and the stock, so no scopa."""
    if game.stock:
        return False
    return (len(game.hands[player]) == 1
            and not game.hands[1 - player])


def choose_move(game: Game, player: int, level: str,
                rng: random.Random | None = None):
    """Pick a card and the cards it takes, at the level asked for."""
    rng = rng or random
    moves = legal_moves(game, player)
    if not moves:
        raise RuntimeError("no card to play")
    if level == EASY:
        return rng.choice(moves)
    if level == HARD:
        return _search(game, player, moves, rng)
    return _greedy(game, player, moves, rng)


def _greedy(game, player, moves, rng):
    unseen = unseen_cards(game, player)
    best, best_value = [], None
    for move in moves:
        value = move_value(game, player, move[0], move[1], unseen)
        if best_value is None or value > best_value + 1e-9:
            best, best_value = [move], value
        elif value > best_value - 1e-9:
            best.append(move)
    return rng.choice(best)


# --- the expert -----------------------------------------------------------

def _search(game, player, moves, rng):
    """Play each move out in dealt-out worlds, and keep the best average.

    What a move is worth in Scopa depends almost entirely on the reply, and
    the reply depends on cards nobody has seen. Guessing them and playing on
    is the only way to price the difference between taking three small cards
    now and leaving the table safe.
    """
    if len(moves) == 1:
        return moves[0]
    unseen = unseen_cards(game, player)
    totals = [0.0] * len(moves)
    played = 0
    deadline = time.perf_counter() + TIME_BUDGET
    for _ in range(WORLDS):
        world_cards = list(unseen)
        rng.shuffle(world_cards)
        for index, move in enumerate(moves):
            world = _deal_world(game, player, world_cards)
            totals[index] += _play_out(world, player, move, rng)
        played += 1
        if time.perf_counter() > deadline:
            break
    best = max(range(len(moves)), key=lambda i: totals[i] / max(played, 1))
    return moves[best]


def _deal_world(game: Game, player: int, cards: list[Card]) -> Game:
    """A copy of the position with the unseen cards dealt out one way."""
    world = _clone(game)
    other = 1 - player
    hand_size = len(game.hands[other])
    world.hands[other] = cards[:hand_size]
    world.stock = cards[hand_size:]
    return world


def _clone(game: Game) -> Game:
    copy = Game.__new__(Game)
    copy.hands = [list(game.hands[0]), list(game.hands[1])]
    copy.table = list(game.table)
    copy.captured = [list(game.captured[0]), list(game.captured[1])]
    copy.scope = list(game.scope)
    copy.stock = list(game.stock)
    copy.turn = game.turn
    copy.last_capture = game.last_capture
    copy.swept = game.swept
    copy.first_player = game.first_player
    copy.seed = game.seed
    return copy


def _play_out(world: Game, player: int, move, rng) -> float:
    """Make the move, finish the hand with the greedy policy, and score it."""
    index, taking = move
    world.play(player, index, taking or None)
    guard = 0
    while not world.game_over and guard < 60:
        guard += 1
        turn = world.turn
        moves = legal_moves(world, turn)
        if not moves:
            break
        pick = _greedy(world, turn, moves, rng)
        world.play(turn, pick[0], pick[1] or None)
    world.sweep()
    scores = world.scores()
    return scores[player] - scores[1 - player]


# --- playing a turn -------------------------------------------------------

def take_turn(game: Game, player: int, level: str,
              rng: random.Random | None = None) -> Play:
    """Choose and play one card, and hand back what it did."""
    index, taking = choose_move(game, player, level, rng)
    return game.play(player, index, taking or None)


def describe(play: Play, you: bool = False) -> str:
    """One line for the move log, in the person it will be read in."""
    who, s = ("You", "") if you else ("The computer", "s")
    if not play.taken:
        return f"{who} play{s} {play.card.short()}"
    took = " ".join(card.short() for card in play.taken)
    line = f"{who} take{s} {took} with {play.card.short()}"
    return f"{line} - SCOPA" if play.scopa else line
