"""How the computer plays Tressette.

The obligation to follow suit does most of the work: with no trump, a trick
is decided inside one suit, so what matters is which cards of a suit are
still out and who holds the one that commands it. `NORMAL` works that out
card by card. `HARD` deals the cards it cannot see and plays the deal to the
end a number of times, keeping the card that scores best on average.
"""

import random
import time

from ..cards import Card, new_deck
from .engine import PLAYERS, STRENGTH, THIRDS, Game, beats_lead

EASY, NORMAL, HARD = "easy", "normal", "hard"
LEVELS = (EASY, NORMAL, HARD)
LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal", HARD: "Expert"}

# Weights for the greedy level, in thirds of a point unless said otherwise.
COMMAND_VALUE = 2.2         # leading a card nothing out there beats
LENGTH_VALUE = 0.35         # and leading the suit you are longest in
EXPOSURE = 1.6              # what a card worth thirds costs when it can lose
LAST_TRICK_PULL = 2.0       # the last trick is worth three thirds on its own

# The expert's sampling.
WORLDS = 20
TIME_BUDGET = 0.9


def unseen_cards(game: Game, player: int) -> list[Card]:
    """What this player cannot account for: the other hand and the stock."""
    known = set(game.hands[player])
    known |= {card for _who, card in game.table}
    for side in PLAYERS:
        known |= set(game.captured[side])
    return [card for card in new_deck() if card not in known]


def commands(card: Card, unseen: list[Card]) -> bool:
    """Whether nothing still out there beats this card in its own suit."""
    return not any(one.suit == card.suit
                   and STRENGTH[one.rank] > STRENGTH[card.rank]
                   for one in unseen)


def choose_card(game: Game, player: int, level: str,
                rng: random.Random | None = None) -> int:
    """Which card to play, as an index into the player's hand."""
    rng = rng or random
    legal = game.legal_cards(player)
    if not legal:
        raise RuntimeError("no card to play")
    if len(legal) == 1:
        return legal[0]
    if level == EASY:
        return rng.choice(legal)
    if level == HARD:
        return _search(game, player, legal, rng)
    return _greedy(game, player, legal, rng)


# --- the greedy level -----------------------------------------------------

def _greedy(game, player, legal, rng):
    unseen = unseen_cards(game, player)
    scored = [(_value(game, player, index, unseen), index) for index in legal]
    best = max(value for value, _index in scored)
    return rng.choice([index for value, index in scored if value >= best - 1e-9])


def _value(game: Game, player: int, index: int, unseen: list[Card]) -> float:
    hand = game.hands[player]
    card = hand[index]
    if game.lead_card is None:
        return _lead_value(game, player, card, unseen)
    return _follow_value(game, player, card, unseen)


def _lead_value(game, player, card, unseen):
    """Leading: take the trick if you can, and give nothing away if you cannot."""
    hand = game.hands[player]
    value = 0.0
    length = sum(1 for one in hand if one.suit == card.suit)
    if commands(card, unseen):
        # The trick is yours, so the thirds on the card come back to you and
        # the other side has to answer in suit.
        value += COMMAND_VALUE + THIRDS[card.rank] + LENGTH_VALUE * length
        if _endgame(game):
            value += LAST_TRICK_PULL
    else:
        # Anything can happen to it, so lead the card that costs least.
        value -= EXPOSURE * THIRDS[card.rank]
        value -= 0.20 * STRENGTH[card.rank]
        value += LENGTH_VALUE * length
    return value


def _follow_value(game, player, card, unseen):
    """Answering: what the trick is worth, less what the card costs."""
    lead = game.lead_card
    pot = THIRDS[lead.rank]
    mine = THIRDS[card.rank]
    if beats_lead(lead, card):
        value = pot + mine
        if _endgame(game):
            value += LAST_TRICK_PULL
        # Win with the cheapest card that does it: spending the three on a
        # trick a knave would have taken is how a hand is thrown away.
        value -= 0.35 * STRENGTH[card.rank]
        if pot == 0 and mine > 0:
            value -= EXPOSURE * mine      # nothing to win, and a card spent
        return value
    # Losing the trick: give away as little as possible.
    return -EXPOSURE * mine - 0.05 * STRENGTH[card.rank]


def _endgame(game: Game) -> bool:
    """The last trick carries three thirds, so it is worth chasing."""
    return not game.stock and len(game.hands[game.turn]) <= 2


# --- the expert -----------------------------------------------------------

def _search(game, player, legal, rng):
    """Deal out the unseen cards, play each candidate to the end, average."""
    unseen = unseen_cards(game, player)
    totals = [0.0] * len(legal)
    played = 0
    deadline = time.perf_counter() + TIME_BUDGET
    for _ in range(WORLDS):
        cards = list(unseen)
        rng.shuffle(cards)
        for slot, index in enumerate(legal):
            world = _deal_world(game, player, cards)
            totals[slot] += _play_out(world, player, index, rng)
        played += 1
        if time.perf_counter() > deadline:
            break
    best = max(range(len(legal)), key=lambda slot: totals[slot] / max(played, 1))
    return legal[best]


def _deal_world(game: Game, player: int, cards: list[Card]) -> Game:
    world = _clone(game)
    other = 1 - player
    held = len(game.hands[other])
    world.hands[other] = cards[:held]
    world.stock = cards[held:]
    return world


def _clone(game: Game) -> Game:
    copy = Game.__new__(Game)
    copy.hands = [list(game.hands[0]), list(game.hands[1])]
    copy.stock = list(game.stock)
    copy.thirds = list(game.thirds)
    copy.bonus = list(game.bonus)
    copy.declared = game.declared
    copy.captured = [list(game.captured[0]), list(game.captured[1])]
    copy.table = list(game.table)
    copy.leader = game.leader
    copy.first_leader = game.first_leader
    copy.turn = game.turn
    copy.tricks_played = game.tricks_played
    copy.drawn = dict(game.drawn)
    copy.history = []
    return copy


def _play_out(world: Game, player: int, index: int, rng) -> float:
    """Play the card, finish the deal greedily, and count the thirds."""
    world.play_card(player, index)
    guard = 0
    while not world.game_over and guard < 60:
        guard += 1
        if world.trick_complete:
            world.resolve_trick()
            continue
        turn = world.turn
        legal = world.legal_cards(turn)
        if not legal:
            break
        world.play_card(turn, _greedy(world, turn, legal, rng))
    if world.trick_complete:
        world.resolve_trick()
    return world.thirds[player] - world.thirds[1 - player]


def describe(result, you: bool = False) -> str:
    """One line for the move log, once a trick has been resolved."""
    who = "You take" if you else "The computer takes"
    points = result.thirds
    return f"{who} the trick (+{points} third{'' if points == 1 else 's'})"
