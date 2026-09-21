"""Tressette rules: the order, the obligation to follow suit, and the thirds."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.cards import ACE, JACK, KING, QUEEN, SUITS, Card, new_deck
from cardgames.tressette import ai
from cardgames.tressette.engine import (AI, HAND_SIZE, HUMAN, LAST_TRICK_THIRDS,
                                        ORDER, STRENGTH, THIRDS, TOTAL_POINTS,
                                        TOTAL_THIRDS, TRICKS_PER_GAME, Game,
                                        Match, MustFollowSuit, beats_lead,
                                        declarations)


def rigged(mine, theirs, stock=(), leader=HUMAN):
    """A position built by hand, for a rule that a deal will not show often."""
    game = Game(seed=0, first_leader=leader)
    game.hands = [list(mine), list(theirs)]
    game.stock = list(stock)
    game.thirds = [0, 0]
    game.bonus = [0, 0]
    game.declared = [[], []]
    game.captured = [[], []]
    game.table = []
    game.turn = leader
    game.leader = leader
    game.tricks_played = 0
    game.history = []
    return game


def play_deal(seed, level=ai.EASY, other=None, leader=None):
    """A whole deal played by the opponent code on both sides."""
    leader = seed % 2 if leader is None else leader
    game = Game(seed=seed, first_leader=leader)
    rng = random.Random(seed * 31 + 7)
    levels = {HUMAN: level, AI: other or level}
    while not game.game_over:
        while not game.trick_complete:
            index = ai.choose_card(game, game.turn, levels[game.turn], rng)
            game.play_card(game.turn, index)
        game.resolve_trick()
    return game


# --- the deck and the order -----------------------------------------------

def test_the_deal_is_ten_each_and_twenty_in_the_stock():
    game = Game(seed=3)
    assert len(game.hands[HUMAN]) == HAND_SIZE
    assert len(game.hands[AI]) == HAND_SIZE
    assert game.cards_left == 20
    everything = game.hands[HUMAN] + game.hands[AI] + game.stock
    assert sorted(map(str, everything)) == sorted(map(str, new_deck()))


def test_the_order_inside_a_suit_is_the_tressette_one():
    assert ORDER[:3] == (3, 2, ACE), "three, two, ace - then the court"
    ranked = sorted(ORDER, key=lambda rank: STRENGTH[rank], reverse=True)
    assert ranked == [3, 2, ACE, KING, QUEEN, JACK, 7, 6, 5, 4]
    assert STRENGTH[3] > STRENGTH[ACE] > STRENGTH[KING]
    assert STRENGTH[4] == min(STRENGTH.values())


def test_the_thirds_are_the_classic_ones():
    assert THIRDS[ACE] == 3
    for rank in (2, 3, JACK, QUEEN, KING):
        assert THIRDS[rank] == 1, rank
    for rank in (4, 5, 6, 7):
        assert THIRDS[rank] == 0, rank
    in_deck = sum(THIRDS[card.rank] for card in new_deck())
    assert in_deck == 32, "eight thirds a suit"
    assert in_deck + LAST_TRICK_THIRDS == TOTAL_THIRDS
    assert TOTAL_POINTS == 11, "eleven whole points, and two thirds thrown away"


# --- winning a trick ------------------------------------------------------

def test_the_highest_card_of_the_suit_led_wins():
    assert beats_lead(Card(ACE, "Spades"), Card(3, "Spades"))
    assert not beats_lead(Card(3, "Spades"), Card(ACE, "Spades"))
    assert beats_lead(Card(JACK, "Spades"), Card(KING, "Spades"))
    assert beats_lead(Card(4, "Spades"), Card(5, "Spades"))
    assert not beats_lead(Card(5, "Spades"), Card(4, "Spades"))


def test_another_suit_never_wins_because_there_is_no_trump():
    for suit in SUITS:
        if suit == "Spades":
            continue
        assert not beats_lead(Card(4, "Spades"), Card(3, suit)), \
            "the three of another suit still loses to a four"


def test_the_trick_goes_to_the_right_player():
    game = rigged(mine=[Card(4, "Spades")], theirs=[Card(ACE, "Spades")])
    game.play_card(HUMAN, 0)
    game.play_card(AI, 0)
    assert game.trick_winner() == AI
    result = game.resolve_trick()
    assert result.winner == AI
    assert result.thirds == THIRDS[ACE] + LAST_TRICK_THIRDS


# --- the obligation to follow suit ----------------------------------------

def test_you_must_follow_suit_when_you_can():
    game = rigged(mine=[Card(4, "Hearts"), Card(ACE, "Spades")],
                  theirs=[Card(KING, "Spades"), Card(2, "Hearts")],
                  leader=AI)
    game.play_card(AI, 0)                     # leads a spade
    assert game.legal_cards(HUMAN) == [1], "only the spade is playable"
    try:
        game.play_card(HUMAN, 0)
    except MustFollowSuit:
        pass
    else:
        raise AssertionError("the heart should have been refused")
    assert len(game.hands[HUMAN]) == 2, "and the card stayed in hand"
    game.play_card(HUMAN, 1)
    assert game.trick_complete


def test_anything_goes_when_the_suit_is_not_in_your_hand():
    game = rigged(mine=[Card(4, "Hearts"), Card(5, "Hearts")],
                  theirs=[Card(KING, "Spades"), Card(2, "Hearts")],
                  leader=AI)
    game.play_card(AI, 0)
    assert game.legal_cards(HUMAN) == [0, 1]
    game.play_card(HUMAN, 0)
    assert game.trick_winner() == AI


def test_leading_is_free():
    game = Game(seed=4, first_leader=HUMAN)
    assert game.legal_cards(HUMAN) == list(range(HAND_SIZE))


def test_the_obligation_holds_all_through_the_deal():
    """It applies while the stock lasts, not only at the end."""
    for seed in range(20):
        game = Game(seed=seed, first_leader=seed % 2)
        rng = random.Random(seed)
        while not game.game_over:
            while not game.trick_complete:
                player = game.turn
                lead = game.lead_card
                index = rng.choice(game.legal_cards(player))
                card = game.hands[player][index]
                if lead is not None and card.suit != lead.suit:
                    assert not any(one.suit == lead.suit
                                   for one in game.hands[player]), \
                        f"seed {seed}: a card of {lead.suit} was still held"
                game.play_card(player, index)
            game.resolve_trick()


# --- drawing --------------------------------------------------------------

def test_the_winner_draws_first_and_both_draws_are_shown():
    stock = [Card(ACE, "Clubs"), Card(2, "Clubs")]
    game = rigged(mine=[Card(4, "Spades"), Card(5, "Spades")],
                  theirs=[Card(ACE, "Spades"), Card(6, "Spades")],
                  stock=stock)
    game.play_card(HUMAN, 0)
    game.play_card(AI, 0)
    result = game.resolve_trick()
    assert result.winner == AI
    assert result.drawn[AI] == stock[0], "the winner takes the top card"
    assert result.drawn[HUMAN] == stock[1]
    assert game.drawn == result.drawn, "and the table remembers both"
    assert stock[0] in game.hands[AI] and stock[1] in game.hands[HUMAN]


def test_nothing_is_drawn_once_the_stock_is_empty():
    game = rigged(mine=[Card(4, "Spades"), Card(5, "Spades")],
                  theirs=[Card(ACE, "Spades"), Card(6, "Spades")])
    game.play_card(HUMAN, 0)
    game.play_card(AI, 0)
    result = game.resolve_trick()
    assert result.drawn == {HUMAN: None, AI: None}
    assert len(game.hands[HUMAN]) == 1


def test_the_last_trick_is_worth_three_thirds():
    game = rigged(mine=[Card(4, "Spades"), Card(5, "Spades")],
                  theirs=[Card(6, "Spades"), Card(7, "Spades")])
    game.play_card(HUMAN, 0)
    game.play_card(AI, 0)
    first = game.resolve_trick()
    assert not first.last and first.thirds == 0
    game.play_card(game.turn, 0)
    game.play_card(game.turn, 0)
    last = game.resolve_trick()
    assert last.last and last.thirds == LAST_TRICK_THIRDS


# --- scoring --------------------------------------------------------------

def test_the_remainder_of_the_thirds_is_thrown_away():
    game = rigged(mine=[], theirs=[])
    game.thirds = [17, 18]
    assert game.scores() == [5, 6], "seventeen thirds is five points, not six"
    game.thirds = [2, 33]
    assert game.scores() == [0, 11]


def test_declarations_are_added_as_whole_points():
    game = rigged(mine=[], theirs=[])
    game.thirds = [9, 9]
    game.bonus = [3, 0]
    assert game.scores() == [6, 3]


def test_a_napoletana_is_the_ace_two_and_three_of_one_suit():
    hand = [Card(ACE, "Hearts"), Card(2, "Hearts"), Card(3, "Hearts"),
            Card(5, "Spades")]
    found = declarations(hand)
    assert [one.kind for one in found] == ["napoletana"]
    assert found[0].suit == "Hearts" and found[0].points == 3
    assert "napoletana in Hearts" == str(found[0])
    # Spread across suits it is nothing at all.
    assert declarations([Card(ACE, "Hearts"), Card(2, "Spades"),
                         Card(3, "Clubs")]) == []


def test_three_and_four_of_a_kind_are_good_game():
    three = [Card(ACE, suit) for suit in SUITS[:3]]
    found = declarations(three)
    assert [one.points for one in found] == [3]
    assert str(found[0]) == "three aces"

    four = [Card(2, suit) for suit in SUITS]
    found = declarations(four)
    assert [one.points for one in found] == [4]
    assert str(found[0]) == "four twos"

    # Only the ace, the two and the three can be declared.
    assert declarations([Card(KING, suit) for suit in SUITS]) == []
    assert declarations([Card(ACE, "Hearts"), Card(ACE, "Spades")]) == [], \
        "two of a kind is nothing"


def test_one_hand_can_hold_several_declarations():
    hand = [Card(ACE, "Hearts"), Card(2, "Hearts"), Card(3, "Hearts"),
            Card(ACE, "Spades"), Card(ACE, "Clubs")]
    found = declarations(hand)
    kinds = sorted(one.kind for one in found)
    assert kinds == ["good game", "napoletana"]
    assert sum(one.points for one in found) == 6, \
        "three aces and a napoletana, and the ace of hearts serves in both"


def test_the_deal_counts_the_declarations_it_was_given():
    for seed in range(30):
        game = Game(seed=seed)
        for player in (HUMAN, AI):
            expected = sum(one.points
                           for one in declarations(game.hands[player]))
            assert game.bonus[player] == expected, seed


# --- whole deals ----------------------------------------------------------

def test_every_deal_accounts_for_every_third():
    for seed in range(60):
        game = play_deal(seed)
        assert game.tricks_played == TRICKS_PER_GAME, seed
        assert sum(game.thirds) == TOTAL_THIRDS, (seed, game.thirds)
        held = game.captured[HUMAN] + game.captured[AI]
        assert sorted(map(str, held)) == sorted(map(str, new_deck())), seed
        assert not game.hands[HUMAN] and not game.hands[AI]
        assert game.cards_left == 0


def test_a_deal_is_worth_eleven_points_less_what_the_division_drops():
    """Each side divides its own thirds by three, so both lose a remainder."""
    for seed in range(30):
        game = play_deal(seed)
        declared = game.bonus[HUMAN] + game.bonus[AI]
        taken = sum(game.thirds[player] // 3 for player in (HUMAN, AI))
        assert sum(game.scores()) == taken + declared, seed
        assert taken <= TOTAL_POINTS, seed
        assert taken >= TOTAL_POINTS - 2, \
            f"seed {seed}: at most two points can be lost to the remainders"


def test_every_level_follows_suit():
    for level in ai.LEVELS:
        for seed in range(4 if level == ai.HARD else 20):
            game = Game(seed=seed, first_leader=seed % 2)
            rng = random.Random(seed)
            while not game.game_over:
                while not game.trick_complete:
                    player = game.turn
                    index = ai.choose_card(game, player, level, rng)
                    assert index in game.legal_cards(player), \
                        f"{level} broke the obligation on seed {seed}"
                    game.play_card(player, index)
                game.resolve_trick()


def test_the_normal_level_beats_the_random_one():
    """Judged on thirds over deals played from both seats and both leads."""
    thirds = [0, 0]
    for seed in range(30):
        for leader in (HUMAN, AI):
            for swap in (False, True):
                first, second = ((ai.EASY, ai.NORMAL) if swap
                                 else (ai.NORMAL, ai.EASY))
                game = play_deal(seed, first, second, leader)
                mine, theirs = game.thirds
                thirds[0] += theirs if swap else mine
                thirds[1] += mine if swap else theirs
    share = thirds[0] / sum(thirds)
    assert share > 0.58, f"normal took only {share:.1%} of the thirds"


# --- what the opponent knows ----------------------------------------------

def test_it_only_counts_what_it_cannot_see():
    game = Game(seed=9)
    unseen = ai.unseen_cards(game, HUMAN)
    assert len(unseen) == 40 - HAND_SIZE
    for card in game.hands[HUMAN]:
        assert card not in unseen
    for card in game.hands[AI]:
        assert card in unseen


def test_it_knows_which_card_commands_a_suit():
    game = rigged(mine=[Card(2, "Spades")], theirs=[Card(4, "Spades")])
    unseen = ai.unseen_cards(game, HUMAN)
    assert not ai.commands(Card(2, "Spades"), unseen), "the three is still out"
    game.captured[AI] = [Card(3, "Spades")]
    unseen = ai.unseen_cards(game, HUMAN)
    assert ai.commands(Card(2, "Spades"), unseen), "now nothing beats it"


def test_it_takes_a_trick_worth_thirds_when_it_can():
    game = rigged(mine=[Card(4, "Hearts")],
                  theirs=[Card(3, "Spades"), Card(4, "Spades"),
                          Card(5, "Spades")],
                  stock=[Card(6, "Clubs")] * 2, leader=HUMAN)
    game.hands[HUMAN] = [Card(ACE, "Spades"), Card(7, "Hearts")]
    game.play_card(HUMAN, 0)                     # leads the ace: three thirds
    for level in (ai.NORMAL, ai.HARD):
        index = ai.choose_card(game, AI, level, random.Random(0))
        assert game.hands[AI][index] == Card(3, "Spades"), \
            f"{level} left three thirds on the table"


def test_it_does_not_spend_a_three_on_an_empty_trick():
    game = rigged(mine=[Card(4, "Spades"), Card(5, "Hearts")],
                  theirs=[Card(3, "Spades"), Card(7, "Spades"),
                          Card(6, "Hearts")],
                  stock=[Card(6, "Clubs")] * 4, leader=HUMAN)
    game.play_card(HUMAN, 0)                     # a four: nothing to win
    index = ai.choose_card(game, AI, ai.NORMAL, random.Random(0))
    assert game.hands[AI][index] == Card(7, "Spades"), \
        "the seven wins it just as well, and costs nothing"


# --- putting the hand in order --------------------------------------------

def test_sorting_by_suit_keeps_each_suit_together_and_in_order():
    game = rigged(mine=[Card(4, "Hearts"), Card(ACE, "Spades"),
                        Card(3, "Hearts"), Card(KING, "Spades"),
                        Card(2, "Hearts")], theirs=[])
    game.sort_hand(HUMAN, "suit")
    hand = game.hands[HUMAN]
    suits = [card.suit for card in hand]
    assert suits == sorted(suits, key=SUITS.index), "the suits are grouped"
    hearts = [card.rank for card in hand if card.suit == "Hearts"]
    assert hearts == [3, 2, 4], "and inside a suit the strongest comes first"
    assert [card.rank for card in hand if card.suit == "Spades"] == [ACE, KING]


def test_sorting_by_rank_uses_this_game_s_order_not_the_number():
    game = rigged(mine=[Card(4, "Hearts"), Card(ACE, "Spades"),
                        Card(3, "Clubs"), Card(2, "Diamonds"),
                        Card(JACK, "Hearts")], theirs=[])
    game.sort_hand(HUMAN, "rank")
    assert [card.rank for card in game.hands[HUMAN]] == [3, 2, ACE, JACK, 4], \
        "the three leads and the four is worthless, whatever the numbers say"


def test_sorting_loses_nothing():
    for by in ("suit", "rank"):
        game = Game(seed=11)
        before = sorted(map(str, game.hands[HUMAN]))
        game.sort_hand(HUMAN, by)
        assert sorted(map(str, game.hands[HUMAN])) == before, by
        assert len(game.hands[HUMAN]) == HAND_SIZE


def test_sorting_leaves_the_other_hand_alone():
    game = Game(seed=11)
    theirs = list(game.hands[AI])
    game.sort_hand(HUMAN, "rank")
    assert game.hands[AI] == theirs


# --- the match ------------------------------------------------------------

def test_a_match_runs_to_the_target_and_needs_a_lead():
    match = Match(target=21)
    match.add_hand([11, 0])
    match.add_hand([10, 1])
    assert match.totals == [21, 1] and match.over
    level = Match(target=21)
    level.add_hand([21, 21])
    assert not level.over, "level at the target settles nothing"


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
