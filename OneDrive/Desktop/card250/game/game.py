"""Game orchestration. Owns the GameState (truth) and hands agents only PlayerViews."""
from __future__ import annotations

import random
from typing import Callable, Dict, Optional

from .bidding import run_bidding
from .game_state import GameState, Phase
from .player import PLAYER_IDS, player_name
from .rules import begin_play, get_legal_cards, play_card, set_call
from .scoring import RoundResult, score_round
from .view import make_view
from .card import sort_hand


class Game:
    def __init__(self, agents: Dict[int, object], rng: Optional[random.Random] = None,
                 log: Callable[[str], None] = print, debug: bool = False,
                 fixed_caller: Optional[int] = 1, fixed_bid: int = 150):
        self.agents = agents
        self.rng = rng or random.Random()
        self.log = log
        self.debug = debug
        self.fixed_caller = fixed_caller  # None => run real bidding
        self.fixed_bid = fixed_bid
        self.state: Optional[GameState] = None

    def _dbg(self, msg: str) -> None:
        if self.debug:
            self.log(f"[DEBUG] {msg}")

    def _dbg_hands(self, title: str) -> None:
        for pid in PLAYER_IDS:
            self._dbg(f"{title} {player_name(pid)}: {' '.join(map(str, sort_hand(self.state.hands[pid])))}")

    def run(self) -> RoundResult:
        s = self.state = GameState.new(self.rng)
        self.log("\n=== New round ===")
        self._dbg_hands("initial 4 |")

        # Phase 2: bidding (or fixed caller for easy testing)
        if self.fixed_caller is None:
            self.log("Bidding:")
            run_bidding(s, self.agents, self.log)
        else:
            s.caller, s.bid, s.phase = self.fixed_caller, self.fixed_bid, Phase.CALLING
            self.log(f"{player_name(s.caller)} is the caller by default (bid {s.bid}).")
        self.log(f"Caller: {player_name(s.caller)}  Bid: {s.bid}")

        # Phase 3: calling — agent sees only its own PlayerView
        trump, friend_cards = self.agents[s.caller].choose_call(make_view(s, s.caller))
        set_call(s, trump, friend_cards)
        self.log(f"Trump: {s.trump}   Called friend cards: {s.called_cards[0]}, {s.called_cards[1]}")

        # Phase 4: remaining deal (teams become fixed here, hidden)
        s.deal_remaining()
        self._dbg_hands("full hand |")
        self._dbg(f"friends of caller: {sorted(map(player_name, s.friends)) or 'none (caller alone)'}; "
                  f"antis: {sorted(map(player_name, set(PLAYER_IDS) - s.caller_team()))}")

        # Phase 5: play 8 tricks
        begin_play(s)
        trick_no = 1
        while s.phase == Phase.PLAY:
            pid = s.to_play
            if not s.current_trick.plays:
                self.log(f"\n-- Trick {trick_no} (led by {player_name(pid)}) --")
            legal = get_legal_cards(pid, s)
            card = self.agents[pid].choose_card(make_view(s, pid), tuple(legal))
            done = play_card(s, pid, card)  # engine re-validates legality
            note = ""
            if card in s.called_cards:
                note = "   <-- called card revealed!"
            self.log(f"  {player_name(pid)} plays {card}{note}")
            if done:
                self.log(f"  => {player_name(done.winner)} wins the trick (+{done.points})")
                trick_no += 1

        # Phase 6: scoring
        result = score_round(s)
        self.log("\n=== Round over ===")
        friends = ", ".join(map(player_name, sorted(result.friends))) or "none"
        self.log(f"Caller team: {player_name(result.caller)} + friends: {friends}")
        self.log(f"Team points: {result.team_points} vs bid {result.bid} -> "
                 f"{'CALLER TEAM WINS' if result.success else 'CALLER TEAM FAILS'}")
        self.log("Points taken: " + "  ".join(f"{player_name(p)}={v}" for p, v in result.points_won.items()))
        self.log("Score change: " + "  ".join(f"{player_name(p)}={v:+d}" for p, v in result.deltas.items()))
        return result
