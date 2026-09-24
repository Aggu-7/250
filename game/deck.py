"""Deck construction and dealing (Phase 1)."""
from __future__ import annotations

import random
from typing import Dict, List

from .card import Card, Rank, Suit
from .player import PLAYER_IDS

FIRST_DEAL = 4
SECOND_DEAL = 4


def build_deck() -> List[Card]:
    """40 cards: 5..A in 4 suits."""
    return [Card(r, s) for s in Suit for r in Rank]


def shuffled_deck(rng: random.Random) -> List[Card]:
    deck = build_deck()
    rng.shuffle(deck)
    return deck


def deal(deck: List[Card]) -> tuple[Dict[int, List[Card]], Dict[int, List[Card]]]:
    """Split a shuffled deck into (first 4 cards each, undealt second 4 each)."""
    assert len(deck) == len(PLAYER_IDS) * (FIRST_DEAL + SECOND_DEAL)
    first, second = {}, {}
    n = len(PLAYER_IDS) * FIRST_DEAL
    for i, pid in enumerate(PLAYER_IDS):
        first[pid] = deck[i * FIRST_DEAL:(i + 1) * FIRST_DEAL]
        second[pid] = deck[n + i * SECOND_DEAL:n + (i + 1) * SECOND_DEAL]
    return first, second
