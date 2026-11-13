import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from wathiqa.synth.degrade import LEVELS, degrade, degrade_file, degrade_folder


def page() -> np.ndarray:
    """A white page with black text-like bars."""
    img = np.full((400, 300, 3), 255, np.uint8)
    for y in range(40, 360, 30):
        cv2.putText(
            img, "FACTURE 12 345,67 DA", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2
        )
    return img


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def test_clean_is_an_unchanged_copy() -> None:
    img = page()
    out = degrade(img, "clean", 1)
    assert np.array_equal(out, img) and out is not img


@pytest.mark.parametrize("level", list(LEVELS))
def test_shape_and_type_are_preserved(level: str) -> None:
    out = degrade(page(), level, 3)
    assert out.shape == page().shape and out.dtype == np.uint8


def test_same_seed_same_pixels_different_seed_different_pixels() -> None:
    a, b, c = (
        degrade(page(), "medium", 5),
        degrade(page(), "medium", 5),
        degrade(page(), "medium", 6),
    )
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_stronger_levels_change_the_image_more() -> None:
    img = page()
    d = [np.mean([distance(degrade(img, lv, s), img) for s in range(5)]) for lv in LEVELS]
    assert d[0] < d[1] < d[2]


def test_heavy_is_degraded_but_still_a_page() -> None:
    out = degrade(page(), "heavy", 2)
    assert out.mean() > 120  # still mostly bright paper, not a black square


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown level"):
        degrade(page(), "extreme", 1)


def test_file_round_trip_and_missing_file(tmp_path: Path) -> None:
    src = tmp_path / "a.png"
    cv2.imwrite(str(src), page())
    dst = tmp_path / "out" / "a.png"
    degrade_file(src, dst, "light", 1)
    assert cv2.imread(str(dst)).shape == page().shape
    with pytest.raises(FileNotFoundError):
        degrade_file(tmp_path / "nope.png", dst, "light", 1)


def test_folder_writes_each_level_and_copies_ground_truth(tmp_path: Path) -> None:
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    for name in ("a", "b"):
        cv2.imwrite(str(src / f"{name}.png"), page())
        (src / f"{name}.json").write_text(json.dumps({"id": name}), encoding="utf-8")
    assert degrade_folder(src, out, ["light", "heavy"], seed=1) == 4
    assert sorted(p.name for p in (out / "heavy").iterdir()) == [
        "a.json",
        "a.png",
        "b.json",
        "b.png",
    ]
    # reproducible: running again gives byte-identical pixels
    first = cv2.imread(str(out / "heavy" / "a.png"))
    degrade_folder(src, out, ["heavy"], seed=1)
    assert np.array_equal(first, cv2.imread(str(out / "heavy" / "a.png")))
