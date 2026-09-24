"""Bidding phase (Phase 2)."""
from __future__ import annotations

from typing import Callable, Dict

from .game_state import GameState, Phase
from .player import PLAYER_IDS, next_player, player_name
from .view import make_view

MIN_BID = 100
MAX_BID = 250
BID_STEP = 5


def run_bidding(state: GameState, agents: Dict[int, object], log: Callable[[str], None] = print,
                min_bid: int = MIN_BID, max_bid: int = MAX_BID, step: int = BID_STEP) -> None:
    """Round-robin auction starting at P1. Passing removes you; last one standing is caller.
    If everyone passes, the last player left becomes caller at the minimum bid."""
    active = list(PLAYER_IDS)
    high, bidder = None, None
    pid = PLAYER_IDS[0]
    while len(active) > 1:
        if pid in active and pid != bidder:
            floor = min_bid if high is None else high + step
            amount = None
            if floor <= max_bid:
                amount = agents[pid].bid(make_view(state, pid), floor, max_bid)
            if amount is None:
                active.remove(pid)
                state.bids.append((pid, None))
                log(f"  {player_name(pid)} passes")
            else:
                if not (floor <= amount <= max_bid and amount % step == 0):
                    raise ValueError(f"Invalid bid {amount} from {player_name(pid)} (floor {floor})")
                high, bidder = amount, pid
                state.bids.append((pid, amount))
                log(f"  {player_name(pid)} bids {amount}")
        pid = next_player(pid)
    state.caller = active[0]
    state.bid = high if high is not None else min_bid
    state.phase = Phase.CALLING
