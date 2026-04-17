"""
Neural Network Models
======================
Supports two backends:

1) TensorFlow/Keras (preferred when installed)
2) NumPy fallback (used automatically when TensorFlow is unavailable)

This allows training to run on CPU without requiring TensorFlow installation,
which is useful on Python versions where TensorFlow wheels are not available.
"""

import os
import io
from typing import Any

import numpy as np

from AI import config


# ---------------------------------------------------------------------------
# Backend detection / setup
# ---------------------------------------------------------------------------

_TF_AVAILABLE = False
try:
    if config.FORCE_CPU:
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        os.environ['TF_DIRECTML_DISABLE'] = '1'
    import tensorflow as tf  # type: ignore
    _TF_AVAILABLE = True
except Exception:
    tf = None  # type: ignore
    _TF_AVAILABLE = False


def backend_name() -> str:
    return 'tensorflow' if _TF_AVAILABLE else 'numpy'


def list_available_gpus() -> list[str]:
    if not _TF_AVAILABLE:
        return []
    try:
        return [d.name for d in tf.config.list_physical_devices('GPU')]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# NumPy fallback model
# ---------------------------------------------------------------------------

class _NumpyTensor:
    """Tiny wrapper to mimic TensorFlow tensors used in existing code."""

    def __init__(self, array: np.ndarray) -> None:
        self._array = np.asarray(array, dtype=np.float32)

    def numpy(self) -> np.ndarray:
        return self._array


class NumpyMLP:
    """Simple feed-forward MLP with relu activation and flat-weight IO."""

    def __init__(
        self,
        input_size: int,
        hidden_sizes: list[int],
        output_size: int,
        activation: str = 'relu',
        name: str = 'numpy_mlp',
    ) -> None:
        self.input_size = input_size
        self.hidden_sizes = hidden_sizes
        self.output_size = output_size
        self.activation = activation
        self.name = name

        rng = np.random.default_rng()
        dims = [input_size] + hidden_sizes + [output_size]
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []

        for fan_in, fan_out in zip(dims[:-1], dims[1:]):
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            w = rng.uniform(-limit, limit, size=(fan_in, fan_out)).astype(np.float32)
            b = np.zeros((fan_out,), dtype=np.float32)
            self.weights.append(w)
            self.biases.append(b)

    def __call__(self, x: np.ndarray, training: bool = False) -> _NumpyTensor:
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 1:
            x = x[np.newaxis, :]

        h = x
        last_idx = len(self.weights) - 1
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            h = h @ w + b
            if i != last_idx and self.activation == 'relu':
                h = np.maximum(h, 0.0)
        return _NumpyTensor(h)

    @property
    def trainable_weights(self) -> list[np.ndarray]:
        tw: list[np.ndarray] = []
        for w, b in zip(self.weights, self.biases):
            tw.append(w)
            tw.append(b)
        return tw

    def get_flat_weights(self) -> np.ndarray:
        return np.concatenate([arr.ravel() for arr in self.trainable_weights]).astype(np.float32)

    def set_flat_weights(self, flat: np.ndarray) -> None:
        flat = np.asarray(flat, dtype=np.float32)
        offset = 0
        for i in range(len(self.weights)):
            w_shape = self.weights[i].shape
            w_size = int(np.prod(w_shape))
            self.weights[i] = flat[offset:offset + w_size].reshape(w_shape)
            offset += w_size

            b_shape = self.biases[i].shape
            b_size = int(np.prod(b_shape))
            self.biases[i] = flat[offset:offset + b_size].reshape(b_shape)
            offset += b_size

    def count_weights(self) -> int:
        return sum(int(np.prod(arr.shape)) for arr in self.trainable_weights)

    def save_weights(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        payload = {f'arr_{i}': arr for i, arr in enumerate(self.trainable_weights)}
        with open(path, 'wb') as f:
            np.savez(f, **payload)

    def load_weights(self, path: str) -> None:
        with np.load(path) as data:
            flat = [data[f'arr_{i}'] for i in range(len(data.files))]
        offset = 0
        for i in range(len(self.weights)):
            self.weights[i] = np.asarray(flat[offset], dtype=np.float32)
            self.biases[i] = np.asarray(flat[offset + 1], dtype=np.float32)
            offset += 2


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_tf_mlp(
    input_size: int,
    hidden_sizes: list[int],
    output_size: int,
    output_activation: str | None = None,
    name: str = 'mlp',
):
    inp = tf.keras.Input(shape=(input_size,), name='input')
    x = inp
    for i, units in enumerate(hidden_sizes):
        x = tf.keras.layers.Dense(units, activation=config.ACTIVATION, name=f'hidden_{i}')(x)
    out = tf.keras.layers.Dense(output_size, activation=output_activation, name='output')(x)
    return tf.keras.Model(inputs=inp, outputs=out, name=name)


def build_placement_net():
    if _TF_AVAILABLE:
        return _build_tf_mlp(
            input_size=config.PLACEMENT_NOISE_SIZE,
            hidden_sizes=config.PLACEMENT_HIDDEN_SIZES,
            output_size=config.PLACEMENT_OUTPUT_SIZE,
            name='placement_net',
        )
    return NumpyMLP(
        input_size=config.PLACEMENT_NOISE_SIZE,
        hidden_sizes=config.PLACEMENT_HIDDEN_SIZES,
        output_size=config.PLACEMENT_OUTPUT_SIZE,
        activation=config.ACTIVATION,
        name='placement_net_numpy',
    )


def build_targeting_net():
    if _TF_AVAILABLE:
        return _build_tf_mlp(
            input_size=config.TARGETING_INPUT_SIZE,
            hidden_sizes=config.TARGETING_HIDDEN_SIZES,
            output_size=config.TARGETING_OUTPUT_SIZE,
            name='targeting_net',
        )
    return NumpyMLP(
        input_size=config.TARGETING_INPUT_SIZE,
        hidden_sizes=config.TARGETING_HIDDEN_SIZES,
        output_size=config.TARGETING_OUTPUT_SIZE,
        activation=config.ACTIVATION,
        name='targeting_net_numpy',
    )


# ---------------------------------------------------------------------------
# Weight helpers
# ---------------------------------------------------------------------------

def get_flat_weights(model: Any) -> np.ndarray:
    if hasattr(model, 'get_flat_weights'):
        return model.get_flat_weights()
    arrays = [w.numpy().flatten() for w in model.trainable_weights]
    return np.concatenate(arrays) if arrays else np.array([], dtype=np.float32)


def set_flat_weights(model: Any, flat: np.ndarray) -> None:
    if hasattr(model, 'set_flat_weights'):
        model.set_flat_weights(flat)
        return

    offset = 0
    for w in model.trainable_weights:
        size = int(w.shape.num_elements())
        chunk = flat[offset:offset + size].reshape(w.shape)
        w.assign(chunk)
        offset += size


def count_weights(model: Any) -> int:
    if hasattr(model, 'count_weights'):
        return int(model.count_weights())
    return sum(int(w.shape.num_elements()) for w in model.trainable_weights)


def genome_size(placement_net: Any, targeting_net: Any) -> int:
    return count_weights(placement_net) + count_weights(targeting_net)


def genome_from_models(placement_net: Any, targeting_net: Any) -> np.ndarray:
    return np.concatenate([get_flat_weights(placement_net), get_flat_weights(targeting_net)]).astype(np.float32)


def models_from_genome(genome: np.ndarray, placement_net: Any, targeting_net: Any) -> None:
    p_size = count_weights(placement_net)
    set_flat_weights(placement_net, genome[:p_size])
    set_flat_weights(targeting_net, genome[p_size:])


def batch_placement_inference(placement_net: Any, noise_batch: np.ndarray) -> np.ndarray:
    out = placement_net(noise_batch, training=False)
    return out.numpy() if hasattr(out, 'numpy') else np.asarray(out, dtype=np.float32)


def batch_targeting_inference(targeting_net: Any, state_batch: np.ndarray) -> np.ndarray:
    out = targeting_net(state_batch, training=False)
    return out.numpy() if hasattr(out, 'numpy') else np.asarray(out, dtype=np.float32)


def save_weights_npz(model: Any, path: str) -> None:
    """
    Save model trainable weights in backend-agnostic .npz format.

    Format:
      arr_0, arr_1, ... in trainable-weight order.
    """
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)

    if hasattr(model, 'trainable_weights'):
        arrays = []
        for w in model.trainable_weights:
            if hasattr(w, 'numpy'):
                arrays.append(np.asarray(w.numpy(), dtype=np.float32))
            else:
                arrays.append(np.asarray(w, dtype=np.float32))
        payload = {f'arr_{i}': arr for i, arr in enumerate(arrays)}
        with open(path, 'wb') as f:
            np.savez(f, **payload)
        return

    if hasattr(model, 'save_weights'):
        model.save_weights(path)
        return

    raise TypeError(f'Unsupported model type for NPZ save: {type(model)}')


def load_weights_npz(model: Any, path: str) -> None:
    """
    Load backend-agnostic .npz trainable weights into either backend model.
    """
    with np.load(path) as data:
        arrays = [
            np.asarray(data[k], dtype=np.float32)
            for k in sorted(data.files, key=lambda name: int(name.split('_')[1]))
        ]

    if hasattr(model, 'trainable_weights'):
        vars_ = list(model.trainable_weights)
        if len(arrays) != len(vars_):
            raise ValueError(
                f'NPZ weight count mismatch: checkpoint has {len(arrays)} arrays, '
                f'model expects {len(vars_)} trainable weights.'
            )

        for var, arr in zip(vars_, arrays):
            if hasattr(var, 'assign'):
                var.assign(arr)
            else:
                np.copyto(var, arr)
        return

    if hasattr(model, 'load_weights'):
        model.load_weights(path)
        return

    raise TypeError(f'Unsupported model type for NPZ load: {type(model)}')
