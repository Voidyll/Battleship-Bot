"""
AI Agent
=========
Wraps PlacementNet + TargetingNet and exposes two clean decision methods:

    agent.place_all_ships(board)          → places all 5 ships on a Board
    agent.choose_shot(ai_state)           → returns (row, col) to fire at

Agents also carry a genome (flat weight array) used by the genetic algorithm.
Each agent owns its own model instances with independent weights.

An agent can operate in two modes:
    - Training mode (default): uses its own TF model instances.
    - Deployed mode: load from a saved checkpoint for use in the web app.
        agent = Agent.load('AI/checkpoints/final_model')
"""

import numpy as np

import sys
import os

from game.game import Board, Orientation, SHIP_DEFINITIONS, BOARD_SIZE, ShotState
from AI.model import (
    build_placement_net,
    build_targeting_net,
    genome_from_models,
    models_from_genome,
    get_flat_weights,
    set_flat_weights,
    count_weights,
    backend_name,
    save_weights_npz,
    load_weights_npz,
)
from AI import config


class Agent:
    """
    A single Battleship AI agent backed by PlacementNet + TargetingNet.

    Attributes:
        placement_net  tf.keras.Model
        targeting_net  tf.keras.Model
        fitness        float   — set by the trainer after evaluation
    """

    def __init__(self) -> None:
        self.placement_net = build_placement_net()
        self.targeting_net = build_targeting_net()
        self.fitness: float = 0.0
        self._target_input_buf = np.zeros((1, config.TARGETING_INPUT_SIZE), dtype=np.float32)

        # Build (eager build) the models with a dummy forward pass so that
        # weight counts and shapes are fixed before the genome is read.
        self._warmup()

    def _warmup(self) -> None:
        import numpy as np
        dummy_p = np.zeros((1, config.PLACEMENT_NOISE_SIZE), dtype=np.float32)
        dummy_t = np.zeros((1, config.TARGETING_INPUT_SIZE),  dtype=np.float32)
        self.placement_net(dummy_p, training=False)
        self.targeting_net(dummy_t, training=False)

    # ---------------------------------------------------------------- genome

    @property
    def genome(self) -> np.ndarray:
        """Flat float32 array of all weights (placement then targeting)."""
        return genome_from_models(self.placement_net, self.targeting_net)

    @genome.setter
    def genome(self, flat: np.ndarray) -> None:
        models_from_genome(flat, self.placement_net, self.targeting_net)

    @property
    def genome_size(self) -> int:
        return count_weights(self.placement_net) + count_weights(self.targeting_net)

    # ------------------------------------------------------------ placement

    def place_all_ships(
        self,
        board: Board,
        rng:   np.random.Generator | None = None,
    ) -> bool:
        """
        Place all 5 ships on *board* using the placement network.

        The network takes a random noise vector as input and outputs
        per-cell preference scores for both orientations. Ships are placed
        greedily from largest to smallest: for each ship, the highest-scoring
        valid (row, col, orientation) combination is tried first.

        Falls back to random placement if a valid slot cannot be found
        (should be extremely rare on a standard 10×10 board).

        Returns True on success.
        """
        if rng is None:
            rng = np.random.default_rng()

        # Generate a deterministic noise vector from the rng
        noise = rng.standard_normal(config.PLACEMENT_NOISE_SIZE).astype(np.float32)
        prefs = self.placement_net(
            noise[np.newaxis, :], training=False
        ).numpy()[0]  # shape (200,)

        h_prefs = prefs[:config.NUM_CELLS].reshape(BOARD_SIZE, BOARD_SIZE)
        v_prefs = prefs[config.NUM_CELLS:].reshape(BOARD_SIZE, BOARD_SIZE)

        # Sort candidate coordinates once and reuse for all ships.
        h_ranked = np.argsort(h_prefs, axis=None)[::-1]
        v_ranked = np.argsort(v_prefs, axis=None)[::-1]
        ranked_candidates: list[tuple[int, int, Orientation]] = []
        for idx in h_ranked:
            r = int(idx // BOARD_SIZE)
            c = int(idx % BOARD_SIZE)
            ranked_candidates.append((r, c, Orientation.HORIZONTAL))
        for idx in v_ranked:
            r = int(idx // BOARD_SIZE)
            c = int(idx % BOARD_SIZE)
            ranked_candidates.append((r, c, Orientation.VERTICAL))

        for ship in board.ships:
            placed = False
            for r, c, ori in ranked_candidates:
                if board.can_place(ship, r, c, ori):
                    board.place_ship(ship.name, r, c, ori)
                    placed = True
                    break

            if not placed:
                # Fallback: random valid placement
                for _ in range(1000):
                    r   = int(rng.integers(0, BOARD_SIZE))
                    c   = int(rng.integers(0, BOARD_SIZE))
                    ori = Orientation(int(rng.integers(0, 2)))
                    if board.place_ship(ship.name, r, c, ori):
                        placed = True
                        break

            if not placed:
                return False

        return True

    # ------------------------------------------------------------ targeting

    def choose_shot(self, ai_state: dict) -> tuple[int, int]:
        """
        Choose a cell to fire at given the current game state.

        ai_state: dict returned by Game.get_ai_state(player)
            shot_tracker    np.ndarray (10, 10)
            enemy_sunk      list[bool] length 5
            own_ships_alive list[bool] length 5

        Returns (row, col).
        Guarantees the returned cell has ShotState.UNKNOWN (never already shot).
        """
        tracker_grid = ai_state['shot_tracker']
        flat_tracker = tracker_grid.flatten()

        # One-hot-like channel encoding gives clearer spatial state than a single
        # signed-value channel: unknown, miss, hit, sunk.
        offset = 0
        self._target_input_buf[0, offset:offset + config.NUM_CELLS] = (
            flat_tracker == int(ShotState.UNKNOWN)
        ).astype(np.float32)
        offset += config.NUM_CELLS
        self._target_input_buf[0, offset:offset + config.NUM_CELLS] = (
            flat_tracker == int(ShotState.MISS)
        ).astype(np.float32)
        offset += config.NUM_CELLS
        self._target_input_buf[0, offset:offset + config.NUM_CELLS] = (
            flat_tracker == int(ShotState.HIT)
        ).astype(np.float32)
        offset += config.NUM_CELLS
        self._target_input_buf[0, offset:offset + config.NUM_CELLS] = (
            flat_tracker == int(ShotState.SUNK)
        ).astype(np.float32)
        offset += config.NUM_CELLS

        self._target_input_buf[0, offset:offset + config.NUM_SHIPS] = np.asarray(
            ai_state['enemy_sunk'], dtype=np.float32
        )
        offset += config.NUM_SHIPS
        self._target_input_buf[0, offset:offset + config.NUM_SHIPS] = np.asarray(
            ai_state['own_ships_alive'], dtype=np.float32
        )

        scores = self.targeting_net(self._target_input_buf, training=False).numpy()[0]  # (100,)

        # Mask already-shot cells so they are never selected.
        unknown_mask = (flat_tracker == int(ShotState.UNKNOWN))
        scores[~unknown_mask] = -np.inf

        # Tactical target-mode gate: if we have unresolved hits, only consider
        # cells that are adjacent to known hits and line extensions from hit pairs.
        hits = np.argwhere(tracker_grid == int(ShotState.HIT))
        if hits.size > 0:
            candidate_mask = np.zeros(config.NUM_CELLS, dtype=bool)

            for r, c in hits:
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    rr, cc = int(r + dr), int(c + dc)
                    if 0 <= rr < BOARD_SIZE and 0 <= cc < BOARD_SIZE:
                        idx = rr * BOARD_SIZE + cc
                        if unknown_mask[idx]:
                            candidate_mask[idx] = True

            hit_set = {(int(r), int(c)) for r, c in hits}
            for r, c in hit_set:
                # Horizontal contiguous hit pair => extend both ends.
                if (r, c + 1) in hit_set:
                    left = c - 1
                    right = c + 2
                    if 0 <= left < BOARD_SIZE:
                        idx = r * BOARD_SIZE + left
                        if unknown_mask[idx]:
                            candidate_mask[idx] = True
                    if 0 <= right < BOARD_SIZE:
                        idx = r * BOARD_SIZE + right
                        if unknown_mask[idx]:
                            candidate_mask[idx] = True

                # Vertical contiguous hit pair => extend both ends.
                if (r + 1, c) in hit_set:
                    up = r - 1
                    down = r + 2
                    if 0 <= up < BOARD_SIZE:
                        idx = up * BOARD_SIZE + c
                        if unknown_mask[idx]:
                            candidate_mask[idx] = True
                    if 0 <= down < BOARD_SIZE:
                        idx = down * BOARD_SIZE + c
                        if unknown_mask[idx]:
                            candidate_mask[idx] = True

            if np.any(candidate_mask):
                gated_scores = scores.copy()
                gated_scores[~candidate_mask] = -np.inf
                if np.any(np.isfinite(gated_scores)):
                    scores = gated_scores

        if not np.any(np.isfinite(scores)):
            unknown_idx = np.flatnonzero(unknown_mask)
            idx = int(unknown_idx[0]) if len(unknown_idx) > 0 else 0
        else:
            idx = int(np.argmax(scores))
        return (idx // BOARD_SIZE, idx % BOARD_SIZE)

    # ------------------------------------------------------------ save / load

    def save(self, path: str) -> None:
        """
        Save both networks' weights to disk.
        TensorFlow backend: writes .weights.h5 files.
        NumPy backend: writes .weights.npz files.
        """
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        if backend_name() == 'tensorflow':
            p_file = f'{path}_placement.weights.h5'
            t_file = f'{path}_targeting.weights.h5'
            p_npz = f'{path}_placement.weights.npz'
            t_npz = f'{path}_targeting.weights.npz'

            self.placement_net.save_weights(p_file)
            self.targeting_net.save_weights(t_file)

            # Always export NPZ alongside H5 so inference users can run without TensorFlow.
            save_weights_npz(self.placement_net, p_npz)
            save_weights_npz(self.targeting_net, t_npz)
        else:
            p_file = f'{path}_placement.weights.npz'
            t_file = f'{path}_targeting.weights.npz'
            self.placement_net.save_weights(p_file)
            self.targeting_net.save_weights(t_file)

    @classmethod
    def load(cls, path: str) -> 'Agent':
        """
        Load an agent from saved weight files.
        Supports either backend's file format:
            - path_placement.weights.h5 / path_targeting.weights.h5
            - path_placement.weights.npz / path_targeting.weights.npz

        Backend TODO:
            Import and call this at server startup to get the deployable agent:
                from AI.agent import Agent
                ai_agent = Agent.load('AI/checkpoints/final_model')
            Then use ai_agent.place_all_ships(board) and ai_agent.choose_shot(state)
            to drive the AI player's moves.
        """
        agent = cls()

        p_h5 = f'{path}_placement.weights.h5'
        t_h5 = f'{path}_targeting.weights.h5'
        p_npz = f'{path}_placement.weights.npz'
        t_npz = f'{path}_targeting.weights.npz'

        active_backend = backend_name()

        try:
            if active_backend == 'tensorflow':
                # Prefer TensorFlow-native weights when available.
                if os.path.exists(p_h5) and os.path.exists(t_h5):
                    agent.placement_net.load_weights(p_h5)
                    agent.targeting_net.load_weights(t_h5)
                elif os.path.exists(p_npz) and os.path.exists(t_npz):
                    # Fallback for compatibility with NumPy-produced checkpoints.
                    load_weights_npz(agent.placement_net, p_npz)
                    load_weights_npz(agent.targeting_net, t_npz)
                else:
                    raise FileNotFoundError(
                        f'Could not find model weight files for base path: {path}'
                    )
            else:
                # NumPy backend cannot consume TensorFlow .h5 files directly.
                if os.path.exists(p_npz) and os.path.exists(t_npz):
                    load_weights_npz(agent.placement_net, p_npz)
                    load_weights_npz(agent.targeting_net, t_npz)
                elif os.path.exists(p_h5) and os.path.exists(t_h5):
                    raise ValueError(
                        'NumPy backend is active, but only TensorFlow .h5 checkpoint files '
                        f'were found for base path: {path}. Use Python 3.10+TensorFlow '
                        'to load these weights, or provide .npz checkpoint files '
                        '(you can generate them by re-saving checkpoints in a TensorFlow environment).'
                    )
                else:
                    raise FileNotFoundError(
                        f'Could not find model weight files for base path: {path}'
                    )
        except ValueError as e:
            raise ValueError(
                'Checkpoint load failed. This can happen if the checkpoint format does not '
                f'match the active backend ({active_backend}) or if the checkpoint architecture '
                'is incompatible. Current targeting input size is '
                f'{config.TARGETING_INPUT_SIZE}; retrain or load a checkpoint produced '
                'with the current architecture and compatible file format.'
            ) from e

        return agent
