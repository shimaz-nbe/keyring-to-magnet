from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_grayscale(image_path: Path) -> np.ndarray:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"could not read image: {image_path}")
    return img


def flip_horizontal(img: np.ndarray) -> np.ndarray:
    """Mirror the scan left-right.

    Rubber keyrings have raised relief on the front face, so an accurate
    outline scan is taken of the flat back/bottom face instead. That leaves
    the traced silhouette mirrored relative to how the character reads from
    the front, so the scan is flipped back before any downstream processing.
    """
    return cv2.flip(img, 1)


def binarize(gray: np.ndarray, blur_ksize: int = 5) -> np.ndarray:
    """Binarize a (possibly noisy) grayscale scan. Foreground (ink) = 255, background = 0.

    Otsu's method picks the threshold automatically, and Potrace's own
    turdsize/alphamax parameters handle despeckling, so no morphological
    open/close is applied here -- that would risk biasing the reference
    circle's radius before calibration.
    """
    blurred = cv2.medianBlur(gray, blur_ksize) if blur_ksize > 1 else gray
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def write_pbm(binary_img: np.ndarray, out_path: Path) -> None:
    """Write a binary (foreground=255) image as a P4 (binary PBM) file for Potrace."""
    h, w = binary_img.shape
    bits = (binary_img > 127).astype(np.uint8)
    packed = np.packbits(bits, axis=1, bitorder="big")
    with open(out_path, "wb") as f:
        f.write(f"P4\n{w} {h}\n".encode("ascii"))
        f.write(packed.tobytes())
