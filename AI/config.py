"""
Training & Model Configuration
================================
All hyperparameters for the genetic algorithm and neural networks live here.
Adjust these values to tune training behaviour without touching other files.

GPU note:
    TensorFlow will use your AMD integrated GPU on Windows automatically
    when the DirectML plugin is installed:
        pip install tensorflow tensorflow-directml-plugin
    After install, TF will log "DirectML device ..." at startup.
    To force CPU only (e.g. for debugging), set FORCE_CPU = True.
"""

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

FORCE_CPU: bool = False
"""Set True to disable GPU and run on CPU only."""

FAST_MODE: bool = True
"""If True, use a lower-cost training profile for faster iteration."""

FAST_POPULATION_SIZE: int = 40
FAST_GAMES_PER_EVAL: int = 10
FAST_BENCHMARK_EVERY: int = 10
FAST_BENCHMARK_GAMES_PER_OPPONENT: int = 6
FAST_HALL_OF_FAME_SIZE: int = 6

# ---------------------------------------------------------------------------
# Board / game constants (mirrored here for convenience)
# ---------------------------------------------------------------------------

BOARD_SIZE:    int = 10
NUM_SHIPS:     int = 5
NUM_CELLS:     int = BOARD_SIZE * BOARD_SIZE  # 100

# ---------------------------------------------------------------------------
# Neural network architecture
# ---------------------------------------------------------------------------

# --- Targeting network (used during the battle phase) ---
# Input : shot_tracker (100) + enemy_sunk flags (5) + own_ships_alive flags (5) = 110
# Output: score for each of the 100 cells (argmax of unseen cells is chosen)
TARGETING_INPUT_SIZE:   int       = NUM_CELLS + NUM_SHIPS + NUM_SHIPS  # 110
TARGETING_HIDDEN_SIZES: list[int] = [96, 64]
TARGETING_OUTPUT_SIZE:  int       = NUM_CELLS  # 100

# --- Placement network (used during the placement phase) ---
# Input : fixed noise vector (gives the network a random seed to vary placements)
# Output: 200 values — first 100 are H-orientation preferences per cell,
#         next 100 are V-orientation preferences per cell.
#         Ships are placed greedily (largest first) using these preference maps.
PLACEMENT_NOISE_SIZE:   int       = 20
PLACEMENT_HIDDEN_SIZES: list[int] = [64, 32]
PLACEMENT_OUTPUT_SIZE:  int       = NUM_CELLS * 2  # 200

ACTIVATION: str = 'relu'

# ---------------------------------------------------------------------------
# Genetic algorithm
# ---------------------------------------------------------------------------

POPULATION_SIZE:      int   = 100
"""Number of AI agents per generation."""

ELITE_FRACTION:       float = 0.15
"""Top fraction kept unchanged as elites into the next generation."""

TOURNAMENT_SIZE:      int   = 9
"""Number of candidates drawn per tournament-selection event."""

CROSSOVER_RATE:       float = 0.70
"""Probability that two parents produce a crossed-over child (vs direct copy)."""

MUTATION_RATE:        float = 0.15
"""Initial probability that any individual weight is mutated."""

MUTATION_STRENGTH:    float = 0.15
"""Initial standard deviation of Gaussian noise added during mutation."""

MUTATION_RATE_END:     float = 0.03
"""Final mutation rate after annealing completes."""

MUTATION_STRENGTH_END: float = 0.04
"""Final mutation strength after annealing completes."""

MUTATION_ANNEAL_POWER: float = 1.0
"""Annealing curve exponent. 1.0 = linear, >1 slows early decay."""

NUM_GENERATIONS:      int   = 200
"""Total generations to train."""

GAMES_PER_EVAL:       int   = 30
"""
Number of games each agent plays per generation to estimate fitness.
Higher = more accurate fitness estimate, slower generation.
"""

MAX_TURNS_PER_GAME:   int   = 200
"""Safety cap on game length to prevent infinite loops during training."""

# ---------------------------------------------------------------------------
# Curriculum learning and opponent diversity
# ---------------------------------------------------------------------------

CURRICULUM_RANDOM_END_GEN: int = 40
"""Early stage end generation: mostly train against random opponents."""

CURRICULUM_MIX_END_GEN: int = 120
"""Middle stage end generation: mixed random/peer/hall-of-fame opponents."""

RANDOM_OPPONENT_WEIGHT_EARLY: float = 0.70
PEER_OPPONENT_WEIGHT_EARLY:   float = 0.30
HOF_OPPONENT_WEIGHT_EARLY:    float = 0.00

RANDOM_OPPONENT_WEIGHT_MID: float = 0.25
PEER_OPPONENT_WEIGHT_MID:   float = 0.55
HOF_OPPONENT_WEIGHT_MID:    float = 0.20

RANDOM_OPPONENT_WEIGHT_LATE: float = 0.05
PEER_OPPONENT_WEIGHT_LATE:   float = 0.65
HOF_OPPONENT_WEIGHT_LATE:    float = 0.30

HALL_OF_FAME_SIZE: int = 12
"""Maximum number of elite historical agents kept for opponent diversity."""

HALL_OF_FAME_ADD_EVERY: int = 1
"""Add the current generation champion every N generations."""

# ---------------------------------------------------------------------------
# Fitness weights
# ---------------------------------------------------------------------------
# Composite fitness = w_win * win_rate
#                   + w_hit * hit_ratio
#                   - w_hit_taken * hit_taken_ratio
#
# All components are normalised to [0, 1] before weighting.

FITNESS_WEIGHT_WIN:       float = 0.50
FITNESS_WEIGHT_HIT_RATIO: float = 0.30
FITNESS_WEIGHT_HIT_TAKEN: float = 0.20  # subtracted (lower times-hit = better)

FITNESS_WEIGHT_EFFICIENCY: float = 0.10
"""Reward for winning quickly (lower turns when you win)."""

FITNESS_TIE_PENALTY: float = 0.15
"""Penalty applied to games that hit MAX_TURNS_PER_GAME without a winner."""

# ---------------------------------------------------------------------------
# External benchmark tracking
# ---------------------------------------------------------------------------

BENCHMARK_EVERY: int = 1
"""Run benchmark matches every N generations."""

BENCHMARK_GAMES_PER_OPPONENT: int =30
"""Number of benchmark games versus each baseline opponent."""

CHECKPOINT_COMPARE_ENABLED: bool = True
"""If True, compare current champion to latest earlier checkpoint each generation."""

CHECKPOINT_COMPARE_GAMES: int = 20
"""Head-to-head games for champion vs latest checkpoint comparison."""

FAST_CHECKPOINT_COMPARE_GAMES: int = 8
"""Fast-mode cap for checkpoint comparison games."""

# ---------------------------------------------------------------------------
# Training I/O
# ---------------------------------------------------------------------------

CHECKPOINT_DIR:  str = 'AI/checkpoints'
"""Directory where generation checkpoints are saved."""

CHECKPOINT_EVERY: int = 10
"""Save a checkpoint every N generations."""

FINAL_MODEL_PATH: str = 'AI/checkpoints/final_model'
"""Path (no extension) for the final trained model weights."""

LOG_EVERY: int = 1
"""Print a progress summary every N generations."""
