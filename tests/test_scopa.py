"""Scopa rules: what a card takes, what a scopa is, and how a hand scores."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.cards import ACE, JACK, KING, QUEEN, Card, new_deck
from cardgames.scopa import ai
from cardgames.scopa.engine import (AI, COINS, HAND_SIZE, HUMAN, PRIME,
                                    SETTEBELLO, TABLE_SIZE, VALUES, Ambiguous,
                                    Game, IllegalCapture, Match, prime_score)


def play_first(game):
    """Play the first card in hand, taking the first legal way of taking."""
    options = game.capture_options(game.hands[game.turn][0])
    return game.play(game.turn, 0, options[0] if options else None)


def rigged(table, hand, other=(), stock=(), turn=HUMAN):
    """A position built by hand: the deal is not what most rules need."""
    game = Game(seed=0)
    game.table = list(table)
    game.hands = [list(hand), list(other)]
    game.stock = list(stock)
    game.captured = [[], []]
    game.scope = [0, 0]
    game.turn = turn
    game.last_capture = None
    game.swept = False
    return game


# --- the deal -------------------------------------------------------------

def test_the_deal_is_four_on_the_table_and_three_each():
    game = Game(seed=5)
    assert len(game.table) == TABLE_SIZE
    assert len(game.hands[HUMAN]) == HAND_SIZE
    assert len(game.hands[AI]) == HAND_SIZE
    assert game.cards_left == 40 - TABLE_SIZE - 2 * HAND_SIZE
    everything = game.table + game.hands[HUMAN] + game.hands[AI] + game.stock
    assert sorted(map(str, everything)) == sorted(map(str, new_deck()))


def test_three_more_come_out_only_when_both_hands_are_empty():
    game = Game(seed=5, first_player=HUMAN)
    for _ in range(5):
        play_first(game)
    # Five cards played: one player still holds one, so nothing is dealt.
    assert game.cards_left == 30
    assert sorted(len(hand) for hand in game.hands) == [0, 1]
    play_first(game)
    assert game.cards_left == 24
    assert [len(hand) for hand in game.hands] == [3, 3]


def test_the_values_are_the_italian_ones():
    assert VALUES[ACE] == 1 and VALUES[7] == 7
    assert (VALUES[JACK], VALUES[QUEEN], VALUES[KING]) == (8, 9, 10)


# --- taking ---------------------------------------------------------------

def test_a_matching_card_is_taken():
    game = rigged(table=[Card(4, "Spades"), Card(KING, "Hearts")],
                  hand=[Card(4, "Clubs")], other=[Card(2, "Clubs")])
    play = game.play(HUMAN, 0)
    assert play.taken == (Card(4, "Spades"),)
    assert game.table == [Card(KING, "Hearts")]
    assert sorted(map(str, game.captured[HUMAN])) == \
        sorted(map(str, [Card(4, "Spades"), Card(4, "Clubs")]))


def test_a_card_that_takes_nothing_stays_on_the_table():
    game = rigged(table=[Card(KING, "Hearts")], hand=[Card(3, "Clubs")])
    play = game.play(HUMAN, 0)
    assert play.taken == ()
    assert Card(3, "Clubs") in game.table
    assert not game.captured[HUMAN]


def test_a_sum_is_taken_only_when_no_single_card_matches():
    table = [Card(3, "Spades"), Card(4, "Hearts"), Card(7, "Clubs")]
    game = rigged(table=table, hand=[Card(7, "Diamonds")])
    options = game.capture_options(Card(7, "Diamonds"))
    assert options == [(Card(7, "Clubs"),)], \
        "the seven on the table has to be taken, not the three and the four"

    # Take the seven away and the sum becomes the only way to take.
    game = rigged(table=table[:2], hand=[Card(7, "Diamonds")])
    options = game.capture_options(Card(7, "Diamonds"))
    assert options == [(Card(3, "Spades"), Card(4, "Hearts"))]


def test_a_choice_has_to_be_made_rather_than_guessed():
    game = rigged(table=[Card(5, "Spades"), Card(5, "Hearts")],
                  hand=[Card(5, "Clubs")], other=[Card(2, "Clubs")])
    try:
        game.play(HUMAN, 0)
    except Ambiguous:
        pass
    else:
        raise AssertionError("two fives on the table is a choice, not a move")
    play = game.play(HUMAN, 0, [Card(5, "Hearts")])
    assert play.taken == (Card(5, "Hearts"),)
    assert game.table == [Card(5, "Spades")]


def test_an_illegal_take_is_refused():
    game = rigged(table=[Card(4, "Spades"), Card(KING, "Hearts")],
                  hand=[Card(4, "Clubs")])
    for taking in ([Card(KING, "Hearts")], []):
        try:
            game.play(HUMAN, 0, taking)
        except IllegalCapture:
            continue
        raise AssertionError(f"{taking} should not be a legal take")


def test_the_face_cards_take_by_their_own_numbers():
    game = rigged(table=[Card(2, "Spades"), Card(6, "Hearts")],
                  hand=[Card(JACK, "Clubs")])
    play = game.play(HUMAN, 0)
    assert set(play.taken) == {Card(2, "Spades"), Card(6, "Hearts")}, \
        "a jack is worth eight, so it takes the two and the six"


# --- the scopa ------------------------------------------------------------

def test_clearing_the_table_is_a_scopa():
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")],
                  other=[Card(5, "Clubs")], stock=list(new_deck()[:6]))
    play = game.play(HUMAN, 0)
    assert play.scopa
    assert game.scope[HUMAN] == 1


def test_the_last_card_of_the_hand_never_scores_a_scopa():
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")])
    play = game.play(HUMAN, 0)
    assert play.taken and not play.scopa, \
        "nobody could have played on that table, so it is not a sweep"
    assert game.scope[HUMAN] == 0


def test_what_is_left_goes_to_whoever_captured_last():
    game = rigged(table=[Card(4, "Spades"), Card(KING, "Hearts")],
                  hand=[Card(4, "Clubs")])
    play = game.play(HUMAN, 0)
    assert game.game_over
    assert play.swept == (Card(KING, "Hearts"),)
    assert Card(KING, "Hearts") in game.captured[HUMAN]
    assert not game.table


# --- scoring --------------------------------------------------------------

def test_primiera_counts_the_best_card_of_each_suit():
    cards = [Card(7, "Diamonds"), Card(ACE, "Diamonds"), Card(6, "Hearts")]
    assert prime_score(cards) == PRIME[7] + PRIME[6]
    assert prime_score([]) == 0


def test_the_four_points_and_the_scope():
    game = Game(seed=1)
    game.captured = [[], []]
    # You take most cards, most coins and the settebello; they take nothing.
    game.captured[HUMAN] = [Card(rank, COINS) for rank in (7, 6, 5)]
    game.captured[AI] = [Card(KING, "Spades")]
    game.scope = [2, 0]
    mine, theirs = game.tallies()
    assert (mine.cards, mine.coins, mine.settebello) == (1, 1, 1)
    assert mine.prime == 1 and mine.scope == 2
    assert mine.total == 6
    assert theirs.total == 0


def test_a_level_count_scores_for_nobody():
    game = Game(seed=1)
    game.captured = [[Card(3, "Spades"), Card(4, "Spades")],
                     [Card(3, "Hearts"), Card(4, "Hearts")]]
    game.scope = [0, 0]
    mine, theirs = game.tallies()
    assert mine.cards == theirs.cards == 0, "twenty cards each is nobody's point"
    assert mine.coins == theirs.coins == 0
    assert mine.prime == theirs.prime == 0


def test_the_settebello_is_always_someone_s_point():
    for seed in range(20):
        game = play_out(seed)
        mine, theirs = game.tallies()
        assert mine.settebello + theirs.settebello == 1
        assert SETTEBELLO in game.captured[HUMAN] + game.captured[AI]


# --- whole hands ----------------------------------------------------------

def play_out(seed: int, level: str = ai.EASY, other: str | None = None) -> Game:
    """A full hand played by the opponent code on both sides."""
    game = Game(seed=seed, first_player=seed % 2)
    rng = random.Random(seed * 31 + 7)
    levels = {HUMAN: level, AI: other or level}
    while not game.game_over:
        ai.take_turn(game, game.turn, levels[game.turn], rng)
    return game


def test_no_card_is_lost_or_duplicated():
    for seed in range(60):
        game = play_out(seed)
        held = game.captured[HUMAN] + game.captured[AI] + game.table
        assert sorted(map(str, held)) == sorted(map(str, new_deck())), seed
        assert not game.table, f"seed {seed}: the table was never swept"


def test_a_hand_is_worth_four_points_plus_the_scope():
    for seed in range(40):
        game = play_out(seed)
        mine, theirs = game.tallies()
        fixed = sum(t.cards + t.coins + t.settebello + t.prime
                    for t in (mine, theirs))
        assert fixed <= 4, seed
        assert mine.total + theirs.total == fixed + sum(game.scope), seed


def test_every_level_plays_a_legal_hand():
    for level in ai.LEVELS:
        game = play_out(3, level)
        assert game.game_over
        assert sum(len(game.captured[p]) for p in (HUMAN, AI)) == 40


def test_the_normal_level_beats_the_random_one():
    """Judged on points over many deals, each played from both seats.

    Scopa is worth four points plus the scope, so a single hand says almost
    nothing: two even players trade the same handful of points. Playing every
    deal from both sides removes the deal itself from the comparison.
    """
    points = [0, 0]
    for seed in range(40):
        for swap in (False, True):
            first, second = ((ai.EASY, ai.NORMAL) if swap
                             else (ai.NORMAL, ai.EASY))
            game = play_out(seed, first, second)
            you, them = game.scores()
            points[0] += them if swap else you
            points[1] += you if swap else them
    share = points[0] / sum(points)
    assert share > 0.58, f"normal took only {share:.1%} of the points"


def test_the_expert_reads_the_position_it_is_given():
    """It should not need a search to see a scopa in front of it."""
    game = rigged(table=[Card(4, "Spades")],
                  hand=[Card(4, "Clubs"), Card(KING, "Hearts")],
                  other=[Card(5, "Clubs")], stock=list(new_deck()[:6]))
    index, taking = ai.choose_move(game, HUMAN, ai.HARD, random.Random(0))
    assert game.hands[HUMAN][index] == Card(4, "Clubs")
    assert taking == (Card(4, "Spades"),)


# --- what the opponent knows ----------------------------------------------

def test_the_opponent_only_counts_what_it_cannot_see():
    game = Game(seed=9, first_player=HUMAN)
    unseen = ai.unseen_cards(game, HUMAN)
    assert len(unseen) == 40 - TABLE_SIZE - HAND_SIZE
    for card in game.hands[HUMAN] + game.table:
        assert card not in unseen
    for card in game.hands[AI]:
        assert card in unseen, "the other hand is exactly what it cannot see"


def test_a_table_of_one_card_is_the_dangerous_one():
    assert ai.clearing_values([Card(6, "Spades")]) == {6}
    # Two cards can only go together as a sum, and only if no single card
    # on the table matches that sum first.
    assert ai.clearing_values([Card(3, "Spades"), Card(4, "Hearts")]) == {7}
    assert ai.clearing_values([Card(3, "Spades"), Card(4, "Hearts"),
                               Card(7, "Clubs")]) == set()
    assert ai.clearing_values([Card(KING, "Spades"), Card(2, "Hearts")]) == set()


def test_the_expert_finishes_within_its_budget():
    game = Game(seed=4)
    rng = random.Random(1)
    import time
    started = time.time()
    for _ in range(4):
        ai.take_turn(game, game.turn, ai.HARD, rng)
    spent = time.time() - started
    assert spent < 4 * ai.TIME_BUDGET + 2, f"four moves took {spent:.1f}s"


# --- the match ------------------------------------------------------------

def test_a_match_runs_until_someone_is_clear():
    match = Match(target=11)
    match.add_hand([6, 5])
    assert not match.over
    match.add_hand([5, 6])
    assert match.totals == [11, 11]
    assert not match.over, "level at the target is not a match won"
    match.add_hand([2, 0])
    assert match.over and match.winner() == HUMAN


# --- every card, and every way of taking ----------------------------------

def test_every_card_in_the_deck_has_a_value_and_a_prime():
    deck = new_deck()
    assert len(deck) == 40
    for card in deck:
        assert card.rank in VALUES, card
        assert card.rank in PRIME, card
    assert sorted(VALUES[card.rank] for card in deck) == \
        sorted(list(range(1, 11)) * 4), "each value once per suit"


def test_the_primiera_order_is_not_the_playing_order():
    order = sorted(PRIME, key=lambda rank: PRIME[rank], reverse=True)
    assert order[:3] == [7, 6, ACE], "seven, six, ace - then the rest"
    assert PRIME[JACK] == PRIME[QUEEN] == PRIME[KING] == 10
    assert PRIME[2] == 12 and PRIME[2] > PRIME[KING], \
        "a two outranks a king on the primiera, which is the point of it"


def test_a_single_card_is_offered_for_every_match_on_the_table():
    table = [Card(5, "Spades"), Card(5, "Hearts"), Card(5, "Clubs"),
             Card(2, "Hearts"), Card(3, "Hearts")]
    game = rigged(table=table, hand=[Card(5, "Diamonds")],
                  other=[Card(2, "Clubs")])
    options = game.capture_options(Card(5, "Diamonds"))
    assert len(options) == 3, "one option per five on the table"
    assert all(len(option) == 1 for option in options)
    assert {option[0].suit for option in options} == {"Spades", "Hearts", "Clubs"}
    assert not any(set(option) == {Card(2, "Hearts"), Card(3, "Hearts")}
                   for option in options), "the sum is not on offer"


def test_every_sum_is_offered_when_no_single_card_matches():
    table = [Card(2, "Spades"), Card(3, "Hearts"), Card(4, "Clubs"),
             Card(ACE, "Diamonds")]
    game = rigged(table=table, hand=[Card(5, "Diamonds")],
                  other=[Card(2, "Clubs")])
    options = {frozenset(option)
               for option in game.capture_options(Card(5, "Diamonds"))}
    assert options == {
        frozenset({Card(2, "Spades"), Card(3, "Hearts")}),
        frozenset({Card(4, "Clubs"), Card(ACE, "Diamonds")}),
    }, "two and three, or four and ace - and nothing else adds to five"


def test_a_king_takes_the_whole_table_when_it_adds_up():
    table = [Card(KING, "Spades")]                # a single king first
    game = rigged(table=table + [Card(4, "Hearts")],
                  hand=[Card(KING, "Clubs")], other=[Card(2, "Clubs")])
    assert game.capture_options(Card(KING, "Clubs")) == [(Card(KING, "Spades"),)]

    game = rigged(table=[Card(4, "Hearts"), Card(6, "Clubs")],
                  hand=[Card(KING, "Clubs")], other=[Card(2, "Clubs")])
    play = game.play(HUMAN, 0)
    assert set(play.taken) == {Card(4, "Hearts"), Card(6, "Clubs")}, \
        "ten is a king, and four and six make ten"


def test_naming_a_card_twice_is_refused():
    game = rigged(table=[Card(4, "Spades"), Card(2, "Hearts"),
                         Card(2, "Clubs")],
                  hand=[Card(4, "Clubs")], other=[Card(3, "Clubs")])
    try:
        game.play(HUMAN, 0, [Card(2, "Hearts"), Card(2, "Hearts")])
    except IllegalCapture:
        pass
    else:
        raise AssertionError("the same card cannot be taken twice")
    assert len(game.table) == 3, "and nothing moved"


def test_a_take_may_be_named_in_any_order():
    game = rigged(table=[Card(2, "Hearts"), Card(3, "Clubs")],
                  hand=[Card(5, "Diamonds")], other=[Card(4, "Clubs")])
    play = game.play(HUMAN, 0, [Card(3, "Clubs"), Card(2, "Hearts")])
    assert len(play.taken) == 2 and not game.table


# --- the turn -------------------------------------------------------------

def test_the_turn_alternates_and_is_enforced():
    game = Game(seed=8, first_player=HUMAN)
    assert game.turn == HUMAN
    try:
        play_first_for(game, AI)
    except RuntimeError:
        pass
    else:
        raise AssertionError("playing out of turn should fail")
    play_first(game)
    assert game.turn == AI
    play_first(game)
    assert game.turn == HUMAN


def play_first_for(game, player):
    options = game.capture_options(game.hands[player][0])
    return game.play(player, 0, options[0] if options else None)


def test_a_card_that_is_not_in_hand_is_refused():
    game = Game(seed=8, first_player=HUMAN)
    for index in (-1, 3, 99):
        try:
            game.play(HUMAN, index)
        except RuntimeError:
            continue
        raise AssertionError(f"index {index} should not be playable")


def test_nothing_can_be_played_once_the_hand_is_over():
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")])
    game.play(HUMAN, 0)
    assert game.game_over
    try:
        game.play(AI, 0)
    except RuntimeError:
        return
    raise AssertionError("the hand is over")


def test_the_deal_alternates_who_starts_a_hand():
    for first in (HUMAN, AI):
        game = Game(seed=2, first_player=first)
        assert game.turn == first
        # The starter is also dealt to first, which is what the rules say.
        assert len(game.hands[first]) == HAND_SIZE


# --- the scopa, in detail -------------------------------------------------

def test_a_scopa_still_counts_when_the_deck_still_has_cards():
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")],
                  other=[Card(5, "Clubs")], stock=list(new_deck()[:6]))
    assert game.play(HUMAN, 0).scopa


def test_a_scopa_counts_on_the_last_card_of_a_round():
    """Hands empty but the deck is not: three more come out, so it counts."""
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")],
                  other=[], stock=list(new_deck()[:6]))
    play = game.play(HUMAN, 0)
    assert play.scopa, "there are still cards to deal, so the table matters"
    assert [len(hand) for hand in game.hands] == [3, 3], "and they came out"


def test_taking_without_clearing_is_not_a_scopa():
    game = rigged(table=[Card(4, "Spades"), Card(KING, "Hearts")],
                  hand=[Card(4, "Clubs")], other=[Card(2, "Clubs")],
                  stock=list(new_deck()[:6]))
    assert not game.play(HUMAN, 0).scopa
    assert game.scope == [0, 0]


def test_the_scope_are_counted_per_player():
    game = rigged(table=[Card(4, "Spades")],
                  hand=[Card(4, "Clubs")], other=[Card(6, "Clubs")],
                  stock=list(new_deck()[:6]))
    game.play(HUMAN, 0)
    game.table = [Card(6, "Hearts")]
    game.play(AI, 0)
    assert game.scope == [1, 1]


def test_the_table_is_only_swept_once():
    game = rigged(table=[Card(4, "Spades"), Card(KING, "Hearts")],
                  hand=[Card(4, "Clubs")])
    game.play(HUMAN, 0)
    before = len(game.captured[HUMAN])
    assert game.sweep() == (), "a second sweep takes nothing"
    assert len(game.captured[HUMAN]) == before


def test_a_hand_nobody_captured_leaves_the_table_where_it_is():
    game = rigged(table=[Card(KING, "Hearts")], hand=[Card(3, "Clubs")])
    game.play(HUMAN, 0)
    assert game.game_over
    assert len(game.table) == 2, "nobody captured, so nobody sweeps"
    assert not game.captured[HUMAN] and not game.captured[AI]


# --- the four points, one at a time ---------------------------------------

def cards_of(spec) -> list:
    return [Card(rank, suit) for rank, suit in spec]


def scored(mine, theirs, scope=(0, 0)):
    game = Game(seed=1)
    game.captured = [list(mine), list(theirs)]
    game.scope = list(scope)
    return game.tallies()


def test_the_cards_point_goes_to_the_bigger_pile():
    mine, theirs = scored(cards_of([(3, "Spades"), (4, "Spades")]),
                          cards_of([(3, "Hearts")]))
    assert (mine.cards, theirs.cards) == (1, 0)


def test_the_coins_point_counts_diamonds_only():
    mine = cards_of([(3, COINS), (4, COINS)])
    theirs = cards_of([(3, "Hearts"), (4, "Hearts"), (5, "Hearts")])
    got, other = scored(mine, theirs)
    assert (got.coins, other.coins) == (1, 0)
    assert (got.cards, other.cards) == (0, 1), "and the cards point is separate"


def test_the_settebello_is_the_seven_of_coins_and_nothing_else():
    mine, theirs = scored([SETTEBELLO], cards_of([(7, "Hearts"),
                                                  (7, "Spades"),
                                                  (7, "Clubs")]))
    assert mine.settebello == 1 and theirs.settebello == 0
    assert SETTEBELLO == Card(7, COINS)


def test_the_primiera_is_won_on_sevens_and_sixes():
    mine = cards_of([(7, "Spades"), (7, "Hearts")])          # 21 + 21 = 42
    theirs = cards_of([(6, "Clubs"), (6, COINS), (ACE, "Spades")])
    # 18 + 18 + 16 = 52, and the ace of spades outranks nothing of ours there
    assert prime_score(mine) == 42
    assert prime_score(theirs) == 52
    got, other = scored(mine, theirs)
    assert (got.prime, other.prime) == (0, 1)


def test_the_primiera_takes_the_best_card_of_a_suit_not_all_of_them():
    many = cards_of([(2, "Spades"), (3, "Spades"), (4, "Spades"),
                     (5, "Spades")])
    one = cards_of([(7, "Spades")])
    assert prime_score(many) == PRIME[5], "one suit, one card counted"
    assert prime_score(one) == PRIME[7]
    assert prime_score(one) > prime_score(many)


def test_a_level_primiera_scores_for_nobody():
    mine = cards_of([(7, "Spades"), (6, "Hearts")])
    theirs = cards_of([(7, "Clubs"), (6, COINS)])
    assert prime_score(mine) == prime_score(theirs)
    got, other = scored(mine, theirs)
    assert got.prime == other.prime == 0


def test_the_four_points_are_the_classic_four():
    """Cards, coins, settebello and primiera - and nothing else but scope."""
    mine = cards_of([(rank, COINS) for rank in (7, 6, 5, 4, 3)])
    theirs = cards_of([(rank, "Hearts") for rank in (2, 3)])
    got, other = scored(mine, theirs, scope=(1, 2))
    assert [value for _name, value in got.lines()] == [1, 1, 1, 1, 1]
    assert [name for name, _value in got.lines()] == \
        ["Cards", "Coins", "Settebello", "Primiera", "Scope"]
    assert got.total == 5 and other.total == 2
    contested = sum(t.cards + t.coins + t.settebello + t.prime
                    for t in (got, other))
    assert contested == 4, "four points are on offer in every hand"


def test_the_winner_is_the_higher_total():
    game = Game(seed=1)
    game.captured = [[SETTEBELLO], []]
    game.scope = [0, 0]
    assert game.winner() == HUMAN
    game.scope = [0, 9]
    assert game.winner() == AI
    game.captured = [[], []]
    game.scope = [0, 0]
    assert game.winner() is None, "nothing captured either way is a draw"


# --- whole hands, played by every level -----------------------------------

def test_every_move_the_opponent_makes_is_a_legal_one():
    """The one check that covers the rules and the opponent at the same time."""
    for level in ai.LEVELS:
        for seed in range(6 if level == ai.HARD else 30):
            game = Game(seed=seed, first_player=seed % 2)
            rng = random.Random(seed)
            while not game.game_over:
                player = game.turn
                index, taking = ai.choose_move(game, player, level, rng)
                card = game.hands[player][index]
                options = game.capture_options(card)
                if options:
                    assert any(sorted(map(str, taking)) == sorted(map(str, one))
                               for one in options), f"{level}: {card} {taking}"
                else:
                    assert taking == (), f"{level}: {card} cannot take"
                game.play(player, index, taking or None)


def test_the_hand_always_ends_with_forty_cards_accounted_for():
    for seed in range(40):
        game = Game(seed=seed, first_player=seed % 2)
        rng = random.Random(seed)
        while not game.game_over:
            before = (len(game.hands[HUMAN]) + len(game.hands[AI])
                      + len(game.table) + len(game.stock)
                      + len(game.captured[HUMAN]) + len(game.captured[AI]))
            assert before == 40, f"seed {seed}: {before} cards in play"
            ai.take_turn(game, game.turn, ai.NORMAL, rng)
        held = game.captured[HUMAN] + game.captured[AI] + game.table
        assert sorted(map(str, held)) == sorted(map(str, new_deck())), seed


def test_the_deck_empties_in_six_rounds_of_three():
    game = Game(seed=6, first_player=HUMAN)
    rng = random.Random(0)
    seen = []
    while not game.game_over:
        seen.append(game.cards_left)
        ai.take_turn(game, game.turn, ai.EASY, rng)
    assert seen[0] == 30
    assert sorted(set(seen), reverse=True) == [30, 24, 18, 12, 6, 0]
    assert len(seen) == 36, "thirty-six cards are played, six at a time"


def test_the_scope_never_outnumber_the_cards_that_could_have_made_them():
    for seed in range(40):
        game = Game(seed=seed, first_player=seed % 2)
        rng = random.Random(seed)
        while not game.game_over:
            ai.take_turn(game, game.turn, ai.NORMAL, rng)
        assert sum(game.scope) <= 18, seed


# --- what the expert does -------------------------------------------------

def test_the_expert_takes_the_settebello_when_it_is_offered():
    game = rigged(table=[SETTEBELLO, Card(3, "Spades")],
                  hand=[Card(7, "Clubs"), Card(3, "Hearts")],
                  other=[Card(2, "Clubs"), Card(4, "Clubs")],
                  stock=list(new_deck()[:6]))
    for level in (ai.NORMAL, ai.HARD):
        index, taking = ai.choose_move(game, HUMAN, level, random.Random(0))
        assert game.hands[HUMAN][index] == Card(7, "Clubs"), level
        assert taking == (SETTEBELLO,), level


def test_the_level_leaves_out_the_card_that_costs_it_least():
    """A king is cheap to give away, and a two is not.

    Both leave a table one card can clear, and the same number of cards can
    clear either, so the tie is broken on what is being handed over: ten on
    the primiera against twelve, which is the one place a two outranks a king.
    """
    game = rigged(table=[],
                  hand=[Card(KING, "Spades"), Card(2, "Clubs")],
                  other=[Card(6, "Hearts"), Card(5, "Hearts")],
                  stock=list(new_deck()[:8]))
    for seed in range(6):
        index, taking = ai.choose_move(ai._clone(game), HUMAN, ai.NORMAL,
                                       random.Random(seed))
        assert taking == (), "neither card takes anything"
        assert game.hands[HUMAN][index] == Card(KING, "Spades"), seed


def test_the_unseen_cards_shrink_as_the_hand_is_played():
    game = Game(seed=12, first_player=HUMAN)
    rng = random.Random(0)
    before = len(ai.unseen_cards(game, HUMAN))
    for _ in range(6):
        ai.take_turn(game, game.turn, ai.NORMAL, rng)
    after = len(ai.unseen_cards(game, HUMAN))
    assert after < before
    for card in game.captured[HUMAN] + game.captured[AI] + game.table:
        assert card not in ai.unseen_cards(game, HUMAN)


def test_the_risk_of_a_sweep_is_zero_when_nothing_can_clear_the_table():
    table = [Card(KING, "Spades"), Card(KING, "Hearts")]
    unseen = [Card(rank, "Clubs") for rank in (2, 3, 4)]
    assert ai.sweep_risk(table, unseen, 3) == 0.0
    single = [Card(3, "Spades")]
    assert ai.sweep_risk(single, unseen, 3) > 0.0


def test_the_expert_and_the_greedy_level_agree_on_a_forced_move():
    game = rigged(table=[Card(4, "Spades")], hand=[Card(4, "Clubs")],
                  other=[Card(2, "Clubs")], stock=list(new_deck()[:6]))
    for level in ai.LEVELS:
        assert ai.choose_move(game, HUMAN, level, random.Random(0)) == \
            (0, (Card(4, "Spades"),)), level


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
