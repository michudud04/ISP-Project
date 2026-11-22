# pylint: disable=line-too-long  # the PANELS table reads better unwrapped
"""Which raw file holds what, and how raw series names map to canonical columns.

Canonical column names follow ``{plot}_{device}_{quantity}[_{position}]``, e.g.
``S1_d10_air_temp_center`` or ``R1_d45_par``. :func:`describe_column` raises on
any series it does not recognise, so a re-export with new sensors fails loudly
instead of silently dropping data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Panel:
    key: str
    filename: str
    resolution: str  # pandas offset alias of the export interval
    description: str


PANELS: tuple[Panel, ...] = (
    Panel("air_temperature", "AIR Temperatures (ALL)-data-as-joinbyfield-2026-09-24 12_15_52.csv", "12h", "Air temperature, all nodes + WS100"),
    Panel("dew_point", "Dew Point-data-as-joinbyfield-2026-09-24 12_16_57.csv", "12h", "Dew point"),
    Panel("irradiance", "Irradiance-data-as-joinbyfield-2026-09-24 12_23_16.csv", "12h", "Plane-of-array and albedo pyranometers"),
    Panel("pv_temperature", "PV panel temperatures-data-as-joinbyfield-2026-09-24 12_23_37.csv", "12h", "PV module back-sheet temperatures"),
    Panel("soil_temperature", "Temperature-data-as-joinbyfield-2026-09-24 12_15_26.csv", "12h", "Soil temperature (HD3910 probes)"),
    Panel("soil_vwc", "VWC-data-as-joinbyfield-2026-09-24 12_14_58.csv", "12h", "Soil volumetric water content (HD3910 probes)"),
    Panel("tracker_angle", "Tracking angles-data-as-joinbyfield-2026-09-24 12_24_35.csv", "12h", "Actual tracker tilt angles"),
    Panel("par", "ePAR (all parameters)-data-as-joinbyfield-2026-09-24 12_17_21.csv", "12h", "Extended PAR (SQ618), all channels"),
    Panel("wind_speed", "Wind speed-data-2026-09-24 12_19_26.csv", "12h", "Wind speed at the reference node"),
    Panel("relative_humidity", "Relative Humidity (ALL)-data-as-joinbyfield-2026-09-24 12_16_12.csv", "1D", "Relative humidity"),
    Panel("site_temperature", "Temperature-data-2026-09-24 12_25_18.csv", "1D", "Site daily air temperature"),
    Panel("site_wind_speed", "Wind speed-data-2026-09-24 12_25_29.csv", "1D", "Site daily average wind speed"),
    Panel("site_wind_direction", "Wind direction-data-2026-09-24 12_25_49.csv", "1D", "Site daily predominant wind direction"),
    Panel("precip_type", "-data-2026-09-24 12_17_49.csv", "30s", "WS100 precipitation type"),
    Panel("precip_wmo_wawa", "-data-2026-09-24 12_18_10.csv", "30s", "WS100 WMO 4680 (wawa) weather code"),
    Panel("precip_wmo_ww", "-data-2026-09-24 12_18_35.csv", "30s", "WS100 WMO 4677 (ww) weather code"),
    Panel("precip_cumulative", "Precipitation (Total & Difference cumulative sum)-data-2026-09-24 12_19_17.csv", "30s", "WS100 cumulative precipitation"),
    Panel("precip_intensity", "Precipitation-data-2026-09-24 12_19_00.csv", "30s", "WS100 precipitation intensity"),
)

# Files that duplicate information available elsewhere; not loaded.
REDUNDANT_FILES = {
    "Temperatures Weather station-data-as-joinbyfield-2026-09-24 12_21_40.csv": "subset of AIR Temperatures (ALL)",
    "ePAR (overview_ calibrated output)-data-as-joinbyfield-2026-09-24 12_16_29.csv": "same series as the cal_out channels in ePAR (all parameters)",
}

PANELS_BY_KEY = {p.key: p for p in PANELS}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    plot: str
    device: str | None
    quantity: str
    position: str | None
    sensor: str


_Z8AI_AIR = {"T": "air_temp", "RH": "rh", "dew_point": "dew_point", "WS": "wind_speed"}
_Z8AI_PYRA = {"GPOA": "gpoa", "ALBEDO": "albedo"}
_HD3910_QUANTITY = {"soil_temperature": "soil_temp", "soil_vwc": "vwc"}
_SINGLETONS = {
    "temp": ("SITE", "air_temp", "unknown"),
    "average_wind_speed": ("SITE", "wind_speed", "unknown"),
    "predominant_wind_direction": ("SITE", "wind_dir", "unknown"),
    "Precipitation Type": ("WS", "precip_type", "WS100"),
    "Precipitation WMO_wawa": ("WS", "wmo_wawa", "WS100"),
    "Precipitation WMO_ww": ("WS", "wmo_ww", "WS100"),
    "Precipitation Difference (Cumulative sum)": ("WS", "precip_cum", "WS100"),
    "Precipitation Intensity": ("WS", "precip_intensity", "WS100"),
}


def describe_column(raw: str, panel_key: str) -> ColumnInfo | None:
    """Canonical metadata for a raw series name, or None if it should be dropped."""

    def info(plot, quantity, sensor, device=None, position=None):
        name = "_".join(p for p in (plot, device, quantity, position) if p)
        return ColumnInfo(name, plot, device, quantity, position, sensor)

    if m := re.fullmatch(r"([RS]\d)d(\d+)_Z8AI\.air\.(T|RH|dew_point|WS)(?:__(\w+?))?\.(?:degC|pct|kmh)", raw):
        return info(m[1], _Z8AI_AIR[m[3]], "Z8AI", f"d{m[2]}", m[4])
    if m := re.fullmatch(r"([RS]\d)d(\d+)_Z8AI\.pyra\.(GPOA|ALBEDO)\.Wm2", raw):
        return info(m[1], _Z8AI_PYRA[m[3]], "pyranometer", f"d{m[2]}")
    if m := re.fullmatch(r"([RS]\d)d(\d+)_HD3910", raw):
        return info(m[1], _HD3910_QUANTITY[panel_key], "HD3910", f"d{m[2]}")
    if m := re.fullmatch(r"([RS]\d)d(\d+)_SQ618 (cal_out|cal_out_16bit|immersed|immersed_16bit)", raw):
        # immersed = 1.25 x cal_out; the 16-bit channels repeat cal_out at a
        # different resolution (and are broken on S1d20). Keep cal_out only.
        return info(m[1], "par", "SQ618", f"d{m[2]}") if m[3] == "cal_out" else None
    if m := re.fullmatch(r"WS100\.Air\.Temp(Act|Avg|Max|Min)\.degC", raw):
        return info("WS", "air_temp", "WS100", position=m[1].lower())
    if raw == "WS100.Heating.Temperature.degC":
        return info("WS", "heating_temp", "WS100")
    if m := re.fullmatch(r"(S\d) (T\d)", raw):
        return info(m[1], "pv_temp", "PV module sensor", position=m[2])
    if m := re.fullmatch(r"tracker_(M\d+) \(actual\)", raw):
        return info("TRK", "angle", "tracker controller", device=m[1])
    if raw in _SINGLETONS:
        plot, quantity, sensor = _SINGLETONS[raw]
        return info(plot, quantity, sensor)
    raise KeyError(f"unrecognised series {raw!r} in panel {panel_key!r}")
