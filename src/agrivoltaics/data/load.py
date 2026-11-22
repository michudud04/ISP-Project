"""Load raw Grafana panels into tidy, canonically named DataFrames."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from agrivoltaics.config import RAW_DIR
from agrivoltaics.data.catalog import PANELS, PANELS_BY_KEY, describe_column
from agrivoltaics.data.grafana import read_grafana_csv


def load_panel(key: str, raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One panel -> (data with canonical column names, per-column metadata)."""
    panel = PANELS_BY_KEY[key]
    gf = read_grafana_csv(raw_dir / panel.filename)
    keep, meta = {}, []
    for raw_name in gf.data.columns:
        info = describe_column(raw_name, key)
        if info is None:
            continue
        keep[raw_name] = info.name
        meta.append(asdict(info) | {
            "unit": gf.units[raw_name],
            "raw_name": raw_name,
            "panel": key,
            "resolution": panel.resolution,
        })
    data = gf.data[list(keep)].rename(columns=keep)
    return data, pd.DataFrame(meta).set_index("name")


def load_resolution(resolution: str, raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Outer-join every panel exported at ``resolution`` ("12h", "1D" or "30s")."""
    frames, metas = [], []
    for panel in PANELS:
        if panel.resolution != resolution:
            continue
        data, meta = load_panel(panel.key, raw_dir)
        overlap = set(data.columns) & {c for f in frames for c in f.columns}
        if overlap:
            raise ValueError(f"{panel.key}: columns already loaded from another panel: {sorted(overlap)}")
        frames.append(data)
        metas.append(meta)
    return pd.concat(frames, axis=1).sort_index(), pd.concat(metas)


def trim_empty(df: pd.DataFrame) -> pd.DataFrame:
    """Drop leading/trailing rows where every column is missing."""
    valid = df.notna().any(axis=1)
    if not valid.any():
        return df.iloc[0:0]
    return df.loc[valid.idxmax(): valid[::-1].idxmax()]
