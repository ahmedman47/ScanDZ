# Synthetic data generator: setup on Windows

    pip install -e ".[dev,db,synth]"
    python -m playwright install chromium
    python -m wathiqa.synth.cli --n 20 --out data\synthetic --seed 42

Output per document: `inv_<seed>_<index>.json` (ground truth), `.pdf`, `.png`.
