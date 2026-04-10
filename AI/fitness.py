"""
Fitness Function
=================
Computes a scalar fitness score for one agent based on multiple games.

Fitness components (all normalised to [0, 1]):
  1. Win rate          — fraction of games won            (weight: FITNESS_WEIGHT_WIN)
  2. Hit ratio         — hits / shots_fired               (weight: FITNESS_WEIGHT_HIT_RATIO)
  3. Hit-taken ratio   — times_hit / total_enemy_shots    (weight: FITNESS_WEIGHT_HIT_TAKEN, subtracted)

Composite:
    fitness = w_win * win_rate
            + w_hit * hit_ratio
            - w_hit_taken * hit_taken_ratio

All three components are bounded to [0, 1], so fitness ∈ [-w_hit_taken, w_win + w_hit].
With default weights (0.5, 0.3, 0.2) fitness ∈ [-0.2, 0.8].
"""

from AI import config


def compute_fitness(game_stats: list[dict]) -> float:
    """
    Compute a composite fitness score from a list of per-game stats dicts.
    Each dict is the output of Game.get_stats(player) for this agent:
        won:          bool
        shots_fired:  int
        hits_made:    int
        times_hit:    int
        ships_sunk:   int
        turns:        int
        timed_out:    bool

    Returns a single float. Higher = better agent.
    """
    if not game_stats:
        return 0.0

    games         = len(game_stats)
    wins          = sum(1 for s in game_stats if s['won'])
    timed_outs    = sum(1 for s in game_stats if s.get('timed_out', False))
    total_shots   = sum(s['shots_fired'] for s in game_stats)
    total_hits    = sum(s['hits_made']   for s in game_stats)
    total_hit_by  = sum(s['times_hit']   for s in game_stats)

    win_rate     = wins / games
    hit_ratio    = total_hits  / max(total_shots, 1)
    # Normalise hit-taken: max possible hits taken is 17 per game (all ship cells)
    max_hit_taken = 17 * games
    hit_taken_ratio = total_hit_by / max_hit_taken

    # Reward faster wins: 1.0 for immediate win, ~0 if win occurs at turn cap.
    win_turn_efficiency = 0.0
    if wins > 0:
        winning_turns = [s['turns'] for s in game_stats if s['won']]
        win_turn_efficiency = sum(
            1.0 - min(t, config.MAX_TURNS_PER_GAME) / config.MAX_TURNS_PER_GAME
            for t in winning_turns
        ) / wins

    tie_ratio = timed_outs / games

    fitness = (
          config.FITNESS_WEIGHT_WIN       * win_rate
        + config.FITNESS_WEIGHT_HIT_RATIO * hit_ratio
        - config.FITNESS_WEIGHT_HIT_TAKEN * hit_taken_ratio
        + config.FITNESS_WEIGHT_EFFICIENCY * win_turn_efficiency
        - config.FITNESS_TIE_PENALTY * tie_ratio
    )
    return float(fitness)


def fitness_summary(game_stats: list[dict]) -> dict:
    """
    Returns a human-readable breakdown of fitness components.
    Useful for terminal training logs.
    """
    if not game_stats:
        return {'fitness': 0.0, 'win_rate': 0.0, 'hit_ratio': 0.0, 'hit_taken_ratio': 0.0}

    games        = len(game_stats)
    wins         = sum(1 for s in game_stats if s['won'])
    timed_outs   = sum(1 for s in game_stats if s.get('timed_out', False))
    total_shots  = sum(s['shots_fired'] for s in game_stats)
    total_hits   = sum(s['hits_made']   for s in game_stats)
    total_hit_by = sum(s['times_hit']   for s in game_stats)

    win_rate        = wins / games
    hit_ratio       = total_hits / max(total_shots, 1)
    hit_taken_ratio = total_hit_by / (17 * games)
    tie_ratio       = timed_outs / games

    win_turn_efficiency = 0.0
    if wins > 0:
        winning_turns = [s['turns'] for s in game_stats if s['won']]
        win_turn_efficiency = sum(
            1.0 - min(t, config.MAX_TURNS_PER_GAME) / config.MAX_TURNS_PER_GAME
            for t in winning_turns
        ) / wins

    fitness         = (
          config.FITNESS_WEIGHT_WIN       * win_rate
        + config.FITNESS_WEIGHT_HIT_RATIO * hit_ratio
        - config.FITNESS_WEIGHT_HIT_TAKEN * hit_taken_ratio
        + config.FITNESS_WEIGHT_EFFICIENCY * win_turn_efficiency
        - config.FITNESS_TIE_PENALTY * tie_ratio
    )
    return {
        'fitness':         round(fitness, 4),
        'win_rate':        round(win_rate, 4),
        'hit_ratio':       round(hit_ratio, 4),
        'hit_taken_ratio': round(hit_taken_ratio, 4),
        'win_efficiency':  round(win_turn_efficiency, 4),
        'tie_ratio':       round(tie_ratio, 4),
        'avg_turns':       round(sum(s['turns'] for s in game_stats) / games, 1),
    }
