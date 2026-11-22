"""Reader for CSV files exported from Grafana panels (Inspect -> Data -> Download CSV).

Quirks handled here:

* an Excel hint line ``sep=,`` before the header, and a UTF-8 BOM;
* values formatted as ``"<number> <unit>"`` strings. Grafana auto-scales some
  units per value: cumulative precipitation switches between ``mm`` and ``µm``,
  so the unit has to be parsed row by row, not once per column;
* duplicate column names when a panel shows the same series twice;
* timestamps rendered in the browser's local time, including DST shifts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from agrivoltaics.config import EXPORT_TZ

log = logging.getLogger(__name__)

# Grafana display unit -> (canonical unit, multiplier to reach it)
UNITS: dict[str, tuple[str, float]] = {
    "°C": ("degC", 1.0),
    "°": ("deg", 1.0),
    "%": ("%", 1.0),
    "%H": ("%", 1.0),
    "W/m²": ("W/m2", 1.0),
    "umol m-2 s-1": ("umol/m2/s", 1.0),
    "km/h": ("m/s", 1 / 3.6),
    "m/s": ("m/s", 1.0),
    "mm": ("mm", 1.0),
    "µm": ("mm", 1e-3),  # micro sign
    "μm": ("mm", 1e-3),  # greek small mu
    "mm/h": ("mm/h", 1.0),
}

_DUPLICATE_SUFFIX = re.compile(r"^(?P<base>.+)\.(?P<n>\d+)$")


@dataclass
class GrafanaFrame:
    """Parsed export: one column per series, indexed by UTC time."""

    data: pd.DataFrame
    units: dict[str, str]  # column -> canonical unit ("" for text columns)
    source: Path
    dropped_duplicates: list[str] = field(default_factory=list)


def read_grafana_csv(path: str | Path, tz: str = EXPORT_TZ) -> GrafanaFrame:
    """Parse one Grafana CSV export into numeric (or categorical) UTC-indexed columns."""
    path = Path(path)
    with path.open(encoding="utf-8-sig") as fh:
        skip = 1 if fh.readline().startswith("sep=") else 0
    raw = pd.read_csv(path, skiprows=skip, encoding="utf-8-sig", dtype=str)

    index = _to_utc(raw.pop("Time"), tz)
    data, units = {}, {}
    for col in raw.columns:
        data[col], units[col] = _parse_values(raw[col], col, path)
    df = pd.DataFrame(data)
    df.index = index

    dropped = []
    for col in list(df.columns):
        m = _DUPLICATE_SUFFIX.match(col)
        if m and m["base"] in df.columns:
            if df[col].equals(df[m["base"]]):
                dropped.append(col)
                df = df.drop(columns=col)
                del units[col]
            else:
                log.warning("%s: duplicate column %r differs from %r; keeping both",
                            path.name, col, m["base"])

    dup_rows = df.index.duplicated(keep="first")
    if dup_rows.any():
        # Seen in the 30 s exports: a few rows repeated verbatim in the raw file.
        log.info("%s: dropping %d repeated timestamps", path.name, dup_rows.sum())
        df = df[~dup_rows]
    return GrafanaFrame(df.sort_index(), units, path, dropped)


def _to_utc(local: pd.Series, tz: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(local, format="%Y-%m-%d %H:%M:%S"))
    try:
        idx = idx.tz_localize(tz, ambiguous="infer")
    except ValueError:
        # Aggregated exports have a single, unrepeated stamp in the fall-back hour,
        # so pandas cannot infer it. Buckets start at 00:00 UTC, which is the
        # first (DST) occurrence of that local hour.
        idx = idx.tz_localize(tz, ambiguous=True)
    return idx.tz_convert("UTC").rename("time")


def _parse_values(s: pd.Series, col: str, path: Path) -> tuple[pd.Series, str]:
    present = s.notna()
    parts = s.str.split(" ", n=1, expand=True).reindex(columns=[0, 1])
    number = pd.to_numeric(parts[0], errors="coerce")

    if present.any() and number[present].isna().mean() > 0.5:
        return s.astype("category"), ""  # categorical text, e.g. precipitation type

    bad = present & number.isna()
    if bad.any():
        raise ValueError(f"{path.name}:{col}: unparseable values, e.g. {s[bad].iloc[0]!r}")

    found = set(parts.loc[present, 1].fillna("").unique())
    unknown = found - UNITS.keys()
    if unknown:
        raise ValueError(f"{path.name}:{col}: unknown unit(s) {sorted(unknown)}; add them to UNITS")
    canonical = {UNITS[u][0] for u in found}
    if len(canonical) > 1:
        raise ValueError(f"{path.name}:{col}: mixes incompatible units {sorted(found)}")

    scale = parts[1].map({u: UNITS[u][1] for u in found})
    return (number * scale).astype("float64"), canonical.pop() if canonical else ""
