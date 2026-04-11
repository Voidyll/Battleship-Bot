"""
Self-play game runner for the trained Battleship AI.

Usage (from project root):
    python AI/self_play.py

Examples:
    python AI/self_play.py --seed 42
    python AI/self_play.py --show-boards
    python AI/self_play.py --no-boards
    python AI/self_play.py --output AI/self_play_logs/game_001.txt
"""

import argparse
from datetime import datetime
import os
import sys

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from AI.agent import Agent
from game.game import Game, GamePhase, GridState, ShotState


def _coord_to_str(row: int, col: int) -> str:
    return f"{chr(ord('A') + col)}{row + 1}"


def _render_shot_tracker(
    tracker: np.ndarray,
    highlight: tuple[int, int] | None = None,
    highlight_symbol: str = '*',
) -> str:
    symbol = {
        int(ShotState.UNKNOWN): '.',
        int(ShotState.MISS): 'o',
        int(ShotState.HIT): 'x',
        int(ShotState.SUNK): '#',
    }
    rows = []
    header = '   ' + ' '.join(chr(ord('A') + c) for c in range(tracker.shape[1]))
    rows.append(header)
    for r in range(tracker.shape[0]):
        row_cells: list[str] = []
        for c, v in enumerate(tracker[r]):
            if highlight is not None and (r, c) == highlight:
                row_cells.append(highlight_symbol)
            else:
                row_cells.append(symbol[int(v)])
        row_symbols = ' '.join(row_cells)
        rows.append(f"{r + 1:2d} {row_symbols}")
    return '\n'.join(rows)


def _render_own_board(grid: np.ndarray) -> str:
    symbol = {
        int(GridState.EMPTY): '.',
        int(GridState.SHIP): 'S',
        int(GridState.HIT): 'X',
        int(GridState.MISS): 'o',
    }
    rows = []
    header = '   ' + ' '.join(chr(ord('A') + c) for c in range(grid.shape[1]))
    rows.append(header)
    for r in range(grid.shape[0]):
        row_symbols = ' '.join(symbol[int(v)] for v in grid[r])
        rows.append(f"{r + 1:2d} {row_symbols}")
    return '\n'.join(rows)


def _build_turn_snapshot(
    game: Game,
    turn: int,
    player: int,
    shot_row: int,
    shot_col: int,
) -> str:
    """Build board snapshot text for the active player's perspective only."""
    lines: list[str] = []
    lines.append(f"\nBoard snapshot after turn {turn} (active player: P{player})")
    lines.append(f"\nP{player} own board")
    lines.append(_render_own_board(game.boards[player].grid))
    lines.append(f"\nP{player} shot tracker (* = this turn's shot)")
    lines.append(_render_shot_tracker(game.boards[player].shot_tracker, highlight=(shot_row, shot_col)))
    lines.append('-' * 70)
    return '\n'.join(lines)


def _has_checkpoint_weights(base_path: str) -> bool:
    has_h5 = (
        os.path.exists(f'{base_path}_placement.weights.h5')
        and os.path.exists(f'{base_path}_targeting.weights.h5')
    )
    has_npz = (
        os.path.exists(f'{base_path}_placement.weights.npz')
        and os.path.exists(f'{base_path}_targeting.weights.npz')
    )
    return has_h5 or has_npz


def _list_older_checkpoint_bases(checkpoint_dir: str) -> list[str]:
    """Return sorted checkpoint base paths for generation checkpoints (gen_XXXX)."""
    if not os.path.isdir(checkpoint_dir):
        return []

    suffixes = ('_placement.weights.h5', '_placement.weights.npz')
    bases: set[str] = set()

    for entry in os.listdir(checkpoint_dir):
        for suffix in suffixes:
            if entry.endswith(suffix):
                base_name = entry[:-len(suffix)]
                if base_name.startswith('gen_'):
                    base_path = os.path.join(checkpoint_dir, base_name)
                    if _has_checkpoint_weights(base_path):
                        bases.add(base_path)

    return sorted(bases)


def run_self_play(
    checkpoints_dir: str,
    seed: int,
    max_turns: int,
    show_boards: bool,
    output_path: str,
) -> int:
    rng = np.random.default_rng(seed)
    log_lines: list[str] = []

    def log(line: str = '') -> None:
        print(line)
        log_lines.append(line)

    final_model_path = os.path.join(checkpoints_dir, 'final_model')
    if not _has_checkpoint_weights(final_model_path):
        raise FileNotFoundError(
            f'Could not find final model weights at base path: {final_model_path}'
        )

    older_checkpoints = _list_older_checkpoint_bases(checkpoints_dir)
    if not older_checkpoints:
        raise FileNotFoundError(
            f'No older generation checkpoints found in: {checkpoints_dir}'
        )

    opponent_idx = int(rng.integers(0, len(older_checkpoints)))
    opponent_model_path = older_checkpoints[opponent_idx]

    log(f'[self-play] Player 1 model: {final_model_path}')
    log(f'[self-play] Player 2 model (random older checkpoint): {opponent_model_path}')

    agent_1 = Agent.load(final_model_path)
    agent_2 = Agent.load(opponent_model_path)

    game = Game()
    agent_1.place_all_ships(game.boards[1], rng)
    agent_2.place_all_ships(game.boards[2], rng)
    game.phase = GamePhase.BATTLE

    log('[self-play] Starting game: P1(final_model) vs P2(random older checkpoint)')

    turn = 0
    while not game.is_over() and turn < max_turns:
        player = game.current_turn
        agent = agent_1 if player == 1 else agent_2
        ai_state = game.get_ai_state(player)
        row, col = agent.choose_shot(ai_state)
        result = game.fire(player, row, col)

        turn += 1
        sunk = result['sunk_ship_name'] if result['sunk_ship_name'] else '-'
        log(
            f"Turn {turn:3d} | P{player} -> {_coord_to_str(row, col):>3} | "
            f"result={result['result']:<4} sunk={sunk}"
        )

        if show_boards:
            log(_build_turn_snapshot(game, turn, player, row, col))

    timed_out = not game.is_over()
    s1 = game.get_stats(1)
    s2 = game.get_stats(2)

    log('\n[self-play] Game complete')
    if timed_out:
        log(f"[self-play] Timed out at max_turns={max_turns}")
        winner = 0
    else:
        winner = int(game.winner or 0)
        log(f"[self-play] Winner: P{winner}")

    log(
        '[self-play] Summary | '
        f"turns={game.turn_count} "
        f"P1 shots={s1['shots_fired']} hits={s1['hits_made']} sunk={s1['ships_sunk']} "
        f"P2 shots={s2['shots_fired']} hits={s2['hits_made']} sunk={s2['ships_sunk']}"
    )

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines) + '\n')
    log(f"[self-play] Full log written to: {output_path}")

    return winner


def main() -> None:
    parser = argparse.ArgumentParser(description='Run self-play: P1 final_model vs P2 random older checkpoint.')
    parser.add_argument('--checkpoints-dir', type=str, default='AI/checkpoints',
                        help='Directory containing final_model and gen_XXXX checkpoints.')
    parser.add_argument('--seed', type=int, default=0,
                        help='Random seed for placement noise and deterministic replay.')
    parser.add_argument('--max-turns', type=int, default=200,
                        help='Safety cap on total turns before declaring timeout.')
    parser.add_argument('--show-boards', dest='show_boards', action='store_true', default=True,
                        help='Print board snapshots after every move (default: enabled).')
    parser.add_argument('--no-boards', dest='show_boards', action='store_false',
                        help='Disable board snapshots and print only move lines.')
    parser.add_argument('--output', type=str, default=None,
                        help='Path to save full game log. Default: AI/self_play_logs/self_play_<timestamp>.txt')
    args = parser.parse_args()

    output_path = args.output
    if output_path is None:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join('AI', 'self_play_logs', f'self_play_{stamp}.txt')

    run_self_play(
        checkpoints_dir=args.checkpoints_dir,
        seed=args.seed,
        max_turns=args.max_turns,
        show_boards=args.show_boards,
        output_path=output_path,
    )


if __name__ == '__main__':
    main()
