"""
Export .npz copies for TensorFlow .h5 checkpoints.

Run this once in a TensorFlow-capable environment so inference-only users
(can run NumPy backend on newer Python versions) can load checkpoints.

Usage:
    python AI/export_npz_checkpoints.py
    python AI/export_npz_checkpoints.py --checkpoints-dir AI/checkpoints
    python AI/export_npz_checkpoints.py --overwrite
"""

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from AI.agent import Agent
from AI.model import backend_name


def _list_h5_checkpoint_bases(checkpoint_dir: str) -> list[str]:
    if not os.path.isdir(checkpoint_dir):
        return []

    bases: set[str] = set()
    suffix = '_placement.weights.h5'
    for name in os.listdir(checkpoint_dir):
        if not name.endswith(suffix):
            continue
        base = name[:-len(suffix)]
        p_h5 = os.path.join(checkpoint_dir, f'{base}_placement.weights.h5')
        t_h5 = os.path.join(checkpoint_dir, f'{base}_targeting.weights.h5')
        if os.path.exists(p_h5) and os.path.exists(t_h5):
            bases.add(os.path.join(checkpoint_dir, base))

    return sorted(bases)


def _npz_exists(base_path: str) -> bool:
    p_npz = f'{base_path}_placement.weights.npz'
    t_npz = f'{base_path}_targeting.weights.npz'
    return os.path.exists(p_npz) and os.path.exists(t_npz)


def main() -> int:
    parser = argparse.ArgumentParser(description='Export NPZ copies for H5 checkpoints.')
    parser.add_argument('--checkpoints-dir', type=str, default='AI/checkpoints',
                        help='Directory containing checkpoint files.')
    parser.add_argument('--overwrite', action='store_true',
                        help='Re-export NPZ even if files already exist.')
    args = parser.parse_args()

    if backend_name() != 'tensorflow':
        print('[export-npz] TensorFlow backend is required to read .h5 checkpoints.')
        print('[export-npz] Run this script in the training environment (e.g. Python 3.10 + TensorFlow).')
        return 1

    bases = _list_h5_checkpoint_bases(args.checkpoints_dir)
    if not bases:
        print(f'[export-npz] No .h5 checkpoint pairs found in: {args.checkpoints_dir}')
        return 0

    converted = 0
    skipped = 0

    for base in bases:
        if _npz_exists(base) and not args.overwrite:
            skipped += 1
            continue

        agent = Agent.load(base)
        agent.save(base)
        converted += 1
        print(f'[export-npz] exported: {base}')

    print(
        f'[export-npz] done | converted={converted} skipped={skipped} total={len(bases)} '
        f'dir={args.checkpoints_dir}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
