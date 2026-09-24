"""Command-line human player (P1). Also only sees a PlayerView."""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

from ai.base_ai import BaseAI
from game.card import Card, Suit
from game.rules import validate_call
from game.view import PlayerView


def _fmt(cards) -> str:
    return "  ".join(str(c) for c in cards)


class HumanPlayer(BaseAI):
    def bid(self, view: PlayerView, min_amount: int, max_amount: int) -> Optional[int]:
        print(f"\nYour hand: {_fmt(view.my_hand)}")
        while True:
            s = input(f"Bid {min_amount}-{max_amount} (multiple of 5), or Enter to pass: ").strip()
            if s == "" or s.lower() in ("p", "pass"):
                return None
            if s.isdigit() and min_amount <= int(s) <= max_amount and int(s) % 5 == 0:
                return int(s)
            print("Invalid bid.")

    def choose_call(self, view: PlayerView) -> Tuple[Suit, Tuple[Card, Card]]:
        print(f"\nYou are the caller (bid {view.bid}). Your first 4 cards: {_fmt(view.my_hand)}")
        letters = {s.letter: s for s in Suit}
        while True:
            try:
                t = input("Trump suit (S/H/D/C): ").strip().upper()
                trump = letters[t]
                raw = input("Two friend cards, e.g. 'AH AD': ").split()
                cards = tuple(Card.parse(x) for x in raw)
                validate_call(trump, cards)
                return trump, cards  # type: ignore[return-value]
            except (KeyError, ValueError) as e:
                print(f"Invalid: {e}")

    def choose_card(self, view: PlayerView, legal_cards: Sequence[Card]) -> Card:
        print(f"\nTrump: {view.trump}   Called: {view.called_cards[0]}, {view.called_cards[1]}")
        if view.current_trick:
            print("On the table: " + "  ".join(f"P{p}:{c}" for p, c in view.current_trick))
        print(f"Your hand: {_fmt(view.my_hand)}")
        options = list(legal_cards)
        print("Legal: " + "  ".join(f"[{i + 1}] {c}" for i, c in enumerate(options)))
        while True:
            s = input("Play (number or card): ").strip()
            if s.isdigit() and 1 <= int(s) <= len(options):
                return options[int(s) - 1]
            try:
                c = Card.parse(s)
                if c in options:
                    return c
            except ValueError:
                pass
            print("Not a legal choice.")
