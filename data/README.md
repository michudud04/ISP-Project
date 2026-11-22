# Data dictionary

## Source

`raw/grafana_export_2026-09-24/` holds 20 CSV files downloaded from Grafana panels
(Inspect → Data → Download CSV) on 2026-09-24. They are the original files and should not be
edited; `scripts/make_dataset.py` turns them into `processed/`.

| File (export timestamp omitted) | Dataset key | Resolution | Content |
|---|---|---|---|
| AIR Temperatures (ALL) | `air_temperature` | 12 h | Air temperature, Z8AI nodes + WS100 |
| Dew Point | `dew_point` | 12 h | Dew point, Z8AI nodes |
| Irradiance | `irradiance` | 12 h | Plane-of-array (GPOA) and albedo pyranometers |
| PV panel temperatures | `pv_temperature` | 12 h | Module temperatures, 4 per section |
| Temperature (joinbyfield) | `soil_temperature` | 12 h | Soil temperature, HD3910 probes |
| VWC | `soil_vwc` | 12 h | Soil volumetric water content, HD3910 probes |
| Tracking angles | `tracker_angle` | 12 h | Actual tilt of trackers M01–M10 |
| ePAR (all parameters) | `par` | 12 h | SQ618 extended-PAR sensors (only `cal_out` kept) |
| Wind speed (12_19_26) | `wind_speed` | 12 h | Wind speed at the R1 node |
| Relative Humidity (ALL) | `relative_humidity` | daily | RH, Z8AI nodes |
| Temperature (12_25_18) | `site_temperature` | daily | Site air temperature (source system unknown) |
| Wind speed (12_25_29) | `site_wind_speed` | daily | Site average wind speed |
| Wind direction | `site_wind_direction` | daily | Site predominant wind direction |
| `-data-… 12_17_49` | `precip_type` | 30 s | WS100 precipitation type (text) |
| `-data-… 12_18_10` | `precip_wmo_wawa` | 30 s | WS100 WMO 4680 weather code (text) |
| `-data-… 12_18_35` | `precip_wmo_ww` | 30 s | WS100 WMO 4677 weather code (text) |
| Precipitation (Total & Difference cumulative sum) | `precip_cumulative` | 30 s | Cumulative precipitation |
| Precipitation | `precip_intensity` | 30 s | Precipitation intensity |
| Temperatures Weather station | — | — | *not loaded:* subset of AIR Temperatures (ALL) |
| ePAR (overview_ calibrated output) | — | — | *not loaded:* same as `cal_out` in ePAR (all parameters) |

The mapping lives in `src/agrivoltaics/data/catalog.py`. A new export needs its filenames updated
there. Any series the catalog does not recognise raises an error rather than being dropped.

## Sites and sensors

| Code | Meaning |
|---|---|
| `R1` | Open-field reference plot (no PV). Inferred: it receives ~1.6× the light of S1/S2. |
| `S1`, `S2` | Crop beds under the single-axis PV trackers |
| `WS` | Lufft WS100 radar precipitation sensor with air temperature |
| `TRK` | Trackers M01–M10 (tilt angle; negative = facing east) |
| `SITE` | Daily site weather summary, source system unknown |
| `dNN` | Device number within a plot, e.g. `S1_d13` |

Sensor models: **Z8AI** nodes (air temperature, RH, dew point, wind; plus pyranometers on d12/d30),
**HD3910** soil probes (VWC + temperature), **SQ618** extended-PAR sensors (380–760 nm),
**WS100** precipitation sensor.

## Canonical column names

`{plot}_{device}_{quantity}[_{position}]`, e.g. `S1_d10_air_temp_center`, `R1_d45_par`,
`S2_pv_temp_T3`, `TRK_M07_angle`, `WS_air_temp_avg`. Units are canonical per quantity:

| Quantity | Unit | Quantity | Unit |
|---|---|---|---|
| `air_temp`, `dew_point`, `soil_temp`, `pv_temp`, `heating_temp` | °C | `vwc`, `rh` | % |
| `gpoa`, `albedo` | W/m² | `par` | µmol/m²/s |
| `wind_speed` | m/s (converted from km/h) | `wind_dir`, `angle` | ° |
| `precip_cum`, `precip_mm` | mm | `precip_intensity` | mm/h |

## Export quirks handled by the parser

- **12 h means.** Buckets run 00–12 and 12–24 UTC. Daily totals and means are exact; the diurnal
  cycle is lost. Grafana averages whatever samples a bucket holds, so a logger outage can leave
  a bucket with only midday samples and an impossibly high mean.
- **Local timestamps with DST.** CET/CEST in the file, converted to UTC.
- **Units inside the values.** Each value reads `"23.0 °C"`, and Grafana rescales some units
  per value: cumulative precipitation switches between `µm` and `mm`. Units are therefore parsed
  row by row.
- **Duplicates.** Two series appear twice within their panel; 10 rows are duplicated in each 30 s file.
- **Files starting with `-`.** Three filenames begin with a dash, so prefix them with `./` in shell commands.

## Processed outputs (`processed/`)

| File | Content |
|---|---|
| `sensors_12h.parquet` | All 12 h series after QC, UTC index, 2025-05-22 → 2026-09-24 |
| `daily.parquet` | Daily means of the 12 h series (days with both buckets only), daily-only series, precipitation totals and minutes by precipitation type, WS100 data coverage |
| `precip_30s.parquet` | Raw 30 s WS100 stream plus per-sample precipitation increments (`WS_precip_mm`) |
| `sensors_meta.csv` | One row per column: plot, device, quantity, position, unit, sensor model, source panel, first/last valid timestamp, suspect flag |
| `qc_log.csv` | Every QC rule that changed values: column, rule, action, count |

## Quality control (`src/agrivoltaics/data/cleaning.py`)

| Rule | Applies to |
|---|---|
| 12 h mean ≈ 0 → removed (every bucket contains daylight) | POA irradiance, PAR |
| 12 h mean above clear-sky ceiling (600 W/m², 1200 µmol/m²/s, albedo 100 W/m²) → removed | radiation |
| PAR / POA ratio < 25 % of its median → removed (PAR logger outage) | PAR |
| Small negative offset (> −5) → clipped to 0 | albedo, wind speed |
| VWC < 1 % → removed (dropout) | soil moisture |
| Exactly 0.0 °C → removed (dropout) | soil temperature |
| > 10 K from the median of the other module sensors in the same section → removed | PV module temperature |

Suspect sensors are kept in the data but excluded from plot-level means: `S1_d20_par`
(erratic relative to its neighbours; its 16-bit channel is also broken).
