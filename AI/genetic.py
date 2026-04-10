"""
Genetic Algorithm
==================
Manages a population of Agent objects and evolves them over generations.

Evolution steps per generation:
  1. Evaluate — play GAMES_PER_EVAL games per agent, compute fitness
  2. Select    — tournament selection to pick parents
  3. Crossover — uniform crossover between two parent genomes
  4. Mutate    — add Gaussian noise to weights
  5. Elitism   — carry the top-N agents unchanged into the next generation

All genome operations work on flat numpy arrays (float32) for speed.
"""

import numpy as np

from AI.agent import Agent
from AI import config


# ---------------------------------------------------------------------------
# Population initialisation
# ---------------------------------------------------------------------------

def create_population(size: int = config.POPULATION_SIZE) -> list[Agent]:
    """
    Create a population of *size* agents with random initial weights.
    TensorFlow initialises Dense layers with Glorot uniform by default,
    so each agent starts with a sensible random genome.
    """
    return [Agent() for _ in range(size)]


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def tournament_select(
    population: list[Agent],
    rng:        np.random.Generator,
    k:          int = config.TOURNAMENT_SIZE,
) -> Agent:
    """
    Tournament selection: sample k agents, return the one with highest fitness.
    """
    k = max(1, min(k, len(population)))
    contestants = rng.choice(len(population), size=k, replace=False)  # type: ignore[arg-type]
    best_idx    = max(contestants, key=lambda i: population[i].fitness)
    return population[best_idx]


# ---------------------------------------------------------------------------
# Crossover
# ---------------------------------------------------------------------------

def uniform_crossover(
    parent_a: np.ndarray,
    parent_b: np.ndarray,
    rng:      np.random.Generator,
) -> np.ndarray:
    """
    Uniform crossover: each gene (weight) is independently drawn from
    parent_a or parent_b with equal probability.
    Returns a new child genome.
    """
    mask   = rng.random(len(parent_a)) < 0.5
    return np.where(mask, parent_a, parent_b).astype(np.float32)


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

def mutate(
    genome:   np.ndarray,
    rng:      np.random.Generator,
    rate:     float = config.MUTATION_RATE,
    strength: float = config.MUTATION_STRENGTH,
) -> np.ndarray:
    """
    Mutation: add Gaussian noise to each weight with probability *rate*.
    """
    genome    = genome.copy()
    mask      = rng.random(len(genome)) < rate
    noise     = rng.standard_normal(len(genome)).astype(np.float32) * strength
    genome[mask] += noise[mask]
    return genome


# ---------------------------------------------------------------------------
# One generation step
# ---------------------------------------------------------------------------

def next_generation(
    population: list[Agent],
    rng:        np.random.Generator,
    mutation_rate: float | None = None,
    mutation_strength: float | None = None,
) -> list[Agent]:
    """
    Produce the next generation from the current evaluated population.
    Assumes agent.fitness has already been set for every agent.

    Steps:
      1. Sort by fitness descending.
      2. Copy top ELITE_FRACTION directly into the new generation.
      3. Fill the rest via tournament selection + crossover + mutation.

    mutation_rate / mutation_strength:
      Optional overrides for annealed mutation schedules controlled by trainer.
    """
    if mutation_rate is None:
        mutation_rate = config.MUTATION_RATE
    if mutation_strength is None:
        mutation_strength = config.MUTATION_STRENGTH

    n       = len(population)
    n_elite = max(1, int(n * config.ELITE_FRACTION))

    sorted_pop = sorted(population, key=lambda a: a.fitness, reverse=True)
    new_pop: list[Agent] = []

    # --- elitism ---
    for agent in sorted_pop[:n_elite]:
        new_agent         = Agent()
        new_agent.genome  = agent.genome.copy()
        new_pop.append(new_agent)

    # --- offspring ---
    while len(new_pop) < n:
        parent_a = tournament_select(sorted_pop, rng)
        parent_b = tournament_select(sorted_pop, rng)

        if rng.random() < config.CROSSOVER_RATE:
            child_genome = uniform_crossover(parent_a.genome, parent_b.genome, rng)
        else:
            child_genome = parent_a.genome.copy()

        child_genome     = mutate(
            child_genome,
            rng,
            rate=mutation_rate,
            strength=mutation_strength,
        )
        child            = Agent()
        child.genome     = child_genome
        new_pop.append(child)

    return new_pop[:n]


# ---------------------------------------------------------------------------
# Population stats (for terminal logging)
# ---------------------------------------------------------------------------

def population_stats(population: list[Agent]) -> dict:
    """Return min / mean / max fitness across the population."""
    fitnesses = [a.fitness for a in population]
    return {
        'min':  round(min(fitnesses),  4),
        'mean': round(float(np.mean(fitnesses)), 4),
        'max':  round(max(fitnesses),  4),
    }


def best_agent(population: list[Agent]) -> Agent:
    """Return the agent with the highest fitness."""
    return max(population, key=lambda a: a.fitness)
