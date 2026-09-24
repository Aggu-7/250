"""Authoritative GameState: the TRUTH. Private to the engine; never given to an AI."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from .card import Card, Suit
from .deck import deal, shuffled_deck
from .player import PLAYER_IDS
from .trick import Trick


class Phase(Enum):
    BIDDING = "bidding"
    CALLING = "calling"
    PLAY = "play"
    DONE = "done"


@dataclass
class GameState:
    hands: Dict[int, List[Card]]
    undealt: Dict[int, List[Card]] = field(default_factory=lambda: {p: [] for p in PLAYER_IDS})
    phase: Phase = Phase.BIDDING
    bids: List[Tuple[int, Optional[int]]] = field(default_factory=list)  # (player, amount|None=pass)
    caller: Optional[int] = None
    bid: Optional[int] = None
    trump: Optional[Suit] = None
    called_cards: Optional[Tuple[Card, Card]] = None
    friends: Set[int] = field(default_factory=set)  # actual teammates (excl. caller) — HIDDEN truth
    current_trick: Optional[Trick] = None
    tricks: List[Trick] = field(default_factory=list)
    points_won: Dict[int, int] = field(default_factory=lambda: {p: 0 for p in PLAYER_IDS})
    to_play: Optional[int] = None

    @classmethod
    def new(cls, rng: random.Random) -> "GameState":
        first, second = deal(shuffled_deck(rng))
        return cls(hands=first, undealt=second)

    # --- truth queries (engine / debug / scoring only) ---
    def deal_remaining(self) -> None:
        """Phase 4: deal the second 4 cards, then fix the hidden teams."""
        for pid in PLAYER_IDS:
            self.hands[pid].extend(self.undealt[pid])
            self.undealt[pid] = []
        if self.called_cards is not None:
            self.friends = {
                pid for pid in PLAYER_IDS
                for c in self.called_cards if c in self.hands[pid] and pid != self.caller
            }

    def caller_team(self) -> Set[int]:
        return {self.caller} | set(self.friends)

    def played_cards(self) -> List[Card]:
        cards = [c for t in self.tricks for _, c in t.plays]
        if self.current_trick:
            cards += [c for _, c in self.current_trick.plays]
        return cards
