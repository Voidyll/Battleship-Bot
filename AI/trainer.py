"""
Training Runner
================
Coordinates the full neuroevolution training loop.

Usage (from project root):
    python -m AI.trainer

What it does each generation:
  1. Each agent plays GAMES_PER_EVAL games against randomly chosen opponents
     from the same population (self-play).
  2. Fitness is computed from each agent's aggregate game stats.
  3. The genetic algorithm produces the next generation.
  4. Progress is printed to the terminal.
  5. Checkpoints are saved every CHECKPOINT_EVERY generations.

GPU note:
    TensorFlow will use your AMD integrated GPU via DirectML automatically
    if tensorflow-directml-plugin is installed:
        pip install tensorflow tensorflow-directml-plugin
    Batch inference (all agents in one GPU call per turn) is used to maximise
    GPU utilisation during the evaluation step.
"""

import os
import sys
import time

import numpy as np

# Ensure project root is on the path when run as a module
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from game.game import Game, GamePhase, Board, BOARD_SIZE, SHIP_DEFINITIONS, ShotState, random_place_all_ships
from AI import config
from AI.agent import Agent
from AI.fitness import compute_fitness, fitness_summary
from AI.genetic import create_population, next_generation, population_stats, best_agent
from AI.model import (
    backend_name,
    list_available_gpus,
)


# ---------------------------------------------------------------------------
# Single-game simulation (two agents play one full game)
# ---------------------------------------------------------------------------

def _simulate_game(
    agent_1:  Agent,
    agent_2:  Agent,
    rng:      np.random.Generator,
    max_turns: int,
) -> tuple[dict, dict]:
    """
    Play one complete game between agent_1 (P1) and agent_2 (P2).
    Returns (stats_p1, stats_p2) dicts from Game.get_stats().
    """
    game = Game()
    ship_sizes = {name: size for name, size in SHIP_DEFINITIONS}

    discovered: dict[int, set[str]] = {1: set(), 2: set()}
    pending_deadlines: dict[int, dict[str, int]] = {1: {}, 2: {}}
    find_events: dict[int, int] = {1: 0, 2: 0}
    quick_conversions: dict[int, int] = {1: 0, 2: 0}
    tactical_decisions: dict[int, int] = {1: 0, 2: 0}
    tactical_followups: dict[int, int] = {1: 0, 2: 0}
    tactical_ignores: dict[int, int] = {1: 0, 2: 0}

    def _ship_name_at(board: Board, row: int, col: int) -> str | None:
        for ship in board.ships:
            if (row, col) in ship.positions:
                return ship.name
        return None

    # --- placement phase ---
    agent_1.place_all_ships(game.boards[1], rng)
    agent_2.place_all_ships(game.boards[2], rng)
    game.phase = GamePhase.BATTLE  # boards already populated directly

    # --- battle phase ---
    turn = 0
    while not game.is_over() and turn < max_turns:
        p     = game.current_turn
        agent = agent_1 if p == 1 else agent_2
        state = game.get_ai_state(p)
        row, col = agent.choose_shot(state)

        # Tactical behavior signal: when unresolved hits exist, reward adjacent
        # follow-up shots and penalize shots elsewhere.
        unresolved_hits = np.argwhere(state['shot_tracker'] == int(ShotState.HIT))
        if len(unresolved_hits) > 0:
            tactical_decisions[p] += 1
            is_adjacent = False
            for hr, hc in unresolved_hits:
                if abs(int(hr) - row) + abs(int(hc) - col) == 1:
                    is_adjacent = True
                    break
            if is_adjacent:
                tactical_followups[p] += 1
            else:
                tactical_ignores[p] += 1

        opponent = 3 - p
        opponent_board = game.boards[opponent]
        shot = game.fire(p, row, col)

        if shot.get('success'):
            hit_ship_name = _ship_name_at(opponent_board, row, col)
            if shot['result'] == 'hit' and hit_ship_name is not None:
                if hit_ship_name not in discovered[p]:
                    discovered[p].add(hit_ship_name)
                    find_events[p] += 1
                    # Deadline rule requested by user:
                    # conversion counts if sunk within (ship_size + 3) turns from first hit.
                    deadline = game.turn_count + ship_sizes[hit_ship_name] + 3
                    pending_deadlines[p][hit_ship_name] = deadline

            sunk_name = shot.get('sunk_ship_name')
            if sunk_name is not None and sunk_name in pending_deadlines[p]:
                if game.turn_count <= pending_deadlines[p][sunk_name]:
                    quick_conversions[p] += 1
                pending_deadlines[p].pop(sunk_name, None)
        turn += 1

    timed_out = (not game.is_over())
    s1 = game.get_stats(1)
    s2 = game.get_stats(2)
    s1['timed_out'] = timed_out
    s2['timed_out'] = timed_out

    for player, stats in ((1, s1), (2, s2)):
        tracker = game.boards[player].shot_tracker
        dangling_hits = int(np.sum(tracker == int(ShotState.HIT)))
        stats['find_events'] = find_events[player]
        stats['quick_conversions'] = quick_conversions[player]
        stats['dangling_hits'] = dangling_hits
        stats['tactical_decisions'] = tactical_decisions[player]
        stats['tactical_followups'] = tactical_followups[player]
        stats['tactical_ignores'] = tactical_ignores[player]
        stats['game_pace'] = 1.0 - (min(stats['turns'], max_turns) / max(max_turns, 1))

    return s1, s2


class _RandomBaseline:
    def place_all_ships(self, board: Board, rng: np.random.Generator | None = None) -> bool:
        return random_place_all_ships(board, rng)

    def choose_shot(self, ai_state: dict) -> tuple[int, int]:
        tracker = ai_state['shot_tracker']
        rows, cols = np.where(tracker == int(ShotState.UNKNOWN))
        idx = int(np.random.randint(0, len(rows)))
        return int(rows[idx]), int(cols[idx])


class _HuntTargetBaseline:
    def place_all_ships(self, board: Board, rng: np.random.Generator | None = None) -> bool:
        return random_place_all_ships(board, rng)

    def choose_shot(self, ai_state: dict) -> tuple[int, int]:
        tracker = ai_state['shot_tracker']
        hits = np.argwhere(tracker == int(ShotState.HIT))

        # Hunt around known hits first
        for r, c in hits:
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                rr, cc = int(r + dr), int(c + dc)
                if 0 <= rr < BOARD_SIZE and 0 <= cc < BOARD_SIZE:
                    if tracker[rr, cc] == int(ShotState.UNKNOWN):
                        return rr, cc

        # Otherwise use checkerboard search pattern, then fallback to random unknown.
        unknown = np.argwhere(tracker == int(ShotState.UNKNOWN))
        checker = [(int(r), int(c)) for r, c in unknown if (int(r) + int(c)) % 2 == 0]
        if checker:
            return checker[int(np.random.randint(0, len(checker)))]
        idx = int(np.random.randint(0, len(unknown)))
        return int(unknown[idx, 0]), int(unknown[idx, 1])


def _simulate_game_generic(
    player_1,
    player_2,
    rng: np.random.Generator,
    max_turns: int,
) -> tuple[dict, dict]:
    """Play one game between any two objects implementing place_all_ships and choose_shot."""
    game = Game()
    ship_sizes = {name: size for name, size in SHIP_DEFINITIONS}

    discovered: dict[int, set[str]] = {1: set(), 2: set()}
    pending_deadlines: dict[int, dict[str, int]] = {1: {}, 2: {}}
    find_events: dict[int, int] = {1: 0, 2: 0}
    quick_conversions: dict[int, int] = {1: 0, 2: 0}
    tactical_decisions: dict[int, int] = {1: 0, 2: 0}
    tactical_followups: dict[int, int] = {1: 0, 2: 0}
    tactical_ignores: dict[int, int] = {1: 0, 2: 0}

    def _ship_name_at(board: Board, row: int, col: int) -> str | None:
        for ship in board.ships:
            if (row, col) in ship.positions:
                return ship.name
        return None
    player_1.place_all_ships(game.boards[1], rng)
    player_2.place_all_ships(game.boards[2], rng)
    game.phase = GamePhase.BATTLE

    turn = 0
    while not game.is_over() and turn < max_turns:
        p = game.current_turn
        player = player_1 if p == 1 else player_2
        state = game.get_ai_state(p)
        row, col = player.choose_shot(state)

        unresolved_hits = np.argwhere(state['shot_tracker'] == int(ShotState.HIT))
        if len(unresolved_hits) > 0:
            tactical_decisions[p] += 1
            is_adjacent = False
            for hr, hc in unresolved_hits:
                if abs(int(hr) - row) + abs(int(hc) - col) == 1:
                    is_adjacent = True
                    break
            if is_adjacent:
                tactical_followups[p] += 1
            else:
                tactical_ignores[p] += 1

        opponent = 3 - p
        opponent_board = game.boards[opponent]
        shot = game.fire(p, row, col)

        if shot.get('success'):
            hit_ship_name = _ship_name_at(opponent_board, row, col)
            if shot['result'] == 'hit' and hit_ship_name is not None:
                if hit_ship_name not in discovered[p]:
                    discovered[p].add(hit_ship_name)
                    find_events[p] += 1
                    deadline = game.turn_count + ship_sizes[hit_ship_name] + 3
                    pending_deadlines[p][hit_ship_name] = deadline

            sunk_name = shot.get('sunk_ship_name')
            if sunk_name is not None and sunk_name in pending_deadlines[p]:
                if game.turn_count <= pending_deadlines[p][sunk_name]:
                    quick_conversions[p] += 1
                pending_deadlines[p].pop(sunk_name, None)
        turn += 1

    timed_out = (not game.is_over())
    s1 = game.get_stats(1)
    s2 = game.get_stats(2)
    s1['timed_out'] = timed_out
    s2['timed_out'] = timed_out

    for player, stats in ((1, s1), (2, s2)):
        tracker = game.boards[player].shot_tracker
        dangling_hits = int(np.sum(tracker == int(ShotState.HIT)))
        stats['find_events'] = find_events[player]
        stats['quick_conversions'] = quick_conversions[player]
        stats['dangling_hits'] = dangling_hits
        stats['tactical_decisions'] = tactical_decisions[player]
        stats['tactical_followups'] = tactical_followups[player]
        stats['tactical_ignores'] = tactical_ignores[player]
        stats['game_pace'] = 1.0 - (min(stats['turns'], max_turns) / max(max_turns, 1))

    return s1, s2


def _opponent_mix_for_generation(generation: int) -> dict[str, float]:
    if generation <= config.CURRICULUM_RANDOM_END_GEN:
        return {
            'random': config.RANDOM_OPPONENT_WEIGHT_EARLY,
            'peer': config.PEER_OPPONENT_WEIGHT_EARLY,
            'hof': config.HOF_OPPONENT_WEIGHT_EARLY,
        }
    if generation <= config.CURRICULUM_MIX_END_GEN:
        return {
            'random': config.RANDOM_OPPONENT_WEIGHT_MID,
            'peer': config.PEER_OPPONENT_WEIGHT_MID,
            'hof': config.HOF_OPPONENT_WEIGHT_MID,
        }
    return {
        'random': config.RANDOM_OPPONENT_WEIGHT_LATE,
        'peer': config.PEER_OPPONENT_WEIGHT_LATE,
        'hof': config.HOF_OPPONENT_WEIGHT_LATE,
    }


def _sample_opponent_mode(
    generation: int,
    hall_of_fame: list[Agent],
    rng: np.random.Generator,
) -> str:
    mix = _opponent_mix_for_generation(generation)
    modes = ['random', 'peer', 'hof']
    probs = np.array([mix[m] for m in modes], dtype=np.float64)

    # If hall-of-fame is empty, redistribute its probability to peers.
    if not hall_of_fame:
        probs[2] = 0.0
        probs[1] += mix['hof']

    probs = probs / probs.sum()
    return modes[int(rng.choice(len(modes), p=probs))]


def _mutation_schedule(generation: int, total_generations: int) -> tuple[float, float]:
    """Anneal mutation parameters from initial values toward end values."""
    if total_generations <= 1:
        return config.MUTATION_RATE, config.MUTATION_STRENGTH

    t = (generation - 1) / (total_generations - 1)
    t = t ** config.MUTATION_ANNEAL_POWER

    rate = config.MUTATION_RATE + (config.MUTATION_RATE_END - config.MUTATION_RATE) * t
    strength = config.MUTATION_STRENGTH + (config.MUTATION_STRENGTH_END - config.MUTATION_STRENGTH) * t
    return float(rate), float(strength)


def _clone_agent(agent: Agent) -> Agent:
    cloned = Agent()
    cloned.genome = agent.genome.copy()
    cloned.fitness = agent.fitness
    return cloned


# ---------------------------------------------------------------------------
# Batch evaluation of the full population
# ---------------------------------------------------------------------------

def evaluate_population(
    population: list[Agent],
    rng:        np.random.Generator,
    generation: int,
    hall_of_fame: list[Agent],
    games_per_eval: int,
    tactical_baseline_games: int,
    max_turns: int,
) -> list[list[dict]]:
    """
    Play GAMES_PER_EVAL games for every agent in the population and assign
    agent.fitness.

    Curriculum + diversity matchmaking:
      - random baseline opponents early
      - mixed peers + hall-of-fame in mid generations
      - mostly peers + hall-of-fame later
    """
    n = len(population)
    random_baseline = _RandomBaseline()
    hunt_baseline = _HuntTargetBaseline()

    # Accumulate stats per agent
    all_stats: list[list[dict]] = [[] for _ in range(n)]

    for _round in range(games_per_eval):
        mode = _sample_opponent_mode(generation, hall_of_fame, rng)

        if mode == 'peer':
            order = rng.permutation(n)
            for i in range(0, n - 1, 2):
                a = int(order[i])
                b = int(order[i + 1])
                s_a, s_b = _simulate_game(population[a], population[b], rng, max_turns=max_turns)
                all_stats[a].append(s_a)
                all_stats[b].append(s_b)

            # Odd population fallback: one agent plays random baseline.
            if n % 2 == 1:
                odd = int(order[-1])
                if rng.random() < 0.5:
                    s_agent, _ = _simulate_game_generic(population[odd], random_baseline, rng, max_turns=max_turns)
                else:
                    _, s_agent = _simulate_game_generic(random_baseline, population[odd], rng, max_turns=max_turns)
                all_stats[odd].append(s_agent)

        elif mode == 'hof':
            for idx, agent in enumerate(population):
                opp = hall_of_fame[int(rng.integers(0, len(hall_of_fame)))]
                if rng.random() < 0.5:
                    s_agent, _ = _simulate_game(agent, opp, rng, max_turns=max_turns)
                else:
                    _, s_agent = _simulate_game(opp, agent, rng, max_turns=max_turns)
                all_stats[idx].append(s_agent)

        else:  # random
            for idx, agent in enumerate(population):
                if rng.random() < 0.5:
                    s_agent, _ = _simulate_game_generic(agent, random_baseline, rng, max_turns=max_turns)
                else:
                    _, s_agent = _simulate_game_generic(random_baseline, agent, rng, max_turns=max_turns)
                all_stats[idx].append(s_agent)

    # Directly include matches against a tactical baseline in selection fitness
    # so target-mode behavior is optimized, not just observed in benchmarks.
    for _round in range(tactical_baseline_games):
        for idx, agent in enumerate(population):
            if rng.random() < 0.5:
                s_agent, _ = _simulate_game_generic(agent, hunt_baseline, rng, max_turns=max_turns)
            else:
                _, s_agent = _simulate_game_generic(hunt_baseline, agent, rng, max_turns=max_turns)
            all_stats[idx].append(s_agent)

    for agent, stats in zip(population, all_stats):
        agent.fitness = compute_fitness(stats) if stats else 0.0

    # Return full stats so trainer can log richer summaries if needed.
    return all_stats


def _evaluate_against_baseline(
    candidate: Agent,
    baseline,
    games: int,
    rng: np.random.Generator,
    max_turns: int,
) -> dict:
    """Run symmetric benchmark matches and return win-rate and score stats."""
    stats: list[dict] = []
    wins = 0

    for _ in range(games):
        if rng.random() < 0.5:
            s_c, _ = _simulate_game_generic(candidate, baseline, rng, max_turns=max_turns)
        else:
            _, s_c = _simulate_game_generic(baseline, candidate, rng, max_turns=max_turns)
        stats.append(s_c)
        if s_c['won']:
            wins += 1

    summary = fitness_summary(stats)
    summary['win_rate'] = round(wins / max(games, 1), 4)
    return summary


def _run_benchmarks(
    candidate: Agent,
    generation: int,
    rng: np.random.Generator,
    benchmark_every: int,
    benchmark_games_per_opponent: int,
    max_turns: int,
) -> dict:
    if generation % benchmark_every != 0:
        return {}

    random_baseline = _RandomBaseline()
    hunt_baseline = _HuntTargetBaseline()
    games = benchmark_games_per_opponent

    random_result = _evaluate_against_baseline(candidate, random_baseline, games, rng, max_turns=max_turns)
    hunt_result = _evaluate_against_baseline(candidate, hunt_baseline, games, rng, max_turns=max_turns)

    return {
        'random': random_result,
        'hunt_target': hunt_result,
    }


def _make_progress_tracker() -> dict:
    """State container for tracking benchmark trend across generations."""
    return {
        'last_score': None,
        'ema_score': None,
        'best_score': float('-inf'),
        'benchmarks_since_best': 0,
        'flat_streak': 0,
    }


def _update_progress_tracker(tracker: dict, benchmark: dict) -> dict | None:
    """
    Convert baseline benchmark results into a single trend signal.

    Score weights:
      - 40% random baseline win-rate
      - 60% hunt-target baseline win-rate (harder opponent)
    """
    if not benchmark:
        return None

    r_win = float(benchmark['random']['win_rate'])
    h_win = float(benchmark['hunt_target']['win_rate'])
    score = 0.4 * r_win + 0.6 * h_win

    prev_score = tracker['last_score']
    prev_ema = tracker['ema_score']
    delta_prev = None if prev_score is None else score - prev_score

    ema_alpha = 0.35
    ema_score = score if prev_ema is None else (ema_alpha * score + (1.0 - ema_alpha) * prev_ema)
    delta_vs_ema = None if prev_ema is None else score - prev_ema

    flat_epsilon = 0.01
    if delta_prev is not None and abs(delta_prev) < flat_epsilon:
        tracker['flat_streak'] += 1
    else:
        tracker['flat_streak'] = 0

    best_before = tracker['best_score']
    is_new_best = score > best_before
    if is_new_best:
        tracker['best_score'] = score
        tracker['benchmarks_since_best'] = 0
    else:
        tracker['benchmarks_since_best'] += 1

    tracker['last_score'] = score
    tracker['ema_score'] = ema_score

    if delta_prev is None:
        trend = 'baseline'
    elif delta_prev > flat_epsilon:
        trend = 'up'
    elif delta_prev < -flat_epsilon:
        trend = 'down'
    else:
        trend = 'flat'

    return {
        'score': score,
        'delta_prev': delta_prev,
        'delta_vs_ema': delta_vs_ema,
        'ema_score': ema_score,
        'best_score': tracker['best_score'],
        'is_new_best': is_new_best,
        'benchmarks_since_best': tracker['benchmarks_since_best'],
        'flat_streak': tracker['flat_streak'],
        'trend': trend,
    }


def _fmt_signed(value: float | None) -> str:
    return 'n/a' if value is None else f'{value:+.3f}'


def _evaluate_against_checkpoint(
    champion: Agent,
    previous_checkpoint: Agent,
    games: int,
    rng: np.random.Generator,
    max_turns: int,
) -> dict:
    """Run symmetric head-to-head games vs the latest earlier checkpoint agent."""
    wins = 0
    losses = 0
    ties = 0

    for _ in range(games):
        if rng.random() < 0.5:
            s_c, _ = _simulate_game(champion, previous_checkpoint, rng, max_turns=max_turns)
        else:
            _, s_c = _simulate_game(previous_checkpoint, champion, rng, max_turns=max_turns)

        if s_c.get('timed_out', False):
            ties += 1
        elif s_c['won']:
            wins += 1
        else:
            losses += 1

    denom = max(games, 1)
    return {
        'games': games,
        'wins': wins,
        'losses': losses,
        'ties': ties,
        'win_rate': round(wins / denom, 4),
        'loss_rate': round(losses / denom, 4),
        'tie_rate': round(ties / denom, 4),
    }


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _save_checkpoint(agent: Agent, generation: int) -> None:
    path = os.path.join(config.CHECKPOINT_DIR, f'gen_{generation:04d}')
    agent.save(path)
    print(f'  [checkpoint] saved → {path}')


def _log_generation(
    gen: int,
    pop: list[Agent],
    elapsed: float,
    mutation_rate: float,
    mutation_strength: float,
    benchmark: dict,
    progress: dict | None,
    checkpoint_compare: dict | None,
) -> None:
    stats = population_stats(pop)
    print(
        f'Gen {gen:4d} | '
        f'fitness min={stats["min"]:.4f}  mean={stats["mean"]:.4f}  max={stats["max"]:.4f} | '
        f'mut(rate={mutation_rate:.4f}, std={mutation_strength:.4f}) | '
        f'{elapsed:.1f}s'
    )
    if benchmark:
        r = benchmark['random']
        h = benchmark['hunt_target']
        print(
            f'           benchmark random win={r["win_rate"]:.3f} fit={r["fitness"]:.3f} | '
            f'hunt-target win={h["win_rate"]:.3f} fit={h["fitness"]:.3f}'
        )
        if progress:
            print(
                f'           progress score={progress["score"]:.3f} trend={progress["trend"]} '
                f'd_prev={_fmt_signed(progress["delta_prev"])} '
                f'd_ema={_fmt_signed(progress["delta_vs_ema"])} '
                f'best={progress["best_score"]:.3f} '
                f'flat_streak={progress["flat_streak"]} '
                f'since_best={progress["benchmarks_since_best"]}'
            )
    if checkpoint_compare:
        ckpt_gen = checkpoint_compare['checkpoint_gen']
        ckpt_tag = f'gen_{ckpt_gen:04d}' if isinstance(ckpt_gen, int) else 'resume'
        print(
            f'           vs {ckpt_tag} win={checkpoint_compare["win_rate"]:.3f} '
            f'loss={checkpoint_compare["loss_rate"]:.3f} '
            f'tie={checkpoint_compare["tie_rate"]:.3f} '
            f'(W/L/T={checkpoint_compare["wins"]}/{checkpoint_compare["losses"]}/{checkpoint_compare["ties"]}, '
            f'n={checkpoint_compare["games"]})'
        )


# ---------------------------------------------------------------------------
# Main training loop
# ---------------------------------------------------------------------------

def train(
    num_generations: int = config.NUM_GENERATIONS,
    population_size: int = config.POPULATION_SIZE,
    seed:            int = 0,
    resume_path:     str | None = None,
    fast_mode:       bool | None = None,
) -> Agent:
    """
    Run the neuroevolution training loop.

    Args:
        num_generations: How many generations to run.
        population_size: Number of agents per generation.
        seed:            Random seed for reproducibility.
        resume_path:     Optional path to a saved agent to seed the initial
                         population (e.g. 'AI/checkpoints/gen_0050').
                         All agents will be initialised around this genome.

    Returns:
        The best agent from the final generation.
    """
    rng = np.random.default_rng(seed)

    if fast_mode is None:
        fast_mode = config.FAST_MODE

    effective_population_size = (
        min(population_size, config.FAST_POPULATION_SIZE) if fast_mode else population_size
    )
    effective_games_per_eval = (
        min(config.GAMES_PER_EVAL, config.FAST_GAMES_PER_EVAL) if fast_mode else config.GAMES_PER_EVAL
    )
    effective_benchmark_every = (
        max(config.BENCHMARK_EVERY, config.FAST_BENCHMARK_EVERY)
        if fast_mode else config.BENCHMARK_EVERY
    )
    effective_benchmark_games = (
        min(config.BENCHMARK_GAMES_PER_OPPONENT, config.FAST_BENCHMARK_GAMES_PER_OPPONENT)
        if fast_mode else config.BENCHMARK_GAMES_PER_OPPONENT
    )
    effective_hof_size = (
        min(config.HALL_OF_FAME_SIZE, config.FAST_HALL_OF_FAME_SIZE)
        if fast_mode else config.HALL_OF_FAME_SIZE
    )
    effective_tactical_baseline_games = (
        min(config.TACTICAL_BASELINE_GAMES_PER_EVAL, config.FAST_TACTICAL_BASELINE_GAMES_PER_EVAL)
        if fast_mode else config.TACTICAL_BASELINE_GAMES_PER_EVAL
    )
    effective_checkpoint_compare_games = (
        min(config.CHECKPOINT_COMPARE_GAMES, config.FAST_CHECKPOINT_COMPARE_GAMES)
        if fast_mode else config.CHECKPOINT_COMPARE_GAMES
    )
    effective_max_turns = config.MAX_TURNS_PER_GAME

    # --- backend / device info ---
    backend = backend_name()
    gpus = list_available_gpus()
    if gpus:
        print(f'[trainer] Backend: {backend} | GPU(s): {gpus}')
    else:
        print(f'[trainer] Backend: {backend} | No GPU detected — running on CPU.')
    if fast_mode:
        print(
            '[trainer] Fast mode enabled: '
            f'population={effective_population_size}, games/eval={effective_games_per_eval}, '
            f'tactical_baseline_games={effective_tactical_baseline_games}, '
            f'benchmark_every={effective_benchmark_every}, benchmark_games={effective_benchmark_games}, '
            f'checkpoint_compare_games={effective_checkpoint_compare_games}'
        )

    # --- initialise population ---
    print(f'[trainer] Initialising population of {effective_population_size} agents...')
    population = create_population(effective_population_size)
    hall_of_fame: list[Agent] = []

    if resume_path:
        seed_agent = Agent.load(resume_path)
        seed_genome = seed_agent.genome
        print(f'[trainer] Resuming from {resume_path}. Seeding population with saved genome.')
        for agent in population:
            # Slightly mutate the seed genome for each member
            from AI.genetic import mutate
            agent.genome = mutate(seed_genome, rng, rate=0.2, strength=0.05)

    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)

    # --- main loop ---
    progress_tracker = _make_progress_tracker()
    latest_checkpoint_agent: Agent | None = None
    latest_checkpoint_gen: int | None = None

    # If resuming from a checkpoint, use it as the first comparison baseline.
    if resume_path:
        latest_checkpoint_agent = Agent.load(resume_path)
        base = os.path.basename(resume_path)
        if base.startswith('gen_'):
            try:
                latest_checkpoint_gen = int(base.split('_')[1])
            except Exception:
                latest_checkpoint_gen = None

    for gen in range(1, num_generations + 1):
        t_start = time.time()
        mutation_rate, mutation_strength = _mutation_schedule(gen, num_generations)

        evaluate_population(
            population,
            rng,
            generation=gen,
            hall_of_fame=hall_of_fame,
            games_per_eval=effective_games_per_eval,
            tactical_baseline_games=effective_tactical_baseline_games,
            max_turns=effective_max_turns,
        )

        champion = best_agent(population)
        benchmark = _run_benchmarks(
            champion,
            gen,
            rng,
            benchmark_every=effective_benchmark_every,
            benchmark_games_per_opponent=effective_benchmark_games,
            max_turns=effective_max_turns,
        )
        progress = _update_progress_tracker(progress_tracker, benchmark)

        checkpoint_compare = None
        if (
            config.CHECKPOINT_COMPARE_ENABLED
            and latest_checkpoint_agent is not None
            and latest_checkpoint_gen is not None
            and latest_checkpoint_gen < gen
        ):
            checkpoint_compare = _evaluate_against_checkpoint(
                champion,
                latest_checkpoint_agent,
                games=effective_checkpoint_compare_games,
                rng=rng,
                max_turns=effective_max_turns,
            )
            checkpoint_compare['checkpoint_gen'] = latest_checkpoint_gen

        elapsed = time.time() - t_start

        if gen % config.LOG_EVERY == 0:
            _log_generation(
                gen,
                population,
                elapsed,
                mutation_rate=mutation_rate,
                mutation_strength=mutation_strength,
                benchmark=benchmark,
                progress=progress,
                checkpoint_compare=checkpoint_compare,
            )

        if gen % config.HALL_OF_FAME_ADD_EVERY == 0:
            hall_of_fame.append(_clone_agent(champion))
            if len(hall_of_fame) > effective_hof_size:
                hall_of_fame.pop(0)

        if gen % config.CHECKPOINT_EVERY == 0:
            _save_checkpoint(champion, gen)
            latest_checkpoint_agent = _clone_agent(champion)
            latest_checkpoint_gen = gen

        if gen < num_generations:
            population = next_generation(
                population,
                rng,
                mutation_rate=mutation_rate,
                mutation_strength=mutation_strength,
            )

    champion = best_agent(population)

    # Save final model
    champion.save(config.FINAL_MODEL_PATH)
    print(f'\n[trainer] Training complete. Final model saved to {config.FINAL_MODEL_PATH}')
    print(f'[trainer] Best fitness: {champion.fitness:.4f}')

    return champion


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Train the Battleship AI.')
    parser.add_argument('--generations', type=int, default=config.NUM_GENERATIONS,
                        help='Number of generations to train.')
    parser.add_argument('--population',  type=int, default=config.POPULATION_SIZE,
                        help='Population size.')
    parser.add_argument('--seed',        type=int, default=0,
                        help='Random seed.')
    parser.add_argument('--resume',      type=str, default=None,
                        help='Path to a saved checkpoint to resume from.')
    parser.add_argument('--fast', action='store_true',
                        help='Use fast-mode profile from config for faster iteration.')
    args = parser.parse_args()

    train(
        num_generations = args.generations,
        population_size = args.population,
        seed            = args.seed,
        resume_path     = args.resume,
        fast_mode       = True if args.fast else None,
    )
