"""Rebuild data/processed/* from the raw Grafana export.

Usage:  python scripts/make_dataset.py
"""

import logging

from agrivoltaics.data.build import build

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = build()
    for name in ("sensors_12h", "daily", "precip_30s"):
        df = result[name]
        print(f"{name:12s} {df.shape[0]:>9,} rows x {df.shape[1]:>3} cols  {df.index.min()} -> {df.index.max()}")
    print(f"QC: {result['qc']['n'].sum()} values changed across {result['qc']['column'].nunique()} columns")
