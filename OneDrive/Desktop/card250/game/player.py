"""Player id helpers. Players are numbered 1..5; seating order is 1→2→3→4→5→1."""
PLAYER_IDS = (1, 2, 3, 4, 5)
NUM_PLAYERS = len(PLAYER_IDS)


def next_player(pid: int) -> int:
    return pid % NUM_PLAYERS + 1


def player_name(pid: int) -> str:
    return f"P{pid}"
