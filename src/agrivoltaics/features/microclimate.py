"""Derived agronomic / energy quantities from the sensor tables."""

from __future__ import annotations

import pandas as pd

from agrivoltaics.data.cleaning import SUSPECT_SENSORS

# Mean PPFD (umol m-2 s-1) over a day -> daily light integral (mol m-2 d-1)
PPFD_MEAN_TO_DLI = 86_400 / 1e6
# Mean irradiance (W m-2) over a day -> daily insolation (kWh m-2 d-1)
IRRADIANCE_MEAN_TO_KWH = 24 / 1000


def sensor_columns(meta: pd.DataFrame, plot: str, quantity: str, include_suspect: bool = False) -> list[str]:
    """Columns measuring ``quantity`` in ``plot``. (Bracket access: ``meta.plot`` is pandas' plot accessor.)"""
    cols = meta.index[(meta["plot"] == plot) & (meta["quantity"] == quantity)].tolist()
    return cols if include_suspect else [c for c in cols if c not in SUSPECT_SENSORS]


def plot_mean(df: pd.DataFrame, meta: pd.DataFrame, plot: str, quantity: str) -> pd.Series:
    """Mean over all (non-suspect) sensors of one quantity in one plot."""
    cols = [c for c in sensor_columns(meta, plot, quantity) if c in df.columns]
    if not cols:
        raise KeyError(f"no {quantity!r} sensors for plot {plot!r} in this frame")
    return df[cols].mean(axis=1).rename(f"{plot}_{quantity}")


def to_daily(df12: pd.DataFrame) -> pd.DataFrame:
    """Daily means from the two 12 h buckets; days missing a bucket become NaN."""
    numeric = df12.select_dtypes("number")
    grouped = numeric.groupby(numeric.index.floor("D"))
    return grouped.mean().where(grouped.count() == 2)
