"""The computer's Burraco play: greedy, but it knows what a meld is worth."""

import random
from collections import Counter

from ..cards import RANKS, SUITS, Card
from .engine import (AI, BURRACO_SIZE, MIN_MELD, CARD_POINTS, Game,
                     InvalidMeld, Meld, Stranded, Turn, build_meld, can_extend,
                     is_wild, wild_stands_for)

EASY, NORMAL, HARD = "easy", "normal", "hard"

# HARD is built and playable — `take_turn(game, player, HARD)` searches the
# whole turn — but it is not offered, because it loses. See the note over
# `search_turn` at the foot of this module for the measurements.
LEVELS = (EASY, NORMAL)
LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal", HARD: "Expert (experimental)"}

# There is no expert level here, and the omission is deliberate. Several were
# tried and measured against Normal over eighty hands apiece, each one played
# from both seats: keeping the pinelle back for burracos, holding cards the
# opponent could use, growing the longest meld first, and taking the discard
# pile more boldly. The first three lost outright; the last gained points
# (51%) while losing matches 34-46, because a player who hoards material stops
# closing. Briscola's expert works by searching sampled worlds, which does not
# carry over: Burraco has far more moves per turn and far longer hands.

# Taking the whole discard pile is worth it when enough of it is usable.
PILE_MIN_GAIN = 15
PILE_COST = 0.25

# Whether to weigh what the pile would be worth to the opponent as well as to
# yourself. Off, and measured: over sixty deals with one seat denying and the
# other not, then with the seats swapped, the denier took 48% and 50% of the
# points and lost the matches 22-38 and 28-32. The reason is the same one that
# sank every other attempt at cleverness here — cards taken for any reason
# other than what they do for your own hand are a liability. They count
# against you if they stay, and they put off the moment you can close.
#
# The switch stays so the two can be played against each other again when
# there is something better to try.
DENY = False

# Past this many cards a hand is a burden: taking the pile only makes it worse.
HAND_TOO_BIG = 16


def take_turn(game: Game, player: int, level: str = NORMAL,
              rng: random.Random | None = None) -> list[str]:
    """Play one full turn and report what was done, for the move log."""
    rng = rng or random.Random()
    moves = []

    if level == HARD:
        return _play_searched_turn(game, player)

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
        card = _card_to_discard(game, player, level)
        game.discard(player, card)
        moves.append(f"discards {card}")
    else:
        game.end_turn(player)
        moves.append("ends with an empty hand")
    return moves


def _play_searched_turn(game: Game, player: int) -> list[str]:
    """Play the turn the search picked, falling back if it finds nothing."""
    plan = search_turn(game, player)
    if not plan:
        return [_draw_phase(game, player, NORMAL)]

    said = []
    for kind, payload in plan:
        try:
            _apply(game, player, (kind, payload))
        except (RuntimeError, InvalidMeld, Stranded):
            continue
        if kind == "draw":
            said.append("draws a card")
        elif kind == "pile":
            said.append("takes the pile")
        elif kind == "meld":
            said.append(f"lays down {len(payload)} cards")
        else:
            said.append(f"discards {payload}")
        if kind in ("draw", "pile"):
            _substitutions(game, player)
            _extend_everything(game, player)
    if game.hands[player] and game.turn == player and not game.game_over:
        try:
            game.discard(player, _card_to_discard(game, player))
            said.append("discards")
        except (RuntimeError, Stranded):
            pass
    if not game.hands[player] and game.turn == player and not game.game_over:
        game.end_turn(player)
    return said


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
    """Take the pile when the melds it unlocks are worth its weight.

    Both simpler rules were wrong in opposite directions. Judging by "these
    cards fit somewhere in my hand" ran away: the bigger the hand, the more of
    the pile looked useful, so it was always taken and the stock never
    drained. Judging by "I can lay this down right now" was so cautious that
    the player never gathered the material to build anything — it melded 414
    points a hand against a near-random opponent's 618, and lost.

    What matters is neither: it is how much more the hand can put on the table
    once the pile is in it.
    """
    pile = game.discards
    hand = game.hands[player]
    if game.may_close(player) and len(hand) <= 2:
        return False                    # so close: do not bury it in cards
    if len(hand) > HAND_TOO_BIG + len(pile):
        return False                    # cards you cannot shed are a liability
    if level == EASY:
        return len(pile) >= 6

    gain = _table_value(hand + pile, game, player) - _table_value(hand, game, player)
    # Every card taken is one more to get rid of, and a penalty if it sticks.
    cost = sum(CARD_POINTS[card.rank] for card in pile) * PILE_COST
    denial = opponent_interest(game, player, pile) * DENIAL_WEIGHT if DENY else 0
    return gain + denial > cost + PILE_MIN_GAIN


DENIAL_WEIGHT = 0.6


def opponent_interest(game: Game, player: int, cards: list[Card]) -> int:
    """What these cards would be worth to the other player.

    Built from what is public: the melds on their side of the table, and the
    ranks their own discards and takes say they are collecting. Taking a pile
    they want is worth something beyond what it does for your own hand.
    """
    other = 1 - player
    worth = 0
    for card in cards:
        if is_wild(card):
            worth += CARD_POINTS[card.rank]
            continue
        if any(can_extend(meld, card) for meld in game.melds[other]):
            worth += CARD_POINTS[card.rank] + 10
        elif reading_of_opponent(game, player, card) > 0:
            worth += 5
    return worth


def _table_value(cards: list[Card], game: Game, player: int) -> int:
    """What these cards could put on the table, melds and burracos included."""
    total = 0
    for meld_cards in _find_melds(list(cards)):
        try:
            meld = build_meld(meld_cards)
        except InvalidMeld:
            continue
        total += meld.points()
    for meld in game.melds[player]:
        total += sum(CARD_POINTS[card.rank] for card in cards
                     if can_extend(meld, card))
    return total


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

    for cards in _find_melds(list(game.hands[player]),
                             greedy_wilds=level != EASY,
                             thrifty_wilds=False):
        try:
            meld = game.lay_meld(player, cards)
        except (InvalidMeld, RuntimeError, Stranded):
            continue
        moves.append(f"lays down a {meld.kind} of {len(meld)}")
    return moves


def _find_melds(hand: list[Card], greedy_wilds: bool = True,
                thrifty_wilds: bool = False) -> list[list[Card]]:
    """Pick melds out of a hand, best first.

    Candidates are scored by what they are worth on the table rather than by
    how long they are: a run of three aces beats a run of four low cards, and
    anything that reaches seven is worth a hundred more again.
    """
    candidates = sorted(_candidate_melds(hand), key=_meld_worth, reverse=True)

    left = Counter(hand)
    found = []
    for cards in candidates:
        need = Counter(cards)
        if need <= left:
            found.append(cards)
            left -= need

    if greedy_wilds:
        rest = list(left.elements())
        wilds = [card for card in rest if is_wild(card)]
        if wilds:
            cards = _pair_plus_wild(rest, wilds[0], thrifty_wilds)
            if cards:
                found.append(cards)
    return found


def _meld_worth(cards: list[Card]) -> int:
    worth = sum(CARD_POINTS[card.rank] for card in cards)
    if len(cards) >= BURRACO_SIZE:
        worth += 200 if not any(is_wild(card) for card in cards) else 100
    return worth


def _candidate_melds(hand: list[Card]) -> list[list[Card]]:
    """Every set and every run the hand holds outright, without wild cards."""
    out = []
    by_rank: dict[int, list[Card]] = {}
    for card in hand:
        if not is_wild(card):
            by_rank.setdefault(card.rank, []).append(card)
    out.extend(same for same in by_rank.values() if len(same) >= MIN_MELD)

    for suit in SUITS:
        ranks = sorted({card.rank for card in hand
                        if card.suit == suit and not is_wild(card)})
        stretch: list[int] = []
        for rank in ranks + [None]:
            if stretch and rank == stretch[-1] + 1:
                stretch.append(rank)
                continue
            if len(stretch) >= MIN_MELD:
                out.append([next(card for card in hand
                                 if card.suit == suit and card.rank == r)
                            for r in stretch])
            stretch = [rank] if rank is not None else []
    return out


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


def _pair_plus_wild(cards: list[Card], wild: Card,
                    thrifty: bool = False) -> list[Card] | None:
    """Spend a wild card only to turn a pair into a meld worth having.

    A pinella is worth twenty on its own and completes a burraco later, so the
    expert will not sink one into three low cards.
    """
    for rank in sorted(RANKS, key=lambda r: -CARD_POINTS[r]):
        if thrifty and CARD_POINTS[rank] < 10:
            continue
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

def _card_to_discard(game: Game, player: int, level: str = NORMAL) -> Card:
    hand = game.hands[player]
    plain = [card for card in hand if not is_wild(card)]
    return min(plain or hand,
               key=lambda card: _keep_score(game, player, hand, card, level))


def reading_of_opponent(game: Game, player: int, card: Card) -> int:
    """What the opponent's own discards and takes say about this card.

    Everything here is public: the pile is face up and taken whole, so both
    sides can see what the other threw away and what they gathered up. A rank
    the opponent has thrown is one they do not want; a rank they took is one
    they were collecting.
    """
    other = 1 - player
    if any(thrown.rank == card.rank for thrown in game.thrown[other]):
        return -1
    for got in game.taken[other]:
        if got.rank == card.rank:
            return 1
        if got.suit == card.suit and 0 < abs(got.rank - card.rank) <= 2:
            return 1
    return 0


def _keep_score(game: Game, player: int, hand: list[Card], card: Card,
                level: str = NORMAL) -> tuple:
    """How much we want to keep a card. Lowest gets thrown."""
    if is_wild(card):
        return (100, 0)
    fits = any(can_extend(meld, card) for meld in game.melds[player])
    same_rank = sum(1 for other in hand if other is not card
                    and other.rank == card.rank)
    neighbours = sum(1 for other in hand
                     if other is not card and other.suit == card.suit
                     and 0 < abs(other.rank - card.rank) <= 2)
    want = 10 if fits else same_rank * 2 + neighbours

    # Among equally useless cards, throw the dearest: it is the one that hurts
    # most if it is still in hand when the hand ends.
    #
    # `reading_of_opponent` was tried here as a tie-break ahead of this one,
    # so that between two cards we were throwing anyway the safer went first.
    # Measured over sixty deals with one seat reading and the other blind, and
    # then with the seats swapped, the reader took 48% and 49% of the points
    # and lost on matches both ways. Withholding a card the opponent could use
    # had already measured worse for the plainer reason: its points stay in
    # your hand and count against you. The reading stays available, and the
    # engine keeps the record it needs, but nothing here acts on it.
    return (want, -CARD_POINTS[card.rank])


# --- searching the turn ---------------------------------------------------
#
# Every attempt above bolts another rule onto a turn played greedily, and six
# of seven measured worse. This tries the other thing: one objective, and a
# choice between the turns actually available — draw or take the pile, lay
# down or hold, and which card to let go — with material and closing weighed
# inside the objective rather than patched on afterwards.
#
# It loses too: 46% of the points against Normal over forty hands played from
# both seats, and 15-25 on matches. Crediting half-built melds in the
# objective, which was the obvious flaw — only finished melds scored, so the
# search would throw one of a pair without noticing — changed the points not
# at all and the matches for the worse, 12-28.
#
# It is kept, unoffered, because it is the only frame here that could carry a
# better evaluation: the machinery for trying turns and scoring positions is
# the part that would be rebuilt otherwise. What it needs is an evaluation
# worth searching with. Two candidates, neither tried: score a position by
# playing it out to the end of the hand with the cheap policy, the way
# Briscola's expert scores a world; or learn the weights from self-play rather
# than guessing them, since every weight here was guessed and this whole
# session says that guessing loses.

HAND_LIABILITY = 1.0        # points in hand count against you at the end
HAND_POTENTIAL = 0.45       # what the hand could still become, discounted
PARTNER_VALUE = 0.30        # a pair, or two in a row: a meld half made
CLOSING_PULL = 70           # being able to finish is worth more than it scores


def _clone(game: Game) -> Game:
    """A copy cheap enough to try a hundred turns on."""
    copy = Game.__new__(Game)
    copy.hands = [list(game.hands[0]), list(game.hands[1])]
    copy.melds = [[Meld(list(m.cards), m.kind, m.wilds) for m in side]
                  for side in game.melds]
    copy.pots = [list(game.pots[0]), list(game.pots[1])]
    copy.pot_taken = list(game.pot_taken)
    copy.stock = list(game.stock)
    copy.discards = list(game.discards)
    copy.thrown = [list(game.thrown[0]), list(game.thrown[1])]
    copy.taken = [list(game.taken[0]), list(game.taken[1])]
    copy.turn = game.turn
    copy.phase = Turn(drawn=game.phase.drawn, took_pile=game.phase.took_pile)
    copy.closed_by = game.closed_by
    copy.exhausted = game.exhausted
    copy.first_player = game.first_player
    copy.seed = game.seed
    return copy


def position_value(game: Game, player: int) -> float:
    """What a position is worth to a player, beyond what it scores today.

    `score` already counts the melds, the burracos, the cards left in hand and
    the pot. Two things it cannot see matter as much: what the hand could
    still put down, and how close the player is to ending the hand on their
    own terms.
    """
    value = float(game.score(player))
    hand = list(game.hands[player])
    melded_here = set()
    for cards in _find_melds(hand):
        value += HAND_POTENTIAL * _meld_worth(cards)
        melded_here.update(id(card) for card in cards)

    # Credit what is half built as well. Without this the search throws away
    # one of a pair without noticing, since only finished melds score, and it
    # loses to the plain rule it was meant to beat.
    rest = [card for card in hand if id(card) not in melded_here]
    for index, card in enumerate(rest):
        if is_wild(card):
            continue
        for other in rest[index + 1:]:
            if is_wild(other):
                continue
            pair = other.rank == card.rank
            run = other.suit == card.suit and abs(other.rank - card.rank) == 1
            if pair or run:
                value += PARTNER_VALUE * CARD_POINTS[card.rank]
                break
    if game.may_close(player):
        value += max(0, CLOSING_PULL - 8 * len(game.hands[player]))
    return value


def _turn_plans(game: Game, player: int):
    """Every turn worth trying, as a list of moves to play out."""
    draws = []
    if game.stock:
        draws.append(("draw", None))
    if game.discards:
        draws.append(("pile", None))

    for draw in draws:
        after_draw = _clone(game)
        try:
            _apply(after_draw, player, draw)
        except (RuntimeError, InvalidMeld, Stranded):
            continue

        melds = _find_melds(list(after_draw.hands[player]))
        clean = [cards for cards in melds
                 if not any(is_wild(card) for card in cards)]
        for lay in ({"all": melds, "clean": clean, "none": []}).values():
            yield [draw] + [("meld", cards) for cards in lay]


def _apply(game: Game, player: int, move) -> None:
    kind, payload = move
    if kind == "draw":
        game.draw(player)
    elif kind == "pile":
        game.take_discards(player)
    elif kind == "meld":
        game.lay_meld(player, payload)
    elif kind == "discard":
        game.discard(player, payload)


def search_turn(game: Game, player: int) -> list:
    """Pick the turn that leaves the best position, discard included."""
    best_moves, best_value = None, None

    for plan in _turn_plans(game, player):
        trial = _clone(game)
        try:
            for move in plan:
                _apply(trial, player, move)
        except (RuntimeError, InvalidMeld, Stranded):
            continue

        _extend_everything(trial, player)
        for card in _discard_options(trial, player):
            after = _clone(trial)
            try:
                after.discard(player, card)
            except (RuntimeError, Stranded):
                continue
            value = position_value(after, player)
            if best_value is None or value > best_value:
                best_value = value
                best_moves = plan + [("discard", card)]
    return best_moves or []


def _extend_everything(game: Game, player: int) -> None:
    """Growing a meld banks points and never costs a card you wanted."""
    for meld in list(game.melds[player]):
        for card in list(game.hands[player]):
            if can_extend(meld, card):
                try:
                    game.extend_meld(player, meld, [card])
                except (InvalidMeld, Stranded, RuntimeError):
                    continue


def _discard_options(game: Game, player: int) -> list[Card]:
    seen, out = set(), []
    for card in game.hands[player]:
        if card in seen:
            continue
        seen.add(card)
        out.append(card)
    return out
