"""Explainable normal-level suggestions using only the player's information."""
import copy
import random
from .briscola import ai as briscola
from .briscola.engine import beats_lead
from .scopa import ai as scopa
from .tressette import ai as tressette
from .burraco import ai as burraco
from .burraco.engine import InvalidMeld, Stranded, wild_stands_for
from .poker import ai as poker


def suggest(kind, game):
    """Return a message, without playing or inspecting hidden card identities."""
    hand = game.hands[0]
    if game.game_over or game.turn != 0:
        return 'Wait for your turn to request a hint.'
    if kind == 'briscola':
        index = briscola._heuristic(game)
        card = hand[index]
        reason = ('This wins the current trick while limiting the card value spent.'
                  if game.lead_card and beats_lead(game.lead_card, card, game.trump_suit)
                  else 'Keep valuable cards and trumps for more profitable tricks.')
        return f'Play {card}.\n{reason}'
    if kind == 'scopa':
        index, take = scopa.choose_move(game, 0, scopa.NORMAL, random.Random(0))
        reason = ('Capture these table cards: ' + ', '.join(str(c) for c in take)
                  if take else 'This card stays on the table.')
        return (f'Play {hand[index]}.\n{reason}\n'
                'The suggestion weighs coins, settebello, primiera and the risk of a scopa.')
    if kind == 'tressette':
        index = tressette.choose_card(game, 0, tressette.NORMAL, random.Random(0))
        return (f'Play {hand[index]}.\n'
                'Respect the lead suit, preserve valuable cards and favour control of the suit.')
    if kind == 'poker':
        # The normal level reads only what this player may see, so the
        # suggestion cannot depend on the opponent's cards or the deck —
        # and a fixed seed keeps it the same suggestion twice over.
        action, amount = poker.choose_action(game, 0, poker.NORMAL, random.Random(0))
        if action == 'fold':
            move, reason = 'Fold.', 'The price is more than the hand can stand.'
        elif action == 'check':
            move, reason = 'Check.', 'Nothing to gain by betting: take the free card.'
        elif action == 'call':
            move = f'Call {game.to_call(0)}.'
            reason = 'The pot is large enough to justify the price of the next card.'
        elif action == 'raise':
            move = f'Raise to {amount}.'
            reason = 'The hand is ahead of what the other side is likely to hold.'
        else:
            move = f'Bet {amount}.'
            reason = 'A hand worth winning is worth betting for value.'
        return f'{move}\n{reason}'
    if not game.phase.drawn:
        if game.discards and burraco._pile_is_worth_taking(game, 0, burraco.NORMAL):
            return 'Take the discard pile.\nThe visible cards improve your possible melds enough to justify the cost.'
        return 'Draw a card from the stock.\nThe visible discard pile does not sufficiently improve your melds.'
    for meld in game.melds[0]:
        for card in hand:
            if card in wild_stands_for(meld):
                return f'Replace the wild card with {card}.\nRecover the wild card for another meld.'
    # Validate candidates on copies: closing and pot rules still apply.
    for cards in burraco._find_melds(list(hand)):
        trial = copy.deepcopy(game)
        try:
            trial.lay_meld(0, cards)
        except (RuntimeError, InvalidMeld, Stranded):
            continue
        return ('Lay down: ' + ', '.join(str(c) for c in cards)
                + '\nMove these cards onto the table to reduce your hand penalty.')
    for i, meld in enumerate(game.melds[0]):
        for card in hand:
            trial = copy.deepcopy(game)
            try:
                trial.extend_meld(0, trial.melds[0][i], [card])
            except (RuntimeError, InvalidMeld, Stranded):
                continue
            return f'Add {card} to meld {i + 1}.\nGrow the meld towards a burraco.'
    card = burraco._card_to_discard(game, 0)
    return f'Discard {card}.\nKeep cards that are more useful for building or extending melds.'
