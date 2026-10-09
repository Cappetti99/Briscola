"""Texas Hold'em: rules, betting, scoring and the opponent, no window.

Run them like the others:

    conda run -n briscola python tests/test_poker.py
"""

import copy
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cardgames import training
from cardgames.cards import ACE, JACK, KING, QUEEN, Card
from cardgames.poker import ai as poker_ai
from cardgames.poker import engine as poker
from cardgames.session import encode

C = Card


def cards_in(game):
    """Every card the hand accounts for: stock, hands, board and muck."""
    return (list(game.stock)
            + [card for hand in game.hands for card in hand]
            + list(game.table) + list(game.mucked))


def play_out(game, rng, limit=80):
    """Drive a hand with arbitrary legal moves until it ends."""
    for _ in range(limit):
        if game.game_over:
            return
        legal = game.legal_actions(game.turn)
        assert legal, (game.phase, game.all_in, game.committed, game.acted)
        kind = rng.choice(sorted(legal))
        amount = None
        if kind in ("bet", "raise"):
            top = game.max_to(game.turn)
            options = sorted({value for value in
                              (game.min_to(game.turn),
                               max(game.committed) + game.pot, top)
                              if max(game.committed) < value <= top})
            amount = rng.choice(options) if options else None
            if amount is None:
                kind = "call" if "call" in legal else "check"
        game.act(game.turn, kind, amount)
    raise AssertionError("the hand never ended")


# --- the hand -------------------------------------------------------------

def test_the_deck_is_52_and_every_hand_starts_the_same_way():
    assert len(poker.poker_deck()) == 52
    assert len(set(map(str, poker.poker_deck()))) == 52
    for seed in range(5):
        game = poker.Game(seed=seed)
        assert [len(hand) for hand in game.hands] == [2, 2]
        assert sum(game.stacks) + sum(game.total) == 200
        assert game.phase == "preflop"
        assert len(game.stock) == 48


def test_the_button_posts_the_small_blind_and_acts_first():
    game = poker.Game(seed=4, first_player=poker.HUMAN)
    assert game.dealer == poker.HUMAN
    assert game.committed == [poker.SMALL_BLIND, poker.BIG_BLIND]
    assert game.turn == poker.HUMAN
    other = poker.Game(seed=4, first_player=poker.AI)
    assert other.dealer == poker.AI
    assert other.committed == [poker.BIG_BLIND, poker.SMALL_BLIND]
    assert other.turn == poker.AI


def test_the_hand_ends_with_the_same_200_chips_it_started_with():
    rng = random.Random(3)
    for seed in range(60):
        game = poker.Game(seed=seed, first_player=seed % 2)
        play_out(game, rng)
        # The stacks carry the whole 200 either way it went, and the cards
        # are all accounted for — in hand, on the board, in the muck or
        # still in the deck.
        assert sum(game.stacks) == 200, (seed, game.stacks)
        dealt = cards_in(game)
        assert len(dealt) == 52 and len(set(map(str, dealt))) == 52, seed


# --- the betting ----------------------------------------------------------

def test_checking_carries_on_to_the_next_street():
    game = poker.Game(seed=1, first_player=poker.HUMAN)
    game.act(poker.HUMAN, "call")            # the small blind completes
    game.act(poker.AI, "check")              # the big blind keeps its option
    assert game.phase == "flop"
    assert len(game.table) == 3
    # Heads-up, the big blind is first to act once the flop is out.
    assert game.turn == poker.AI


def test_a_raise_puts_the_answer_back():
    game = poker.Game(seed=2, first_player=poker.HUMAN)
    game.act(poker.HUMAN, "raise", 6)
    assert game.turn == poker.AI and not game.acted[poker.AI]
    game.act(poker.AI, "raise", 14)
    assert game.turn == poker.HUMAN and not game.acted[poker.HUMAN]
    game.act(poker.HUMAN, "call")
    assert game.phase == "flop"
    assert game.total == [14, 14]


def test_illegal_moves_are_refused_rather_than_approximated():
    game = poker.Game(seed=3, first_player=poker.HUMAN)
    for bad in (("check", None), ("raise", None), ("raise", 1),
                ("raise", 1000), ("bet", 5)):
        try:
            game.act(poker.HUMAN, *bad)
        except poker.IllegalAction:
            pass
        else:
            raise AssertionError(f"accepted {bad}")
    try:
        game.act(poker.AI, "call")
    except poker.IllegalAction:
        pass
    else:
        raise AssertionError("moved out of turn")
    assert not game.game_over


def test_a_fold_hands_over_the_pot_and_the_muck():
    game = poker.Game(seed=5, first_player=poker.HUMAN)
    assert game.act(poker.HUMAN, "fold") == "You fold"
    assert game.game_over and game.winner == poker.AI
    assert game.hands[poker.HUMAN] == []
    assert len(game.mucked) == 2
    assert sum(game.stacks) == 200
    assert game.stacks[poker.AI] > game.stacks[poker.HUMAN]
    assert "fold" in game.result_text
    # The other way round, the line the log gets says so too.
    game = poker.Game(seed=5, first_player=poker.AI)
    assert game.act(poker.AI, "fold") == "The computer folds"
    assert game.winner == poker.HUMAN


def test_all_in_runs_the_rest_of_the_board_out_with_no_more_betting():
    game = poker.Game(seed=6, first_player=poker.AI)
    game.stacks[poker.HUMAN] = 30        # a stack short of the button's
    chips = sum(game.stacks) + sum(game.total)
    game.act(poker.AI, "raise", game.max_to(poker.AI))
    game.act(poker.HUMAN, "call")        # all in for less
    assert game.game_over, game.phase
    assert len(game.table) == 5, "the board must be dealt out"
    assert game.showdown
    # Whatever the button put past the call came straight back.
    assert sum(game.stacks) == chips, (game.stacks, chips)


def test_a_split_pot_gives_both_sides_their_chips_back():
    game = poker.Game(seed=7, first_player=poker.HUMAN)
    # The five on the table make the hand for both of them, and neither
    # hole card can touch it: the pot simply comes back down the middle.
    game.hands = [[C(2, "Clubs"), C(3, "Clubs")],
                  [C(2, "Diamonds"), C(3, "Diamonds")]]
    game.table = [C(6, "Hearts"), C(7, "Hearts"), C(8, "Hearts"),
                  C(9, "Hearts"), C(10, "Hearts")]
    game.stock = []                      # nothing left to deal, so the
    game.phase = "flop"                  # remaining streets come up empty
    game.committed = [0, 0]              # the blinds are already in the pot
    while not game.game_over:
        game.act(game.turn, "check")
    assert game.split and game.winner is None
    assert game.names[0] == game.names[1]
    assert "Split pot" in game.result_text
    assert game.stacks == [100, 100]


# --- reading a hand -------------------------------------------------------

def test_the_categories_are_ordered_the_way_poker_orders_them():
    straight_flush = [C(9, "Hearts"), C(10, "Hearts"), C(JACK, "Hearts"),
                      C(QUEEN, "Hearts"), C(KING, "Hearts")]
    quads = [C(4, "Spades"), C(4, "Hearts"), C(4, "Clubs"), C(4, "Diamonds"),
             C(9, "Spades")]
    boat = [C(7, "Spades"), C(7, "Hearts"), C(7, "Clubs"), C(KING, "Diamonds"),
            C(KING, "Spades")]
    higher_boat = [C(KING, "Spades"), C(KING, "Hearts"), C(KING, "Clubs"),
                   C(7, "Diamonds"), C(7, "Spades")]
    flush = [C(2, "Spades"), C(6, "Spades"), C(9, "Spades"), C(JACK, "Spades"),
             C(ACE, "Spades")]
    straight = [C(4, "Clubs"), C(5, "Diamonds"), C(6, "Spades"), C(7, "Hearts"),
                C(8, "Clubs")]
    ordered = [straight_flush, quads, higher_boat, boat, flush, straight]
    ranked = [poker.best_hand(one) for one in ordered]
    assert ranked == sorted(ranked, reverse=True)
    assert poker.best_hand(straight_flush)[0] == poker.STRAIGHT_FLUSH
    assert poker.describe(straight_flush) == "a straight flush to the king"
    assert poker.describe(boat) == "a full house, sevens full of kings"
    assert poker.describe(higher_boat) == "a full house, kings full of sevens"
    assert poker.describe(flush) == "a flush, ace high"


def test_the_ace_goes_low_only_in_the_wheel():
    wheel = [C(ACE, "Spades"), C(2, "Hearts"), C(3, "Spades"), C(4, "Clubs"),
             C(5, "Diamonds")]
    key = poker.best_hand(wheel)
    assert key == (poker.STRAIGHT, 5)
    assert poker.describe(wheel) == "a straight to the five"
    # A-2-3-4-6 is no straight, and K-Q-J-10-A is the top one.
    assert poker.best_hand([C(ACE, "Spades"), C(2, "Hearts"),
                            C(3, "Spades"), C(4, "Clubs"),
                            C(6, "Diamonds")])[0] == poker.HIGH_CARD
    broadway = poker.best_hand([C(ACE, "Spades"), C(KING, "Hearts"),
                                C(QUEEN, "Spades"), C(JACK, "Clubs"),
                                C(10, "Diamonds")])
    assert broadway == (poker.STRAIGHT, 14)


def test_seven_cards_find_the_best_five_inside_them():
    made = [C(9, "Spades"), C(9, "Hearts"), C(ACE, "Clubs"),
            C(KING, "Diamonds"), C(QUEEN, "Clubs")]
    # Two cards that cannot touch the hand or its kickers change nothing.
    assert (poker.best_hand(made + [C(2, "Clubs"), C(3, "Diamonds")])
            == poker.best_hand(made))
    # A board flush is the hand for everyone who holds two of the suit...
    board = [C(2, "Spades"), C(6, "Spades"), C(9, "Spades"),
             C(JACK, "Spades"), C(ACE, "Spades")]
    assert (poker.best_hand(board + [C(KING, "Clubs"), C(7, "Diamonds")])[0]
            == poker.FLUSH)
    # ...and the ace-high straight flush sits above it.
    royal = [C(10, "Hearts"), C(JACK, "Hearts"), C(QUEEN, "Hearts"),
             C(KING, "Hearts"), C(ACE, "Hearts")]
    assert (poker.best_hand(royal + [C(2, "Clubs"), C(7, "Diamonds")])
            == poker.best_hand(royal))


def test_kickers_break_a_tie_that_the_pair_cannot():
    pair_of_nines_ace = [C(9, "Spades"), C(9, "Hearts"), C(ACE, "Clubs"),
                         C(7, "Diamonds"), C(3, "Spades")]
    pair_of_nines_king = [C(9, "Clubs"), C(9, "Diamonds"), C(KING, "Hearts"),
                          C(7, "Spades"), C(3, "Clubs")]
    assert (poker.best_hand(pair_of_nines_ace)
            > poker.best_hand(pair_of_nines_king))
    assert poker.describe(pair_of_nines_ace) == "a pair of nines"
    assert poker.describe(pair_of_nines_king) == "a pair of nines"


# --- the opponent ---------------------------------------------------------

def test_every_level_only_ever_plays_a_legal_move():
    rng = random.Random(11)
    for level in (poker_ai.EASY, poker_ai.NORMAL):
        for seed in (1, 2, 3, 7, 21):
            game = poker.Game(seed=seed, first_player=seed % 2)
            while not game.game_over:
                legal = game.legal_actions(game.turn)
                before = encode(game)
                action, amount = poker_ai.choose_action(
                    game, game.turn, level, rng)
                assert action in legal, (level, seed, action, legal)
                if action in ("bet", "raise"):
                    assert game.min_to(game.turn) <= amount <= game.max_to(
                        game.turn), (level, seed, amount)
                assert encode(game) == before, "choosing must not move the game"
                game.act(game.turn, action, amount)
            assert sum(game.stacks) == 200, (level, seed)


def test_the_expert_also_only_ever_plays_a_legal_move():
    # One decision a hand, because the expert samples for a living and a
    # full hand of it would make this suite take a minute rather than a
    # couple of seconds. The legality rules are the same ones.
    rng = random.Random(12)
    for seed in (1, 7, 21):
        game = poker.Game(seed=seed, first_player=seed % 2)
        before = encode(game)
        legal = game.legal_actions(game.turn)
        action, amount = poker_ai.choose_action(
            game, game.turn, poker_ai.HARD, rng)
        assert action in legal, (seed, action, legal)
        if action in ("bet", "raise"):
            assert game.min_to(game.turn) <= amount <= game.max_to(game.turn)
        assert encode(game) == before


def test_the_normal_level_never_folds_away_the_minimum_preflop_call():
    """Heads-up, one chip into a live pot is right with any two cards.

    It is also what the window's space-bar test relies on: skipping the
    computer's pause has to land back on the player, and a fold would end
    the hand first.
    """
    for seed in range(30):
        game = poker.Game(seed=seed, first_player=poker.AI)
        assert game.to_call(poker.AI) <= poker.BIG_BLIND
        action, _amount = poker_ai.choose_action(
            game, poker.AI, poker_ai.NORMAL, random.Random(seed))
        assert action != "fold", seed


def test_the_expert_counts_its_outs():
    game = poker.Game(seed=9, first_player=poker.AI)
    for _ in range(2):
        won = poker_ai.equity(game, poker.AI, random.Random(1))
        assert 0.0 <= won <= 1.0
    # The nut flush draw with a card to come is worth a great deal...
    game.phase = "turn"
    game.table = [C(2, "Spades"), C(7, "Spades"), C(JACK, "Spades"),
                  C(4, "Diamonds")]
    game.hands[poker.AI] = [C(ACE, "Spades"), C(8, "Hearts")]
    draw = poker_ai.equity(game, poker.AI, random.Random(2))
    assert draw > 0.45, draw
    # ...and live cards against a board already made for somebody else.
    game.table = [C(KING, "Clubs"), C(QUEEN, "Diamonds"), C(JACK, "Spades"),
                  C(2, "Hearts")]
    game.hands[poker.AI] = [C(4, "Clubs"), C(9, "Diamonds")]
    broken = poker_ai.equity(game, poker.AI, random.Random(3))
    assert broken < draw, (broken, draw)


def test_the_expert_folds_junk_and_never_folds_the_nuts():
    game = poker.Game(seed=10, first_player=poker.HUMAN)
    game.phase = "river"
    game.stock = []
    game.table = [C(KING, "Clubs"), C(QUEEN, "Diamonds"), C(JACK, "Spades"),
                  C(2, "Hearts"), C(6, "Clubs")]
    game.acted = [False, True]
    game.turn = poker.HUMAN
    game.committed = [0, 100]           # everything in, and nothing to call with
    game.total = [0, 100]
    game.hands[poker.HUMAN] = [C(4, "Clubs"), C(9, "Diamonds")]  # nine high
    action, _amount = poker_ai.choose_action(
        game, poker.HUMAN, poker_ai.HARD, random.Random(4))
    assert action == "fold", action
    # Nothing beats a royal flush, so against the very same bet the answer
    # cannot be a fold whatever the price is.
    game.hands[poker.HUMAN] = [C(ACE, "Hearts"), C(KING, "Hearts")]
    game.table = [C(QUEEN, "Hearts"), C(JACK, "Hearts"), C(10, "Hearts"),
                  C(2, "Clubs"), C(3, "Spades")]
    action, _amount = poker_ai.choose_action(
        game, poker.HUMAN, poker_ai.HARD, random.Random(5))
    assert action in ("call", "raise"), action


def test_the_expert_takes_no_longer_than_the_budget_allows():
    longest = 0.0
    for seed in range(4):
        game = poker.Game(seed=seed, first_player=poker.AI)
        started = time.perf_counter()
        poker_ai.choose_action(game, poker.AI, poker_ai.HARD,
                               random.Random(seed))
        longest = max(longest, time.perf_counter() - started)
    assert longest < 1.5, longest


# --- the training hint ----------------------------------------------------

def test_the_hint_depends_only_on_what_the_player_may_see():
    for seed in range(12):
        game = poker.Game(seed=seed)
        before = encode(game)
        hint = training.suggest("poker", game)
        assert isinstance(hint, str) and hint
        assert encode(game) == before, "the hint moved the table"
        # Replace every hidden identity with a card from the player's own
        # hand: the suggestion has no business changing.
        other = copy.deepcopy(game)
        other.hands[1] = [game.hands[0][0]] * len(other.hands[1])
        other.stock = [game.hands[0][0]] * len(other.stock)
        assert training.suggest("poker", other) == hint, (seed, hint)


def test_the_hint_is_only_offered_on_the_players_own_turn():
    game = poker.Game(seed=1, first_player=poker.AI)
    assert training.suggest("poker", game).startswith("Wait")
    game.act(poker.AI, "check") if "check" in game.legal_actions(poker.AI) \
        else game.act(poker.AI, "call")
    assert not game.game_over
    assert not training.suggest("poker", game).startswith("Wait")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok   {name}")
