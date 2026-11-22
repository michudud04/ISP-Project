"""Rule-based quality control for the aggregated sensor series.

The rules are simple and physically motivated. Every value they change is
counted in the returned log so the EDA can report what was removed and why.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Upper limits for 12 h *means*. Clear-sky 12 h means stay below ~500 W/m2 POA
# and ~900 umol/m2/s PAR (their 99th percentiles here); the handful of values
# above these limits share timestamps across sensors, i.e. logger outages
# that left only a few midday samples in the bucket.
CEILINGS_12H = {"gpoa": 600.0, "albedo": 100.0, "par": 1200.0}

# Both 12 h buckets (00-12 and 12-24 UTC) contain daylight all year at this
# latitude, so a 12 h mean of ~0 is a logger outage reporting zeros.
FLATLINE_12H = {"gpoa": 1.0, "par": 1.0}

# PAR / mean POA irradiance below this fraction of its median ratio means the
# PAR logger dropped out while the pyranometers kept running (full or partial bucket).
PAR_CONSISTENCY_FRACTION = 0.25

NONNEGATIVE = ("albedo", "wind_speed")
NEGATIVE_TOLERANCE = 5.0  # offsets down to -5 are clipped to 0, below that removed
PV_SIBLING_TOLERANCE_K = 10.0

# Sensors that look unreliable but are kept in the data; downstream plot-level
# aggregates exclude them.
SUSPECT_SENSORS = {
    "S1_d20_par": (
        "erratic relative to S1_d19/S1_d21 (monthly ratio 0.3-1.9), fails the PAR/POA "
        "consistency check ~2.5x more often than its neighbours; its 16-bit channel is broken"
    ),
}


def clean_sensors(
    df: pd.DataFrame, meta: pd.DataFrame, resolution: str = "12h"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply QC rules column by column. Returns (cleaned data, log of changes)."""
    df = df.copy()
    log: list[dict] = []
    is_12h = resolution == "12h"

    def record(col: str, mask: pd.Series, rule: str, action: str = "removed") -> None:
        n = int(mask.sum())
        if n:
            log.append({"column": col, "rule": rule, "action": action, "n": n})

    def remove(col: str, mask: pd.Series, rule: str) -> None:
        record(col, mask, rule)
        df.loc[mask, col] = np.nan

    for col in df.columns:
        quantity = meta.at[col, "quantity"]
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if quantity in NONNEGATIVE:
            remove(col, df[col] < -NEGATIVE_TOLERANCE, "negative beyond sensor offset")
            small_negative = df[col] < 0
            record(col, small_negative, "small negative offset", action="clipped to 0")
            df.loc[small_negative, col] = 0.0
        if is_12h and quantity in FLATLINE_12H:
            remove(col, df[col] < FLATLINE_12H[quantity], "~0 over a 12 h bucket (logger outage)")
        if is_12h and quantity in CEILINGS_12H:
            limit = CEILINGS_12H[quantity]
            remove(col, df[col] > limit, f"12 h mean above {limit:g} (partial bucket)")
        if quantity == "vwc":
            remove(col, df[col] < 1.0, "VWC dropout (< 1 %)")
        if quantity == "soil_temp":
            remove(col, df[col] == 0.0, "exact-zero dropout")
        if quantity == "rh":
            remove(col, (df[col] < 0) | (df[col] > 100), "RH outside 0-100 %")

    _check_par_against_poa(df, meta, remove)
    _check_pv_siblings(df, meta, remove)
    return df, pd.DataFrame(log, columns=["column", "rule", "action", "n"])


def _columns(df: pd.DataFrame, meta: pd.DataFrame, quantity: str) -> list[str]:
    return [c for c in meta.index[meta["quantity"] == quantity] if c in df.columns]


def _check_par_against_poa(df, meta, remove) -> None:
    poa_cols = _columns(df, meta, "gpoa")
    if not poa_cols:
        return
    poa = df[poa_cols].mean(axis=1)
    for col in _columns(df, meta, "par"):
        ratio = df[col] / poa
        remove(col, ratio < PAR_CONSISTENCY_FRACTION * ratio.median(),
               "PAR inconsistent with POA irradiance (PAR logger outage)")


def _check_pv_siblings(df, meta, remove) -> None:
    pv = meta[(meta["quantity"] == "pv_temp") & meta.index.isin(df.columns)]
    for _, cols in pv.groupby("plot").groups.items():
        block = df[list(cols)]
        for col in cols:
            siblings = block.drop(columns=col).median(axis=1)
            remove(col, (block[col] - siblings).abs() > PV_SIBLING_TOLERANCE_K,
                   f"deviates > {PV_SIBLING_TOLERANCE_K:g} K from sibling module sensors")
