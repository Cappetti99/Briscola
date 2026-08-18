"""Burraco rules: melds, wild cards, the pot, closing and scoring."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames.burraco.engine import (AI, BURRACO_CLEAN, BURRACO_DIRTY,
                                      CARD_POINTS, CLOSING_BONUS, HAND_SIZE,
                                      HUMAN, POT_NOT_TAKEN, POT_SIZE, Game,
                                      InvalidMeld, Meld, RUN, SET, build_meld,
                                      can_extend, is_wild, order_meld,
                                      the_wild, wild_stands_for)
from cardgames.cards import (ACE, JOKER_RANK, KING, QUEEN, SUITS, Card,
                             burraco_deck)

SUIT_ORDER = {suit: index for index, suit in enumerate(SUITS)}

JOKER = Card(JOKER_RANK, "Joker")


def meld_or_none(cards):
    try:
        return build_meld(cards)
    except InvalidMeld:
        return None


# --- the deck -------------------------------------------------------------

def test_deck_is_two_full_decks():
    deck = burraco_deck()
    assert len(deck) == 108
    counts = Counter(deck)
    assert counts[JOKER] == 4, "two jokers per deck"
    ranked = {card: n for card, n in counts.items() if not card.is_joker}
    assert len(ranked) == 52, "one full deck's worth of distinct cards"
    assert set(ranked.values()) == {2}, "every ranked card appears twice"


def test_deal_puts_every_card_somewhere():
    game = Game(seed=3)
    assert [len(hand) for hand in game.hands] == [HAND_SIZE, HAND_SIZE]
    assert [len(pot) for pot in game.pots] == [POT_SIZE, POT_SIZE]
    everywhere = (game.hands[0] + game.hands[1] + game.pots[0] + game.pots[1]
                  + game.stock + game.discards)
    assert len(everywhere) == 108
    assert Counter(everywhere) == Counter(burraco_deck())


# --- sets -----------------------------------------------------------------

def test_plain_set():
    meld = build_meld([Card(9, "Hearts"), Card(9, "Spades"), Card(9, "Clubs")])
    assert meld.kind == SET and meld.wilds == 0


def test_set_may_repeat_a_card_since_there_are_two_decks():
    meld = build_meld([Card(9, "Hearts"), Card(9, "Hearts"), Card(9, "Clubs")])
    assert meld.kind == SET


def test_set_with_a_joker_or_a_wild_two():
    assert build_meld([Card(9, "Hearts"), Card(9, "Spades"), JOKER]).wilds == 1
    assert build_meld([Card(9, "Hearts"), Card(9, "Spades"),
                       Card(2, "Clubs")]).wilds == 1


def test_a_set_of_twos_is_natural():
    meld = build_meld([Card(2, "Hearts"), Card(2, "Spades"), Card(2, "Clubs")])
    assert meld.kind == SET and meld.wilds == 0, "twos in a set are just twos"


def test_two_wilds_in_one_meld_are_refused():
    assert meld_or_none([Card(9, "Hearts"), JOKER, JOKER]) is None
    assert meld_or_none([Card(9, "Hearts"), JOKER, Card(2, "Clubs")]) is None


def test_a_meld_needs_three_cards():
    assert meld_or_none([Card(9, "Hearts"), Card(9, "Spades")]) is None


def test_mixed_ranks_are_not_a_set():
    assert meld_or_none([Card(9, "Hearts"), Card(8, "Spades"),
                         Card(7, "Clubs")]) is None


# --- runs -----------------------------------------------------------------

def test_plain_run():
    meld = build_meld([Card(5, "Hearts"), Card(6, "Hearts"), Card(7, "Hearts")])
    assert meld.kind == RUN and meld.wilds == 0


def test_a_run_needs_one_suit():
    assert meld_or_none([Card(5, "Hearts"), Card(6, "Spades"),
                         Card(7, "Hearts")]) is None


def test_a_wild_fills_a_gap_or_extends_the_end():
    assert build_meld([Card(5, "Hearts"), JOKER, Card(7, "Hearts")]).wilds == 1
    assert build_meld([Card(5, "Hearts"), Card(6, "Hearts"), JOKER]).wilds == 1


def test_ace_runs_low_and_high():
    low = build_meld([Card(ACE, "Hearts"), Card(2, "Hearts"), Card(3, "Hearts")])
    assert low.kind == RUN and low.wilds == 0, "the two is natural in A-2-3"
    high = build_meld([Card(QUEEN, "Hearts"), Card(KING, "Hearts"),
                       Card(ACE, "Hearts")])
    assert high.kind == RUN and high.wilds == 0


def test_a_run_does_not_wrap_around_the_king():
    # K-A-2 is only legal read as Q(wild)-K-A, so the two must be the wild.
    meld = build_meld([Card(KING, "Hearts"), Card(ACE, "Hearts"),
                       Card(2, "Hearts")])
    assert meld.wilds == 1
    # With the queen already there the two has nowhere natural to sit.
    assert meld_or_none([Card(QUEEN, "Hearts"), Card(KING, "Hearts"),
                         Card(ACE, "Hearts"), Card(2, "Hearts")]).wilds == 1


def test_the_same_rank_twice_is_not_a_run():
    assert meld_or_none([Card(5, "Hearts"), Card(5, "Hearts"),
                         Card(6, "Hearts")]) is None


def test_a_gap_too_wide_for_one_wild():
    assert meld_or_none([Card(5, "Hearts"), Card(8, "Hearts"), JOKER]) is None


# --- burraco --------------------------------------------------------------

def seven_run(suit="Hearts", wild=False):
    cards = [Card(rank, suit) for rank in range(3, 10)]
    if wild:
        cards[3] = JOKER
    return build_meld(cards)


def test_seven_cards_make_a_burraco():
    clean = seven_run()
    assert clean.is_burraco and clean.is_clean
    assert clean.bonus() == BURRACO_CLEAN

    dirty = seven_run(wild=True)
    assert dirty.is_burraco and not dirty.is_clean
    assert dirty.bonus() == BURRACO_DIRTY


def test_six_cards_are_not_a_burraco_yet():
    meld = build_meld([Card(rank, "Hearts") for rank in range(3, 9)])
    assert not meld.is_burraco and meld.bonus() == 0


def test_meld_points_add_up():
    meld = build_meld([Card(ACE, "Hearts"), Card(2, "Hearts"),
                       Card(3, "Hearts")])
    assert meld.card_points() == CARD_POINTS[ACE] + CARD_POINTS[2] + CARD_POINTS[3]


def test_extending_a_meld():
    meld = build_meld([Card(5, "Hearts"), Card(6, "Hearts"), Card(7, "Hearts")])
    assert can_extend(meld, Card(8, "Hearts"))
    assert can_extend(meld, Card(4, "Hearts"))
    assert not can_extend(meld, Card(8, "Spades"))


def test_wild_cards_are_named_correctly():
    assert is_wild(JOKER) and is_wild(Card(2, "Hearts"))
    assert not is_wild(Card(ACE, "Hearts"))


# --- a turn ---------------------------------------------------------------

def test_a_turn_is_draw_then_discard():
    game = Game(seed=5, first_player=HUMAN)
    try:
        game.discard(HUMAN, game.hands[HUMAN][0])
    except RuntimeError:
        pass
    else:
        raise AssertionError("discarding before drawing should fail")

    game.draw(HUMAN)
    assert len(game.hands[HUMAN]) == HAND_SIZE + 1
    game.discard(HUMAN, game.hands[HUMAN][0])
    assert len(game.hands[HUMAN]) == HAND_SIZE
    assert game.turn == AI and len(game.discards) == 1


def test_playing_out_of_turn_is_refused():
    game = Game(seed=5, first_player=HUMAN)
    try:
        game.draw(AI)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the other player should not be able to draw")


def test_taking_the_discard_pile_takes_all_of_it():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    game.discard(HUMAN, game.hands[HUMAN][0])
    game.draw(AI)
    game.discard(AI, game.hands[AI][0])
    assert len(game.discards) == 2

    before = len(game.hands[HUMAN])
    taken = game.take_discards(HUMAN)
    assert len(taken) == 2
    assert len(game.hands[HUMAN]) == before + 2
    assert game.discards == []


def test_melded_cards_leave_the_hand():
    game = Game(seed=5, first_player=HUMAN)
    game.hands[HUMAN] = [Card(5, "Hearts"), Card(6, "Hearts"),
                         Card(7, "Hearts"), Card(KING, "Clubs")]
    game.draw(HUMAN)
    meld = game.lay_meld(HUMAN, [Card(5, "Hearts"), Card(6, "Hearts"),
                                 Card(7, "Hearts")])
    assert meld in game.melds[HUMAN]
    assert Card(5, "Hearts") not in game.hands[HUMAN]


def test_an_illegal_meld_leaves_the_hand_alone():
    game = Game(seed=5, first_player=HUMAN)
    game.hands[HUMAN] = [Card(5, "Hearts"), Card(9, "Spades"),
                         Card(KING, "Clubs")]
    game.draw(HUMAN)
    before = sorted(map(str, game.hands[HUMAN]))
    try:
        game.lay_meld(HUMAN, [Card(5, "Hearts"), Card(9, "Spades"),
                              Card(KING, "Clubs")])
    except InvalidMeld:
        pass
    else:
        raise AssertionError("that is not a meld")
    assert sorted(map(str, game.hands[HUMAN])) == before


# --- the pot and closing --------------------------------------------------

def test_emptying_your_hand_hands_you_the_pot():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    # One card left: discarding it empties the hand, which is what earns the pot.
    game.hands[HUMAN] = [Card(KING, "Clubs")]
    game.discard(HUMAN, Card(KING, "Clubs"))
    assert game.pot_taken[HUMAN] is True
    assert len(game.hands[HUMAN]) == POT_SIZE
    assert game.pots[HUMAN] == []


def test_closing_needs_the_pot_and_a_burraco():
    game = Game(seed=5, first_player=HUMAN)
    assert not game.may_close(HUMAN)

    game.pot_taken[HUMAN] = True
    assert not game.may_close(HUMAN), "a burraco is still missing"

    game.melds[HUMAN] = [seven_run()]
    assert game.may_close(HUMAN)


def test_scoring_counts_melds_up_and_the_hand_down():
    game = Game(seed=5)
    game.melds[HUMAN] = [seven_run()]
    game.hands[HUMAN] = [Card(ACE, "Clubs")]
    game.pot_taken[HUMAN] = True

    expected = seven_run().points() - CARD_POINTS[ACE]
    assert game.score(HUMAN) == expected

    game.closed_by = HUMAN
    assert game.score(HUMAN) == expected + CLOSING_BONUS


def test_never_taking_the_pot_costs_you():
    game = Game(seed=5)
    game.hands[HUMAN] = []
    game.pot_taken[HUMAN] = False
    assert game.score(HUMAN) == POT_NOT_TAKEN


def test_winner_compares_the_two_scores():
    game = Game(seed=5)
    game.pot_taken = [True, True]
    game.melds[HUMAN] = [seven_run()]
    game.melds[AI] = []
    game.hands = [[], []]
    assert game.winner() == HUMAN


# --- the pinella, taken back out of a meld --------------------------------

def test_a_wild_in_a_run_stands_for_one_card():
    run = build_meld([Card(5, "Hearts"), JOKER, Card(7, "Hearts")])
    assert wild_stands_for(run) == [Card(6, "Hearts")]


def test_a_wild_at_the_end_of_a_run_stands_for_either_end():
    run = build_meld([Card(5, "Hearts"), Card(6, "Hearts"), JOKER])
    assert set(wild_stands_for(run)) == {Card(4, "Hearts"), Card(7, "Hearts")}


def test_a_wild_in_a_set_stands_for_any_of_that_rank():
    meld = build_meld([Card(9, "Hearts"), Card(9, "Spades"), JOKER])
    assert set(wild_stands_for(meld)) == {Card(9, suit) for suit in
                                          ("Diamonds", "Hearts", "Spades", "Clubs")}


def test_a_meld_with_no_wild_has_nothing_to_swap():
    assert wild_stands_for(seven_run()) == []


def test_swapping_the_pinella_puts_it_back_in_your_hand():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    game.melds[HUMAN] = [build_meld([Card(5, "Hearts"), JOKER,
                                     Card(7, "Hearts")])]
    game.hands[HUMAN] = [Card(6, "Hearts")]

    freed = game.substitute_wild(HUMAN, game.melds[HUMAN][0], Card(6, "Hearts"))
    assert freed == JOKER
    assert JOKER in game.hands[HUMAN]
    meld = game.melds[HUMAN][0]
    assert meld.wilds == 0 and Card(6, "Hearts") in meld.cards
    assert len(meld) == 3


def test_you_cannot_swap_in_the_wrong_card():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    game.melds[HUMAN] = [build_meld([Card(5, "Hearts"), JOKER,
                                     Card(7, "Hearts")])]
    game.hands[HUMAN] = [Card(6, "Spades")]
    try:
        game.substitute_wild(HUMAN, game.melds[HUMAN][0], Card(6, "Spades"))
    except InvalidMeld:
        pass
    else:
        raise AssertionError("the six of spades is not what the joker stands for")


# --- melding out ----------------------------------------------------------

def test_laying_down_your_last_cards_takes_the_pot():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    game.hands[HUMAN] = [Card(5, "Hearts"), Card(6, "Hearts"), Card(7, "Hearts")]
    game.lay_meld(HUMAN, list(game.hands[HUMAN]))
    assert game.pot_taken[HUMAN] is True
    assert len(game.hands[HUMAN]) == POT_SIZE


def test_an_empty_hand_can_end_the_turn_without_discarding():
    game = Game(seed=5, first_player=HUMAN)
    game.draw(HUMAN)
    game.pot_taken[HUMAN] = True
    game.hands[HUMAN] = [Card(5, "Hearts"), Card(6, "Hearts"), Card(7, "Hearts")]
    game.lay_meld(HUMAN, list(game.hands[HUMAN]))
    assert game.hands[HUMAN] == []
    game.end_turn(HUMAN)
    assert game.turn == AI


# --- the computer plays ---------------------------------------------------

def test_the_computer_finishes_every_hand():
    """Both seats played by the computer: every hand has to end, and end well.

    An earlier draft never finished. Taking the discard pile only ever grows a
    hand, so a player who kept taking it never ran out of cards and the stock
    never drained.
    """
    import random

    from cardgames.burraco import ai as burraco_ai

    for seed in range(25):
        game = Game(seed=seed)
        rng = random.Random(seed)
        turns = 0
        while not game.game_over and turns < 300:
            burraco_ai.take_turn(game, game.turn, rng=rng)
            turns += 1

        assert game.game_over, f"seed {seed}: still going after {turns} turns"
        everywhere = Counter(game.hands[0] + game.hands[1] + game.stock
                             + game.discards + game.pots[0] + game.pots[1])
        for melds in game.melds:
            for meld in melds:
                everywhere.update(meld.cards)
        assert everywhere == Counter(burraco_deck()), f"seed {seed}: cards lost"
        assert isinstance(game.score(HUMAN), int)


def test_the_computer_only_makes_legal_melds():
    import random

    from cardgames.burraco import ai as burraco_ai

    for seed in range(15):
        game = Game(seed=seed)
        rng = random.Random(seed)
        turns = 0
        while not game.game_over and turns < 300:
            burraco_ai.take_turn(game, game.turn, rng=rng)
            turns += 1
        for melds in game.melds:
            for meld in melds:
                rebuilt = build_meld(meld.cards)
                assert rebuilt.kind == meld.kind
                assert rebuilt.wilds == meld.wilds
                assert len(meld) >= 3


def test_sorting_a_hand_by_suit_and_by_rank():
    game = Game(seed=4)
    game.sort_hand(HUMAN, "suit")
    hand = game.hands[HUMAN]
    plain = [card for card in hand if not is_wild(card)]
    suits = [card.suit for card in plain]
    assert suits == sorted(suits, key=lambda s: SUIT_ORDER[s]), "suits grouped"
    for first, second in zip(plain, plain[1:]):
        if first.suit == second.suit:
            assert first.rank <= second.rank, "and rising within a suit"

    game.sort_hand(HUMAN, "rank")
    plain = [card for card in game.hands[HUMAN] if not is_wild(card)]
    ranks = [card.rank for card in plain]
    assert ranks == sorted(ranks)


def test_sorting_puts_the_wild_cards_last():
    game = Game(seed=4)
    for by in ("suit", "rank"):
        game.sort_hand(HUMAN, by)
        wilds = [index for index, card in enumerate(game.hands[HUMAN])
                 if is_wild(card)]
        tail = list(range(len(game.hands[HUMAN]) - len(wilds),
                          len(game.hands[HUMAN])))
        assert wilds == tail, f"{by}: pinelle belong at the end"


def test_sorting_keeps_every_card():
    game = Game(seed=4)
    before = Counter(game.hands[HUMAN])
    game.sort_hand(HUMAN, "rank")
    assert Counter(game.hands[HUMAN]) == before


def test_a_meld_reads_in_order_however_it_was_played():
    meld = build_meld([Card(7, "Hearts"), Card(5, "Hearts"), Card(6, "Hearts")])
    assert [card.rank for card in meld.cards] == [5, 6, 7]


def test_the_wild_sits_in_the_hole_it_fills():
    meld = build_meld([Card(7, "Hearts"), Card(5, "Hearts"), JOKER])
    assert meld.cards[1] == JOKER, "the joker belongs between the five and seven"

    at_the_end = build_meld([Card(5, "Hearts"), Card(6, "Hearts"), JOKER])
    assert at_the_end.cards[-1] == JOKER, "with no hole it extends an end"


def test_an_ace_reads_high_or_low_as_the_run_needs():
    low = build_meld([Card(3, "Hearts"), Card(ACE, "Hearts"), Card(2, "Hearts")])
    assert [card.rank for card in low.cards] == [ACE, 2, 3]
    high = build_meld([Card(ACE, "Hearts"), Card(QUEEN, "Hearts"),
                       Card(KING, "Hearts")])
    assert [card.rank for card in high.cards] == [QUEEN, KING, ACE]


def test_cards_added_later_are_folded_into_the_order():
    game = Game(seed=1, first_player=HUMAN)
    game.draw(HUMAN)
    meld = build_meld([Card(5, "Hearts"), Card(6, "Hearts"), Card(7, "Hearts")])
    game.melds[HUMAN] = [meld]
    game.hands[HUMAN] = [Card(4, "Hearts"), Card(8, "Hearts")]

    game.extend_meld(HUMAN, meld, [Card(8, "Hearts")])
    game.extend_meld(HUMAN, meld, [Card(4, "Hearts")])
    assert [card.rank for card in meld.cards] == [4, 5, 6, 7, 8], \
        "a card added at the low end belongs at the low end"


def test_a_set_reads_by_suit_with_the_wild_last():
    meld = build_meld([Card(9, "Clubs"), Card(9, "Diamonds"), JOKER])
    assert meld.cards[-1] == JOKER
    assert [card.suit for card in meld.cards[:-1]] == ["Diamonds", "Clubs"]


def test_the_wild_is_named_correctly_in_each_kind():
    run = build_meld([Card(5, "Hearts"), JOKER, Card(7, "Hearts")])
    assert the_wild(run) == JOKER
    with_two = build_meld([Card(5, "Hearts"), Card(2, "Clubs"),
                           Card(7, "Hearts")])
    assert the_wild(with_two) == Card(2, "Clubs")
    assert the_wild(seven_run()) is None, "nothing wild in a clean run"


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
