"""Make clean renders look like phone photos and scans.

Each level mixes the same defects with growing strength: small rotation, perspective
(camera not parallel to the page), blur, sensor noise, uneven lighting, a soft shadow,
lower contrast, a fold line and JPEG compression. Everything is driven by one seed, so a
degraded dataset can be regenerated exactly.

The ground truth never changes: only the pixels do.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[Any]  # uint8 BGR pixels; OpenCV stubs are loose, so keep the alias loose


@dataclass(frozen=True, slots=True)
class Level:
    rotation_deg: float  # maximum absolute rotation
    perspective: float  # corner jitter as a fraction of the image size
    blur_sigma: float
    noise_std: float
    lighting: float  # strength of the brightness gradient (0 to 1)
    shadow: float  # strength of the shadow band (0 to 1)
    contrast: float  # 1.0 = unchanged, lower = washed out
    fold: bool
    jpeg_quality: int  # 100 = effectively lossless


LEVELS: dict[str, Level] = {
    "light": Level(0.5, 0.003, 0.5, 3.0, 0.05, 0.0, 1.00, False, 90),
    "medium": Level(1.5, 0.012, 1.0, 8.0, 0.15, 0.25, 0.90, False, 65),
    "heavy": Level(3.0, 0.025, 1.8, 16.0, 0.30, 0.55, 0.75, True, 35),
}
PAPER = 235  # grey used where the warp reveals "table" behind the page


def _rotate_and_warp(img: Image, rng: np.random.Generator, lv: Level) -> Image:
    h, w = img.shape[:2]
    angle = rng.uniform(-lv.rotation_deg, lv.rotation_deg)
    rot = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1.0)
    out = cv2.warpAffine(
        img, rot, (w, h), flags=cv2.INTER_LINEAR, borderValue=(PAPER, PAPER, PAPER)
    )
    if lv.perspective > 0:
        src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
        jitter = rng.uniform(-lv.perspective, lv.perspective, size=(4, 2)) * np.array([w, h])
        dst = (src + jitter).astype(np.float32)
        warp = cv2.getPerspectiveTransform(src, dst)
        out = cv2.warpPerspective(
            out, warp, (w, h), flags=cv2.INTER_LINEAR, borderValue=(PAPER, PAPER, PAPER)
        )
    return out


def _gradient(h: int, w: int, rng: np.random.Generator) -> NDArray[np.float32]:
    """A smooth ramp from -1 to 1 along a random direction."""
    theta = rng.uniform(0, 2 * np.pi)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ramp = (xs / w - 0.5) * np.cos(theta) + (ys / h - 0.5) * np.sin(theta)
    return np.asarray(ramp / (np.abs(ramp).max() + 1e-6), dtype=np.float32)


def _lighting(img: Image, rng: np.random.Generator, lv: Level) -> Image:
    if lv.lighting <= 0:
        return img
    h, w = img.shape[:2]
    factor = 1.0 + lv.lighting * _gradient(h, w, rng)
    return np.clip(img.astype(np.float32) * factor[..., None], 0, 255).astype(np.uint8)


def _shadow(img: Image, rng: np.random.Generator, lv: Level) -> Image:
    if lv.shadow <= 0:
        return img
    h, w = img.shape[:2]
    ramp = _gradient(h, w, rng)
    centre = rng.uniform(-0.3, 0.3)
    band = np.exp(-((ramp - centre) ** 2) / 0.08).astype(np.float32)
    soft = np.asarray(cv2.GaussianBlur(band, (0, 0), max(h, w) * 0.02), dtype=np.float32)
    factor = 1.0 - lv.shadow * 0.6 * soft
    return np.clip(img.astype(np.float32) * factor[..., None], 0, 255).astype(np.uint8)


def _fold(img: Image, rng: np.random.Generator) -> Image:
    h = img.shape[0]
    y = int(rng.uniform(0.3, 0.7) * h)
    out = img.astype(np.float32)
    out[max(0, y - 1) : y + 2] *= 0.82
    out[max(0, y - 6) : y - 1] *= 1.03
    return np.clip(out, 0, 255).astype(np.uint8)


def degrade(img: Image, level: str, seed: int) -> Image:
    """Return a degraded copy of ``img`` (BGR, uint8).

    ``level`` is one of clean, light, medium, heavy.
    """
    if level == "clean":
        return img.copy()
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; choose clean, {', '.join(LEVELS)}")
    lv = LEVELS[level]
    rng = np.random.default_rng(seed)
    out = _rotate_and_warp(img, rng, lv)
    out = _lighting(out, rng, lv)
    out = _shadow(out, rng, lv)
    if lv.contrast < 1.0:
        out = np.clip((out.astype(np.float32) - 128) * lv.contrast + 128, 0, 255).astype(np.uint8)
    if lv.fold:
        out = _fold(out, rng)
    if lv.blur_sigma > 0:
        out = cv2.GaussianBlur(out, (0, 0), lv.blur_sigma)
    if lv.noise_std > 0:
        noise = rng.normal(0, lv.noise_std, size=out.shape)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, lv.jpeg_quality])
    if not ok:  # pragma: no cover - encoding a valid array does not fail
        raise RuntimeError("JPEG encoding failed")
    decoded = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return np.asarray(decoded, dtype=np.uint8)


def degrade_file(src: Path, dst: Path, level: str, seed: int) -> None:
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"cannot read image: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(dst), degrade(img, level, seed)):
        raise OSError(f"cannot write image: {dst}")


def degrade_folder(src_dir: Path, out_dir: Path, levels: list[str], seed: int) -> int:
    """For every ``*.png`` write one degraded copy per level, and copy the ground truth."""
    count = 0
    for png in sorted(src_dir.glob("*.png")):
        for level in levels:
            # One independent random stream per (document, level): stable and reproducible.
            doc_seed = int.from_bytes(f"{seed}-{png.stem}-{level}".encode(), "little") % (2**32)
            target = out_dir / level
            degrade_file(png, target / png.name, level, doc_seed)
            truth = png.with_suffix(".json")
            if truth.exists():
                shutil.copy(truth, target / truth.name)
            count += 1
    return count


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Degrade synthetic invoices to look like photos")
    ap.add_argument("--src", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--out", type=Path, default=Path("data/degraded"))
    ap.add_argument("--levels", nargs="+", default=["light", "medium", "heavy"])
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    n = degrade_folder(args.src, args.out, args.levels, args.seed)
    print(f"wrote {n} images to {args.out}")


if __name__ == "__main__":
    main()
