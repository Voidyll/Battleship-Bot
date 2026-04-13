"""
Fitness Function
=================
Computes a scalar fitness score for one agent based on multiple games.

Fitness components (all normalised to [0, 1]):
    1. Win rate            — fraction of games won              (weight: FITNESS_WEIGHT_WIN)
    2. Sink rate           — ships_sunk / (5 * games)           (weight: FITNESS_WEIGHT_SINK_RATE)
    3. Conversion rate     — quick_conversions / find_events    (weight: FITNESS_WEIGHT_CONVERSION)
    4. Hit ratio           — hits / shots_fired                 (weight: FITNESS_WEIGHT_HIT_RATIO)
    5. Hit-taken ratio     — times_hit / max_possible_hits      (weight: FITNESS_WEIGHT_HIT_TAKEN, subtracted)
    6. Win efficiency      — faster wins score higher           (weight: FITNESS_WEIGHT_EFFICIENCY)
    7. Game pace           — shorter games score higher         (weight: FITNESS_WEIGHT_GAME_PACE)
    8. Tactical follow-up  — adjacent follow-up when hits exist (weight: FITNESS_WEIGHT_TACTICAL_FOLLOWUP)
    9. Tactical ignore     — non-adjacent shot when hits exist  (penalty: FITNESS_TACTICAL_IGNORE_PENALTY)
    10. Tie ratio          — timeout frequency                  (penalty: FITNESS_TIE_PENALTY)
    11. Dangling hit ratio — unresolved hit cells at game end   (penalty: FITNESS_DANGLING_HIT_PENALTY)

Composite:
        fitness = w_win * win_rate
            + w_sink * sink_rate
            + w_convert * conversion_rate
            + w_hit * hit_ratio
            + w_eff * win_turn_efficiency
            + w_pace * game_pace
            + w_follow * tactical_followup_rate
            - w_hit_taken * hit_taken_ratio
            - p_ignore * tactical_ignore_rate
            - p_tie * tie_ratio
            - p_dangling * dangling_hit_ratio

    Additional strategy metrics are sourced from trainer simulation stats:
        find_events:       times a previously unseen ship is first hit
        quick_conversions: sinks achieved within (ship_size + 3) turns of first hit
        dangling_hits:     remaining HIT cells that never reached SUNK by game end
        game_pace:         1 - turns / MAX_TURNS_PER_GAME
        tactical_followups / tactical_decisions: follow-up behavior under pressure
        tactical_ignores / tactical_decisions: ignored unresolved-hit situations
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
    total_sunk    = sum(s.get('ships_sunk', 0) for s in game_stats)
    total_find_events = sum(s.get('find_events', 0) for s in game_stats)
    total_quick_conversions = sum(s.get('quick_conversions', 0) for s in game_stats)
    total_dangling_hits = sum(s.get('dangling_hits', 0) for s in game_stats)
    total_game_pace = sum(s.get('game_pace', 0.0) for s in game_stats)
    total_tactical_decisions = sum(s.get('tactical_decisions', 0) for s in game_stats)
    total_tactical_followups = sum(s.get('tactical_followups', 0) for s in game_stats)
    total_tactical_ignores = sum(s.get('tactical_ignores', 0) for s in game_stats)

    win_rate     = wins / games
    hit_ratio    = total_hits  / max(total_shots, 1)
    sink_rate    = total_sunk / (5 * games)
    conversion_rate = total_quick_conversions / max(total_find_events, 1)
    # Normalise hit-taken: max possible hits taken is 17 per game (all ship cells)
    max_hit_taken = 17 * games
    hit_taken_ratio = total_hit_by / max_hit_taken
    # Normalise unresolved hits by max ship cells per game.
    dangling_hit_ratio = total_dangling_hits / max(17 * games, 1)
    tactical_followup_rate = total_tactical_followups / max(total_tactical_decisions, 1)
    tactical_ignore_rate = total_tactical_ignores / max(total_tactical_decisions, 1)

    # Reward faster wins: 1.0 for immediate win, ~0 if win occurs at turn cap.
    win_turn_efficiency = 0.0
    if wins > 0:
        winning_turns = [s['turns'] for s in game_stats if s['won']]
        win_turn_efficiency = sum(
            1.0 - min(t, config.MAX_TURNS_PER_GAME) / config.MAX_TURNS_PER_GAME
            for t in winning_turns
        ) / wins

    tie_ratio = timed_outs / games
    game_pace = total_game_pace / games

    fitness = (
          config.FITNESS_WEIGHT_WIN       * win_rate
        + config.FITNESS_WEIGHT_SINK_RATE * sink_rate
        + config.FITNESS_WEIGHT_CONVERSION * conversion_rate
        + config.FITNESS_WEIGHT_HIT_RATIO * hit_ratio
        - config.FITNESS_WEIGHT_HIT_TAKEN * hit_taken_ratio
        + config.FITNESS_WEIGHT_EFFICIENCY * win_turn_efficiency
        + config.FITNESS_WEIGHT_GAME_PACE * game_pace
        + config.FITNESS_WEIGHT_TACTICAL_FOLLOWUP * tactical_followup_rate
        - config.FITNESS_TACTICAL_IGNORE_PENALTY * tactical_ignore_rate
        - config.FITNESS_TIE_PENALTY * tie_ratio
        - config.FITNESS_DANGLING_HIT_PENALTY * dangling_hit_ratio
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
    total_sunk = sum(s.get('ships_sunk', 0) for s in game_stats)
    total_find_events = sum(s.get('find_events', 0) for s in game_stats)
    total_quick_conversions = sum(s.get('quick_conversions', 0) for s in game_stats)
    total_dangling_hits = sum(s.get('dangling_hits', 0) for s in game_stats)
    total_game_pace = sum(s.get('game_pace', 0.0) for s in game_stats)
    total_tactical_decisions = sum(s.get('tactical_decisions', 0) for s in game_stats)
    total_tactical_followups = sum(s.get('tactical_followups', 0) for s in game_stats)
    total_tactical_ignores = sum(s.get('tactical_ignores', 0) for s in game_stats)

    win_rate        = wins / games
    hit_ratio       = total_hits / max(total_shots, 1)
    sink_rate       = total_sunk / (5 * games)
    conversion_rate = total_quick_conversions / max(total_find_events, 1)
    hit_taken_ratio = total_hit_by / (17 * games)
    dangling_hit_ratio = total_dangling_hits / max(17 * games, 1)
    tactical_followup_rate = total_tactical_followups / max(total_tactical_decisions, 1)
    tactical_ignore_rate = total_tactical_ignores / max(total_tactical_decisions, 1)
    tie_ratio       = timed_outs / games
    game_pace       = total_game_pace / games

    win_turn_efficiency = 0.0
    if wins > 0:
        winning_turns = [s['turns'] for s in game_stats if s['won']]
        win_turn_efficiency = sum(
            1.0 - min(t, config.MAX_TURNS_PER_GAME) / config.MAX_TURNS_PER_GAME
            for t in winning_turns
        ) / wins

    fitness         = (
          config.FITNESS_WEIGHT_WIN       * win_rate
        + config.FITNESS_WEIGHT_SINK_RATE * sink_rate
        + config.FITNESS_WEIGHT_CONVERSION * conversion_rate
        + config.FITNESS_WEIGHT_HIT_RATIO * hit_ratio
        - config.FITNESS_WEIGHT_HIT_TAKEN * hit_taken_ratio
        + config.FITNESS_WEIGHT_EFFICIENCY * win_turn_efficiency
        + config.FITNESS_WEIGHT_GAME_PACE * game_pace
        + config.FITNESS_WEIGHT_TACTICAL_FOLLOWUP * tactical_followup_rate
        - config.FITNESS_TACTICAL_IGNORE_PENALTY * tactical_ignore_rate
        - config.FITNESS_TIE_PENALTY * tie_ratio
        - config.FITNESS_DANGLING_HIT_PENALTY * dangling_hit_ratio
    )
    return {
        'fitness':         round(fitness, 4),
        'win_rate':        round(win_rate, 4),
        'sink_rate':       round(sink_rate, 4),
        'conversion_rate': round(conversion_rate, 4),
        'hit_ratio':       round(hit_ratio, 4),
        'hit_taken_ratio': round(hit_taken_ratio, 4),
        'dangling_hit_ratio': round(dangling_hit_ratio, 4),
        'tactical_followup_rate': round(tactical_followup_rate, 4),
        'tactical_ignore_rate': round(tactical_ignore_rate, 4),
        'win_efficiency':  round(win_turn_efficiency, 4),
        'game_pace':       round(game_pace, 4),
        'tie_ratio':       round(tie_ratio, 4),
        'avg_turns':       round(sum(s['turns'] for s in game_stats) / games, 1),
    }
