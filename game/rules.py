"""Rules: calling validation, legal moves, playing cards (Phases 3-5)."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .card import Card, Rank, A_SPADES, Suit
from .game_state import GameState, Phase
from .player import next_player
from .trick import Trick, trick_winner

TRICKS_PER_ROUND = 8


class IllegalMove(Exception):
    pass


def validate_call(trump: Suit, friend_cards: Sequence[Card]) -> None:
    """Raise ValueError if the call is invalid."""
    if not isinstance(trump, Suit):
        raise ValueError("Trump must be a suit")
    if len(friend_cards) != 2 or friend_cards[0] == friend_cards[1]:
        raise ValueError("Choose two different friend cards")
    if A_SPADES in friend_cards:
        raise ValueError("A♠ cannot be called as a friend card")
    if any(card.rank not in (Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
           for card in friend_cards):
        raise ValueError("Friend cards must be face cards (J, Q, K, or A)")


def set_call(state: GameState, trump: Suit, friend_cards: Sequence[Card]) -> None:
    if state.phase != Phase.CALLING:
        raise IllegalMove("Not in calling phase")
    validate_call(trump, friend_cards)
    state.trump = trump
    state.called_cards = (friend_cards[0], friend_cards[1])


def begin_play(state: GameState) -> None:
    """Caller leads the first trick."""
    state.phase = Phase.PLAY
    state.to_play = state.caller
    state.current_trick = Trick(leader=state.caller)


def get_legal_cards(player_id: int, state: GameState) -> List[Card]:
    """Must follow the led suit if able; otherwise any card (cut with trump or discard)."""
    if state.phase != Phase.PLAY:
        return []
    hand = state.hands[player_id]
    trick = state.current_trick
    if trick is None or not trick.plays:
        return list(hand)
    follow = [c for c in hand if c.suit == trick.led_suit]
    return follow if follow else list(hand)


def play_card(state: GameState, player_id: int, card: Card) -> Optional[Trick]:
    """Play a card. Returns the finished Trick if this play completed one."""
    if state.phase != Phase.PLAY:
        raise IllegalMove("Not in play phase")
    if player_id != state.to_play:
        raise IllegalMove(f"It is not P{player_id}'s turn")
    if card not in get_legal_cards(player_id, state):
        raise IllegalMove(f"{card} is not legal for P{player_id}")

    state.hands[player_id].remove(card)
    trick = state.current_trick
    trick.add(player_id, card)
    if not trick.is_complete:
        state.to_play = next_player(player_id)
        return None

    trick.winner = trick_winner(trick.plays, state.trump)
    state.points_won[trick.winner] += trick.points
    state.tricks.append(trick)
    if len(state.tricks) == TRICKS_PER_ROUND:
        state.phase, state.current_trick, state.to_play = Phase.DONE, None, None
    else:
        state.current_trick = Trick(leader=trick.winner)
        state.to_play = trick.winner
    return trick
