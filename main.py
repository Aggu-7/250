"""Play one 250 game. P1 is human unless --auto."""
import argparse
import random

from ai.random_ai import RandomAI
from game.game import Game
from game.player import PLAYER_IDS, player_name
from human import HumanPlayer


def build_agents(auto: bool, rng: random.Random):
    agents = {}
    for pid in PLAYER_IDS:
        if pid == 1 and not auto:
            agents[pid] = HumanPlayer(pid)
        else:
            agents[pid] = RandomAI(pid, random.Random(rng.random()))
    return agents


def main():
    ap = argparse.ArgumentParser(description="250 card game")
    ap.add_argument("--auto", action="store_true", help="all 5 players are random AIs")
    ap.add_argument("--debug", action="store_true", help="print hidden hands/teams (engine only)")
    ap.add_argument("--quiet", action="store_true", help="only print round summaries")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    agents = build_agents(args.auto, rng)
    log = (lambda m: None) if args.quiet else print
    game = Game(agents, rng, log=log, debug=args.debug, fixed_caller=None)
    result = game.run()
    if args.quiet:
        print(f"caller {player_name(result.caller)} bid {result.bid}: team "
              f"{result.team_points} {'WIN' if result.success else 'FAIL'}")
    print("\nScore change: " + "  ".join(
        f"{player_name(p)}={v:+d}" for p, v in result.deltas.items()))


if __name__ == "__main__":
    main()
