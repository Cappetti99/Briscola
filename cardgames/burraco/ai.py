"""The computer's Burraco play: greedy, but it knows what a meld is worth."""

import random

from ..cards import RANKS, SUITS, Card
from .engine import (AI, MIN_MELD, CARD_POINTS, Game, InvalidMeld, Meld,
                     Stranded, build_meld, can_extend, is_wild,
                     wild_stands_for)

EASY, NORMAL = "easy", "normal"
LEVELS = (EASY, NORMAL)
LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal"}

# Taking the whole discard pile is worth it when enough of it is usable.
PILE_MIN_USEFUL = 2

# Past this many cards a hand is a burden: taking the pile only makes it worse.
HAND_TOO_BIG = 16


def take_turn(game: Game, player: int, level: str = NORMAL,
              rng: random.Random | None = None) -> list[str]:
    """Play one full turn and report what was done, for the move log."""
    rng = rng or random.Random()
    moves = []

    moves.append(_draw_phase(game, player, level))
    if game.game_over:
        return moves

    if level != EASY:
        moves += _substitutions(game, player)
    had_pot = game.pot_taken[player]
    moves += _meld_phase(game, player, level)
    if game.pot_taken[player] and not had_pot:
        moves.append("empties the hand and takes the pot")
        moves += _meld_phase(game, player, level)      # carry on with the pot

    if game.game_over:
        return moves
    if game.hands[player]:
        card = _card_to_discard(game, player)
        game.discard(player, card)
        moves.append(f"discards {card}")
    else:
        game.end_turn(player)
        moves.append("ends with an empty hand")
    return moves


# --- drawing --------------------------------------------------------------

def _draw_phase(game: Game, player: int, level: str) -> str:
    if game.discards and _pile_is_worth_taking(game, player, level):
        taken = game.take_discards(player)
        return f"takes the pile ({len(taken)} cards)"
    try:
        card = game.draw(player)
    except RuntimeError:
        return "cannot draw: the stock is out"
    return f"draws {card}"


def _pile_is_worth_taking(game: Game, player: int, level: str) -> bool:
    """Take the pile only when it really pays.

    Being greedy about it is a trap: the pile only ever grows the hand, so a
    player who keeps taking it never runs out of cards, never closes, and the
    stock never drains — the hand simply never ends.
    """
    pile = game.discards
    hand = game.hands[player]
    if game.may_close(player) and len(hand) <= 2:
        return False                    # so close: do not bury it in cards
    if len(hand) > HAND_TOO_BIG:
        return False                    # cards you cannot shed are a liability
    if level == EASY:
        return len(pile) >= 6

    # Count only what can go straight down on the table. Judging by "fits
    # somewhere in my hand" instead is what made this run away: the bigger the
    # hand, the more of the pile looked useful, so the pile was always taken,
    # the hand grew again, and the stock never drained.
    useful = sum(1 for card in pile if _can_use_now(game, player, card))
    return useful >= PILE_MIN_USEFUL or (len(pile) <= 4 and useful >= 1)


def _can_use_now(game: Game, player: int, card: Card) -> bool:
    """Cards that go down this turn, not cards that might one day be handy."""
    if is_wild(card):
        return True
    return any(can_extend(meld, card) for meld in game.melds[player])


def _fits_anything(game: Game, player: int, hand: list[Card], card: Card) -> bool:
    if is_wild(card):
        return True
    if any(can_extend(meld, card) for meld in game.melds[player]):
        return True
    same_rank = sum(1 for other in hand if other.rank == card.rank)
    neighbours = sum(1 for other in hand
                     if other.suit == card.suit and abs(other.rank - card.rank) <= 2)
    return same_rank >= 1 or neighbours >= 1


# --- melding --------------------------------------------------------------

def _substitutions(game: Game, player: int) -> list[str]:
    """Swap a natural card in and take the wild back: it is worth more free."""
    moves = []
    for meld in list(game.melds[player]):
        for card in wild_stands_for(meld):
            if card in game.hands[player]:
                wild = game.substitute_wild(player, meld, card)
                moves.append(f"puts the {card} back and frees the {wild}")
                break
    return moves


def _meld_phase(game: Game, player: int, level: str) -> list[str]:
    moves = []
    # Grow what is already down first: cheap points, and it builds burracos.
    for meld in list(game.melds[player]):
        for card in list(game.hands[player]):
            if can_extend(meld, card):
                try:
                    game.extend_meld(player, meld, [card])
                except (InvalidMeld, Stranded):
                    continue        # it would leave nothing to discard
                moves.append(f"adds {card} to a {meld.kind}")

    for cards in _find_melds(list(game.hands[player]), greedy_wilds=level != EASY):
        try:
            meld = game.lay_meld(player, cards)
        except (InvalidMeld, RuntimeError, Stranded):
            continue
        moves.append(f"lays down a {meld.kind} of {len(meld)}")
    return moves


def _find_melds(hand: list[Card], greedy_wilds: bool = True) -> list[list[Card]]:
    """Pick melds out of a hand: long runs first, then sets."""
    left = list(hand)
    found = []

    for finder in (_longest_run, _best_set):
        while True:
            cards = finder(left)
            if not cards:
                break
            found.append(cards)
            for card in cards:
                left.remove(card)

    if greedy_wilds:
        wilds = [card for card in left if is_wild(card)]
        if wilds:
            cards = _pair_plus_wild(left, wilds[0])
            if cards:
                found.append(cards)
    return found


def _longest_run(cards: list[Card]) -> list[Card] | None:
    best = None
    for suit in SUITS:
        ranks = sorted({card.rank for card in cards
                        if card.suit == suit and not is_wild(card)})
        run = []
        for rank in ranks:
            if run and rank == run[-1] + 1:
                run.append(rank)
            else:
                run = [rank]
            if len(run) >= MIN_MELD and (best is None or len(run) > len(best[1])):
                best = (suit, list(run))
    if best is None:
        return None
    suit, ranks = best
    return [next(card for card in cards
                 if card.suit == suit and card.rank == rank) for rank in ranks]


def _best_set(cards: list[Card]) -> list[Card] | None:
    for rank in sorted(RANKS, key=lambda r: -CARD_POINTS[r]):
        same = [card for card in cards if card.rank == rank and not is_wild(card)]
        if len(same) >= MIN_MELD:
            return same[:len(same)]
    return None


def _pair_plus_wild(cards: list[Card], wild: Card) -> list[Card] | None:
    """Spend a wild card only to turn a pair into a meld worth having."""
    for rank in sorted(RANKS, key=lambda r: -CARD_POINTS[r]):
        same = [card for card in cards if card.rank == rank and not is_wild(card)]
        if len(same) == 2:
            candidate = same + [wild]
            try:
                build_meld(candidate)
            except InvalidMeld:
                continue
            return candidate
    return None


# --- discarding -----------------------------------------------------------

def _card_to_discard(game: Game, player: int) -> Card:
    hand = game.hands[player]
    plain = [card for card in hand if not is_wild(card)]
    return min(plain or hand, key=lambda card: _keep_score(game, player, hand, card))


def _keep_score(game: Game, player: int, hand: list[Card], card: Card) -> tuple:
    """How much we want to keep a card. Lowest gets thrown."""
    if is_wild(card):
        return (100, 0)
    fits = any(can_extend(meld, card) for meld in game.melds[player])
    same_rank = sum(1 for other in hand if other is not card
                    and other.rank == card.rank)
    neighbours = sum(1 for other in hand
                     if other is not card and other.suit == card.suit
                     and 0 < abs(other.rank - card.rank) <= 2)
    # Among equally useless cards, throw the dearest: it is the one that hurts
    # most if it is still in hand when the hand ends.
    return (10 if fits else same_rank * 2 + neighbours, -CARD_POINTS[card.rank])
