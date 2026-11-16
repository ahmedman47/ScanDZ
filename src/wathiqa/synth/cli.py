"""python -m wathiqa.synth.cli --n 20 --out data/synthetic --seed 42"""

from __future__ import annotations

import argparse
import random
from dataclasses import asdict
from pathlib import Path

from wathiqa.synth.generate import (
    DEV_TEMPLATES,
    ERROR_KINDS,
    TEMPLATES,
    TEST_TEMPLATES,
    inject_error,
    make_invoice,
    random_style,
)
from wathiqa.synth.render import html_to_files, render_html, write_ground_truth


def generate(
    n: int,
    out: Path,
    seed: int,
    error_rate: float = 0.05,
    pool: tuple[str, ...] = TEMPLATES,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    htmls: dict[str, str] = {}
    for i in range(n):
        rng = random.Random(f"{seed}-{i}")  # one independent stream per document
        invoice = make_invoice(rng)
        style = random_style(rng, pool=pool)
        error = rng.choice(ERROR_KINDS) if rng.random() < error_rate else None
        if error:
            invoice = inject_error(invoice, error)
        name = f"inv_{seed}_{i:05d}"
        htmls[name] = render_html(invoice, style)
        write_ground_truth(
            out / f"{name}.json",
            invoice,
            {"seed": seed, "index": i, "injected_error": error, **asdict(style)},
        )
    html_to_files(htmls, out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic invoices with ground truth")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--split", choices=("dev", "test"), default="dev",
                    help="dev uses DEV_TEMPLATES, test uses TEST_TEMPLATES only")
    ap.add_argument("--out", type=Path, default=None,
                    help="default: data/synthetic/<split>")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--error-rate", type=float, default=0.05)
    args = ap.parse_args()
    pool = DEV_TEMPLATES if args.split == "dev" else TEST_TEMPLATES
    out = args.out or Path("data/synthetic") / args.split
    generate(args.n, out, args.seed, args.error_rate, pool)
    print(f"wrote {args.n} {args.split} documents to {out}")


if __name__ == "__main__":
    main()
