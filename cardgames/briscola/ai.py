"""Computer opponent, with three difficulty levels.

* `easy`   - mostly random, but it grabs an obviously valuable trick.
* `normal` - the classic heuristics: lead your cheapest card, duck small
             tricks, spend a trump only when the trick pays for it.
* `hard`   - a genuinely strong player:
             - it counts cards, so once the stock is empty it knows the
               opponent's hand exactly and solves the ending by exhaustive
               minimax search (it then plays the best possible line);
             - before that it samples the hands the opponent could hold and
               plays out each candidate card in every sampled world, keeping
               the card that wins the most of them. This is perfect
               information Monte Carlo, the standard strong approach for
               trick-taking games.
"""

import random
import time

from ..cards import Card, new_deck
from .engine import AI, HUMAN, WINNING_POINTS, Game, beats_lead

EASY, NORMAL, HARD = "easy", "normal", "hard"
LEVELS = (EASY, NORMAL, HARD)

LEVEL_LABELS = {EASY: "Easy", NORMAL: "Normal", HARD: "Expert"}

# Sampled worlds per decision: more of them once the unknowns shrink.
WORLDS_EARLY = 100
WORLDS_LATE = 200
LATE_STOCK = 8

# The search runs in the interface thread, so it is capped by wall clock as
# well: whichever limit comes first. A few worlds are always played, so a
# slow machine still gets a sensible move instead of a random one.
TIME_BUDGET = 0.12
MIN_WORLDS = 8

# With this many cards left to draw the opponent's hand is fully known,
# so the ending can be solved exactly instead of sampled.
EXACT_FROM = 1

# Cards in both hands under which a position is small enough to solve exactly.
SOLVE_CARDS = 6

_rng = random.Random()


def choose_card(game: Game, level: str = NORMAL,
                rng: random.Random | None = None) -> int:
    """Index of the card the opponent plays."""
    hand = game.hands[AI]
    if len(hand) == 1:
        return 0
    if level == EASY:
        return _easy(game, hand, rng or _rng)
    if level == HARD:
        return _expert(game, rng or _rng)
    return _heuristic(game)


# --- easy -----------------------------------------------------------------

def _easy(game: Game, hand: list[Card], rng: random.Random) -> int:
    lead = game.lead_card
    if lead is not None and lead.points >= 10:
        winning = [i for i, c in enumerate(hand)
                   if beats_lead(lead, c, game.trump_suit)]
        if winning:
            return min(winning, key=lambda i: hand[i].points)
    plain = [i for i, c in enumerate(hand) if c.suit != game.trump_suit]
    return rng.choice(plain or list(range(len(hand))))


# --- normal: heuristics ---------------------------------------------------

def _heuristic(game: Game) -> int:
    hand = game.hands[game.turn]
    if len(hand) == 1:
        return 0
    if game.lead_card is None:
        return _lead(game, hand)
    return _follow(game, hand, game.lead_card)


def _lead(game: Game, hand: list[Card]) -> int:
    trump = game.trump_suit
    plain = [i for i, c in enumerate(hand) if c.suit != trump]
    if plain:
        # Lead the cheapest throwaway: few points, low strength.
        return min(plain, key=lambda i: (hand[i].points, hand[i].strength))
    # Trumps only: start with the weakest one.
    return min(range(len(hand)), key=lambda i: (hand[i].points, hand[i].strength))


def _follow(game: Game, hand: list[Card], lead: Card) -> int:
    trump = game.trump_suit
    pot = lead.points
    player = game.turn

    winning = [i for i, c in enumerate(hand) if beats_lead(lead, c, trump)]
    losing = [i for i in range(len(hand)) if i not in winning]

    # Winning without spending a trump is worth it whenever it is free.
    free_wins = [i for i in winning if hand[i].suit != trump]
    if free_wins:
        best = min(free_wins, key=lambda i: (hand[i].points, hand[i].strength))
        if pot > 0 or hand[best].points == 0:
            return best

    endgame = game.cards_left == 0
    needed = WINNING_POINTS - game.points[player]
    closing = endgame and needed <= pot + 4

    if winning:
        cost = min(winning, key=lambda i: (hand[i].points, hand[i].strength))
        worth_it = pot >= 10 or (pot >= 4 and hand[cost].points <= 2) or closing
        if worth_it or not losing:
            return cost

    if not losing:
        return min(winning, key=lambda i: (hand[i].points, hand[i].strength))

    # Duck: throw the least valuable card, keeping trumps back.
    return min(losing, key=lambda i: (hand[i].suit == trump,
                                      hand[i].points,
                                      hand[i].strength))


# --- card counting --------------------------------------------------------

def unseen_cards(game: Game) -> list[Card]:
    """Cards the opponent could still hold: not the AI's, and never played."""
    seen = set(game.hands[AI])
    seen.update(game.captured[HUMAN])
    seen.update(game.captured[AI])
    seen.update(card for _player, card in game.table)
    if game.trump_card is not None:
        seen.add(game.trump_card)
    return [card for card in new_deck() if card not in seen]


def known_opponent_hand(game: Game) -> list[Card] | None:
    """The opponent's exact hand once nothing unknown is left to draw."""
    if game.cards_left > EXACT_FROM:
        return None
    return unseen_cards(game)


# --- hard: search and sampling -------------------------------------------

def _expert(game: Game, rng: random.Random) -> int:
    known = known_opponent_hand(game)
    if known is not None:
        _value, index = _solve(_clone(game, opponent_hand=known))
        if index is not None:
            return index
        return _heuristic(game)
    return _monte_carlo(game, rng)


def _clone(game: Game, opponent_hand: list[Card] | None = None,
           stock: list[Card] | None = None) -> Game:
    """A cheap copy, optionally with a guessed opponent hand and stock."""
    copy = Game.__new__(Game)
    copy.hands = [list(game.hands[HUMAN]) if opponent_hand is None
                  else list(opponent_hand),
                  list(game.hands[AI])]
    copy.stock = list(game.stock) if stock is None else list(stock)
    copy.trump_card = game.trump_card
    copy.trump_suit = game.trump_suit
    copy.points = list(game.points)
    copy.captured = [list(game.captured[HUMAN]), list(game.captured[AI])]
    copy.table = list(game.table)
    copy.leader = game.leader
    copy.first_leader = game.first_leader
    copy.turn = game.turn
    copy.tricks_played = game.tricks_played
    copy.history = []
    return copy


def _solve(game: Game) -> tuple[int, int | None]:
    """Exhaustive minimax on a fully known position.

    Returns the AI's final points under best play by both sides, and the
    index the AI should play now (None when it is not the AI's move).
    """
    if game.game_over:
        return game.points[AI], None
    if game.trick_complete:
        nxt = _clone(game)
        nxt.resolve_trick()
        value, _ = _solve(nxt)
        return value, None

    player = game.turn
    best_value: int | None = None
    best_index: int | None = None
    for index in range(len(game.hands[player])):
        nxt = _clone(game)
        nxt.play_card(player, index)
        value, _ = _solve(nxt)
        better = (best_value is None
                  or (value > best_value if player == AI else value < best_value))
        if better:
            best_value, best_index = value, index
    return best_value or 0, best_index if player == AI else None


def _monte_carlo(game: Game, rng: random.Random) -> int:
    """Try every candidate card in the same set of sampled worlds.

    Worlds are played one at a time across all the candidate cards, and the
    loop stops when the time budget runs out. Sampling in that order keeps
    the comparison fair when the search is cut short, and keeps the window
    responsive on a slow machine instead of freezing for however long a
    fixed number of worlds happens to take.
    """
    hand_size = len(game.hands[AI])
    worlds = _sample_worlds(game, _world_count(game), rng)
    wins = [0.0] * hand_size
    points = [0.0] * hand_size
    deadline = time.perf_counter() + TIME_BUDGET

    for played, (opponent_hand, stock) in enumerate(worlds, start=1):
        for index in range(hand_size):
            final = _rollout(_clone(game, opponent_hand, stock), index)
            points[index] += final
            if final >= WINNING_POINTS:
                wins[index] += 1.0
            elif final == WINNING_POINTS - 1:   # 60-60 is a draw
                wins[index] += 0.5
        if played >= MIN_WORLDS and time.perf_counter() > deadline:
            break

    return max(range(hand_size), key=lambda i: (wins[i], points[i]))


def _sample_worlds(game: Game, count: int,
                   rng: random.Random) -> list[tuple[list[Card], list[Card]]]:
    """Deal the unseen cards into a possible opponent hand and stock."""
    unseen = unseen_cards(game)
    hand_size = len(game.hands[HUMAN])
    worlds = []
    for _ in range(count):
        pool = unseen[:]
        rng.shuffle(pool)
        worlds.append((pool[:hand_size], pool[hand_size:]))
    return worlds


def _world_count(game: Game) -> int:
    return WORLDS_LATE if len(game.stock) <= LATE_STOCK else WORLDS_EARLY


def _rollout(game: Game, index: int) -> int:
    """Play the given card, then finish this world off as well as we can.

    Inside a sampled world both hands are known, so the playout uses the
    tactical policy below rather than the blind heuristics, and the last
    tricks are solved exactly.
    """
    game.play_card(AI, index)
    while not game.game_over:
        if game.trick_complete:
            game.resolve_trick()
            continue
        if (game.cards_left == 0
                and len(game.hands[AI]) + len(game.hands[HUMAN]) <= SOLVE_CARDS):
            value, _ = _solve(game)
            return value
        game.play_card(game.turn, _tactical(game))
    return game.points[AI]


# --- tactical playout policy (both hands visible) --------------------------

def _card_cost(card: Card, trump_suit: str) -> float:
    """How much it hurts to give this card up (tuned by self-play)."""
    return 0.5 * card.points + (2.5 if card.suit == trump_suit else 0.0)


def _follow_value(lead: Card, card: Card, trump_suit: str) -> float:
    """Value of answering `lead` with `card`: the trick is decided at once."""
    pot = lead.points + card.points
    wins = beats_lead(lead, card, trump_suit)
    return (pot if wins else -pot) - _card_cost(card, trump_suit)


def _tactical(game: Game) -> int:
    """One trick of lookahead on a position where both hands are known."""
    player = game.turn
    hand = game.hands[player]
    if len(hand) == 1:
        return 0
    trump = game.trump_suit
    lead = game.lead_card

    if lead is not None:
        return max(range(len(hand)),
                   key=lambda i: _follow_value(lead, hand[i], trump))

    opponent = game.hands[1 - player]
    best_index, best_value = 0, None
    for index, card in enumerate(hand):
        if opponent:
            reply = max(opponent, key=lambda r: _follow_value(card, r, trump))
            lost = beats_lead(card, reply, trump)
            pot = card.points + reply.points
        else:
            lost, pot = False, card.points
        value = (-pot if lost else pot) - _card_cost(card, trump)
        if best_value is None or value > best_value:
            best_value, best_index = value, index
    return best_index
