"""Build the processed datasets in ``data/processed`` from the raw Grafana export."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from agrivoltaics.config import PROCESSED_DIR, RAW_DIR
from agrivoltaics.data.cleaning import SUSPECT_SENSORS, clean_sensors
from agrivoltaics.data.load import load_resolution, trim_empty
from agrivoltaics.features.microclimate import to_daily

log = logging.getLogger(__name__)

MAX_SAMPLE_GAP = pd.Timedelta("2min")  # longer gaps are outages, not measurement time


def precipitation_tables(d30: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """30 s WS100 data -> (per-sample table, daily totals and durations)."""
    d30 = d30.copy()
    cum = d30["WS_precip_cum"]
    inc = cum.dropna().diff()
    if (inc < 0).any():
        log.warning("cumulative precipitation decreased %d times; treating as 0", (inc < 0).sum())
    d30["WS_precip_mm"] = inc.clip(lower=0).reindex(d30.index)

    # seconds each sample represents (time to the next one, capped across outages)
    dt = d30.index.to_series().diff().shift(-1)
    dt = dt.where(dt <= MAX_SAMPLE_GAP).dt.total_seconds()
    d30["sample_s"] = dt

    by_day = d30.index.floor("D")
    daily = pd.DataFrame({
        "WS_precip_mm": d30["WS_precip_mm"].groupby(by_day).sum(min_count=1),
        "WS_precip_mm_from_intensity": (d30["WS_precip_intensity"] * dt / 3600).groupby(by_day).sum(min_count=1),
        "WS_coverage": dt.groupby(by_day).sum() / 86_400,
    })
    minutes = (
        d30.assign(m=dt / 60).groupby([by_day, "WS_precip_type"], observed=True)["m"].sum()
        .unstack(fill_value=0.0)
    )
    minutes.columns = [f"WS_minutes_{c.split(' (')[0].lower().replace(' ', '_')}" for c in minutes.columns]
    daily = daily.join(minutes)
    daily.index.name = "date"
    return d30, daily


def build(raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)

    d12, meta12 = load_resolution("12h", raw_dir)
    d12, qc12 = clean_sensors(trim_empty(d12), meta12, "12h")

    d1, meta1 = load_resolution("1D", raw_dir)
    d1, qc1 = clean_sensors(trim_empty(d1), meta1, "1D")

    d30, meta30 = load_resolution("30s", raw_dir)
    d30, precip_daily = precipitation_tables(trim_empty(d30))

    daily = to_daily(d12).join(d1, how="outer").join(precip_daily, how="outer")
    daily.index.name = "date"

    meta = pd.concat([meta12, meta1, meta30])
    meta["suspect"] = meta.index.map(SUSPECT_SENSORS).fillna("")
    series = [_frame_for(c, d12, d1, d30)[c] for c in meta.index]
    meta["first_valid"] = [s.first_valid_index() for s in series]
    meta["last_valid"] = [s.last_valid_index() for s in series]
    qc = pd.concat([qc12, qc1], ignore_index=True)

    outputs = {
        "sensors_12h": d12,
        "daily": daily,
        "precip_30s": d30.drop(columns="sample_s"),
    }
    for name, frame in outputs.items():
        frame.to_parquet(out_dir / f"{name}.parquet")
    meta.to_csv(out_dir / "sensors_meta.csv")
    qc.to_csv(out_dir / "qc_log.csv", index=False)
    log.info("wrote %s", ", ".join(f"{k} {v.shape}" for k, v in outputs.items()))
    return outputs | {"meta": meta, "qc": qc}


def _frame_for(col: str, *frames: pd.DataFrame) -> pd.DataFrame:
    return next(f for f in frames if col in f.columns)
