"""Image pre-processing that makes faint, tinted or unevenly lit receipts readable.

Typical failures this addresses:
  * grey or blue ink on grey/blue paper (very little luminance contrast),
  * faded thermal paper,
  * shadows and uneven lighting across the receipt,
  * tiny or huge photos (text too small / needlessly slow).

All functions take and return BGR uint8 arrays (what OCR engines expect).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 2000      # larger photos are scaled down (OCR cost grows with pixels)
MIN_SIDE = 1200      # smaller photos are scaled up (tiny text is unreadable)


def load_image(path: str | Path) -> np.ndarray:
    """Read an image honouring EXIF rotation, as a BGR array."""
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def fit_size(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    longest = max(height, width)

    if longest > MAX_SIDE:
        scale, method = MAX_SIDE / longest, cv2.INTER_AREA
    elif longest < MIN_SIDE:
        scale, method = MIN_SIDE / longest, cv2.INTER_CUBIC
    else:
        return image

    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=method)


def _text_visibility(gray: np.ndarray) -> float:
    """How strongly fine structure (text) stands out against the dynamic range."""
    low, high = np.percentile(gray, (1, 99))
    span = max(float(high - low), 1.0)
    blurred = cv2.GaussianBlur(gray, (0, 0), 8)
    detail = np.abs(gray.astype(np.float32) - blurred.astype(np.float32)).mean()
    return float(detail / span)


def _principal_axis_gray(image: np.ndarray) -> np.ndarray:
    """Project colours onto the axis along which they vary the most."""
    pixels = image[::4, ::4].reshape(-1, 3).astype(np.float32)
    mean = pixels.mean(axis=0)
    covariance = np.cov((pixels - mean).T)
    _, vectors = np.linalg.eigh(covariance)
    axis = vectors[:, -1]

    projected = (image.astype(np.float32) - mean) @ axis
    low, high = np.percentile(projected, (0.5, 99.5))
    scaled = (projected - low) / max(float(high - low), 1e-6)
    return np.clip(scaled * 255, 0, 255).astype(np.uint8)


def best_grayscale(image: np.ndarray) -> np.ndarray:
    """Pick the greyscale conversion in which the text is most visible.

    Plain luminance is fine for black-on-white, but blue or grey ink can all but
    vanish in it while staying clear in one colour channel.
    """
    candidates = [cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), *cv2.split(image)]
    candidates.append(_principal_axis_gray(image))

    gray = max(candidates, key=_text_visibility)

    # Receipts are dark text on light paper; flip if the page came out dark.
    if np.median(gray) < 110:
        gray = 255 - gray

    return gray


def flatten_and_stretch(gray: np.ndarray) -> np.ndarray:
    """Remove shadows/uneven light, then stretch the remaining contrast."""
    longest = max(gray.shape[:2])
    kernel_size = max(15, longest // 50) | 1          # odd, relative to image size
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    background = cv2.GaussianBlur(background, (0, 0), kernel_size / 3)
    flat = cv2.divide(gray, np.maximum(background, 1), scale=255)

    low = float(np.percentile(flat, 1))
    high = float(np.percentile(flat, 99.5))
    if high - low < 8:                                  # essentially blank
        return flat

    stretched = (flat.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(stretched, 0, 255).astype(np.uint8)


def _to_bgr(gray: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _prepared_gray(image: np.ndarray) -> np.ndarray:
    """Best channel -> even lighting -> strong contrast -> denoise.

    Order matters. Denoising *before* the contrast stretch erases faint text
    (it looks like noise at that point); stretching without any smoothing makes
    sensor noise look like text. So: a very light blur, stretch, then denoise
    once the text is strong enough to survive it.
    """
    gray = best_grayscale(fit_size(image))
    gray = cv2.GaussianBlur(gray, (0, 0), 1.0)
    gray = flatten_and_stretch(gray)
    return cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)


def enhanced(image: np.ndarray) -> np.ndarray:
    """Second-chance variant for faint, tinted or unevenly lit photos."""
    return _to_bgr(_prepared_gray(image))


def original(image: np.ndarray) -> np.ndarray:
    """Fallback variant: only resized, colours untouched."""
    return fit_size(image)


VARIANTS = {"original": original, "enhanced": enhanced}
