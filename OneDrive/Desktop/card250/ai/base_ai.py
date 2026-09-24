"""Agent interface. Agents only ever see a PlayerView — never GameState or Game."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence, Tuple

from game.card import Card, Suit
from game.view import PlayerView


class BaseAI(ABC):
    def __init__(self, player_id: int):
        self.player_id = player_id

    @abstractmethod
    def bid(self, view: PlayerView, min_amount: int, max_amount: int) -> Optional[int]:
        """Return a bid in [min_amount, max_amount] (multiple of 5) or None to pass."""

    @abstractmethod
    def choose_call(self, view: PlayerView) -> Tuple[Suit, Tuple[Card, Card]]:
        """Caller only: choose trump and two friend cards."""

    @abstractmethod
    def choose_card(self, view: PlayerView, legal_cards: Sequence[Card]) -> Card:
        """Choose one of legal_cards."""
