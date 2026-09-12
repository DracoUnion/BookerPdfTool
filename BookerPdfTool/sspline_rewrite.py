"""NumPy reimplementation of the image-resampling core identified in S-Spline.exe.

The original binary uses separable image operations and clipped bitmap copies.
This module keeps those operations portable and vectorized with NumPy.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

try:
    from PIL import Image
except ImportError:  # Pillow is only needed by resize_file().
    Image = None


def _mirror_indices(indices: np.ndarray, length: int) -> np.ndarray:
    """Reflect integer coordinates at image boundaries."""
    if length <= 1:
        return np.zeros_like(indices, dtype=np.intp)
    period = 2 * length - 2
    indices = np.mod(indices, period)
    return np.where(indices < length, indices, period - indices).astype(np.intp)


def _cubic_bspline(distance: np.ndarray) -> np.ndarray:
    """Evaluate the centered cubic B-spline kernel elementwise."""
    distance = np.abs(distance)
    weights = np.zeros_like(distance, dtype=np.float64)
    inner = distance < 1.0
    outer = (distance >= 1.0) & (distance < 2.0)
    weights[inner] = (4.0 - 6.0 * distance[inner] ** 2
                      + 3.0 * distance[inner] ** 3) / 6.0
    delta = 2.0 - distance[outer]
    weights[outer] = delta ** 3 / 6.0
    return weights


def _axis_weights(destination_size: int, source_size: int,
                  scale: float) -> tuple[np.ndarray, np.ndarray]:
    """Build a normalized sparse 4-tap sampling matrix for one axis."""
    positions = (np.arange(destination_size, dtype=np.float64) + 0.5) / scale - 0.5
    left = np.floor(positions).astype(np.intp) - 1
    offsets = np.arange(4, dtype=np.intp)
    coordinates = _mirror_indices(left[:, None] + offsets[None, :], source_size)
    weights = _cubic_bspline(positions[:, None] - (left[:, None] + offsets[None, :]))
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), np.finfo(np.float64).eps)
    return coordinates, weights


def resize_rgb(pixels: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize an RGB/RGBA image using separable cubic B-spline sampling.

    Args:
        pixels: Array shaped ``(source_height, source_width, channels)``.
        width: Destination width.
        height: Destination height.

    Returns:
        ``uint8`` NumPy array shaped ``(height, width, channels)``.
    """
    source = np.asarray(pixels)
    if source.ndim != 3 or source.shape[2] not in (3, 4):
        raise ValueError("pixels must have shape (height, width, 3) or (height, width, 4)")
    if width < 1 or height < 1:
        raise ValueError("destination dimensions must be positive")

    source_height, source_width, _ = source.shape
    source = source.astype(np.float64, copy=False)
    x_indices, x_weights = _axis_weights(width, source_width, width / source_width)
    y_indices, y_weights = _axis_weights(height, source_height, height / source_height)

    # Horizontal pass: (H, W, C) -> (H, destination_W, C).
    horizontal = np.take(source, x_indices, axis=1)
    horizontal = np.sum(horizontal * x_weights[None, :, :, None], axis=2)

    # Vertical pass: (H, destination_W, C) -> (destination_H, destination_W, C).
    result = np.take(horizontal, y_indices, axis=0)
    result = np.sum(result * y_weights[:, :, None, None], axis=1)
    return np.clip(np.rint(result), 0, 255).astype(np.uint8)


def clipped_copy(src: np.ndarray, dst: np.ndarray, src_x: int, src_y: int,
                 dst_x: int, dst_y: int, width: int, height: int) -> None:
    """NumPy equivalent of the clipped row copy observed at 0x459194.

    The copy is clipped against both arrays and supports RGB/RGBA or any trailing
    channel shape. It mutates ``dst`` in place.
    """
    source = np.asarray(src)
    target = np.asarray(dst)
    if source.ndim < 2 or target.ndim < 2:
        raise ValueError("src and dst must be at least two-dimensional")
    if width <= 0 or height <= 0:
        return
    if source.ndim != target.ndim or source.shape[2:] != target.shape[2:]:
        raise ValueError("src and dst channel shapes must match")

    sx, sy, dx, dy = src_x, src_y, dst_x, dst_y
    if sx < 0:
        dx -= sx
        width += sx
        sx = 0
    if sy < 0:
        dy -= sy
        height += sy
        sy = 0
    if dx < 0:
        sx -= dx
        width += dx
        dx = 0
    if dy < 0:
        sy -= dy
        height += dy
        dy = 0
    width = min(width, source.shape[1] - sx, target.shape[1] - dx)
    height = min(height, source.shape[0] - sy, target.shape[0] - dy)
    if width <= 0 or height <= 0:
        return
    target[dy:dy + height, dx:dx + width] = source[sy:sy + height, sx:sx + width]


def resize_file(input_path: str | Path, output_path: str | Path,
                width: int, height: int) -> None:
    """Load an image, resize it through the NumPy implementation, and save it."""
    if Image is None:
        raise RuntimeError("Pillow is required: python -m pip install Pillow")
    with Image.open(input_path) as image:
        mode = "RGBA" if "A" in image.getbands() else "RGB"
        source = np.asarray(image.convert(mode))
    result = resize_rgb(source, width, height)
    Image.fromarray(result, mode=mode).save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="NumPy S-Spline-style image resampler")
    parser.add_argument("input", help="input image")
    parser.add_argument("output", help="output image")
    parser.add_argument("width", type=int)
    parser.add_argument("height", type=int)
    args = parser.parse_args()
    resize_file(args.input, args.output, args.width, args.height)


if __name__ == "__main__":
    main()
