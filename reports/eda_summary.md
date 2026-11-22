# EDA summary — agrivoltaic farm sensor export (2026-09-24)

Source: [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb), run on the processed data in `data/processed/`.
All figures are in [figures/](figures/).

| Figure | Shows |
|---|---|
| [01_coverage](figures/01_coverage.png) | When each sensor reported |
| [02_quality_examples](figures/02_quality_examples.png) | Drifting PV sensor; PAR logger outages |
| [03_weather](figures/03_weather.png) | Daily air temperature, monthly precipitation |
| [04_light](figures/04_light.png) | Daily light integral and light transmission under PV |
| [05_soil_moisture](figures/05_soil_moisture.png) | Soil moisture per plot vs rainfall |
| [06_soil_temperature](figures/06_soil_temperature.png) | Soil temperature under PV minus reference |
| [07_air_microclimate](figures/07_air_microclimate.png) | Air temperature and humidity differences |
| [08_pv_thermal](figures/08_pv_thermal.png) | Module temperature above ambient vs irradiance |
| [09_trackers](figures/09_trackers.png) | Tracker schedule and deviations |
| [10_correlations](figures/10_correlations.png) | Correlations between daily variables |

## Key findings

### About the data

- **About 15 months of usable data.** The export window starts on 2024-09-24, but sensors only
  come online in late April 2025 (trackers, site weather) and on 2025-06-18 (most field sensors).
  All four R1 soil probes report from 2025-10-08. Soil moisture ends around 2026-09-07; the
  tracker and site-weather feeds end on 2026-09-02.
- **Coarse resolution.** Everything except precipitation is a 12 h mean. Daily totals are exact,
  but the diurnal cycle is not visible.
- **Sensor faults are common.** QC removed or clipped ~500 values. The lasting problems:
  `S2_pv_temp_T1` drifts for weeks; `S1_d20_par` is erratic (excluded from plot means); the PAR
  logger had two outages that reported zeros; soil probes `S1_d17` and `S1_d16` stop in January
  and May 2026.
- **Overlapping sources agree.** Three air-temperature sources correlate at r ≥ 0.997 (WS100
  reads ~0.7 K cooler than the other two). The precipitation counter and integrated intensity
  give 578 vs 548 mm, daily r = 0.99.
- **Weather.** 578 mm of precipitation from mid-June 2025 to late September 2026 (wettest month
  December 2025 with 112 mm; July + August 2026 only 8 mm); ~400 h of rain and ~4 h of snow or
  sleet; prevailing wind from S–SE.

### Agrivoltaic effects (under PV vs open field)

- **Light.** Crops under the panels receive **63–64 % of the open-field daily light integral**
  (monthly 58–73 %), with the higher shares in winter and in September 2026. Individual
  under-panel sensors range from 60 % to 69 % depending on position.
- **Soil temperature.** Under-panel soil is **1–2.5 K cooler in summer** and about the same in
  winter (S2 up to 0.7 K *warmer* in November–December): the panels damp both daytime heating
  and night-time cooling.
- **Soil moisture has no single direction.** S1 is 4–6 points wetter than R1 through winter
  2025/26 and S2 is within ±2 points. In the June 2026 dry-down S1 dried fastest (about 15 %
  vs 21 % in R1). Differences between probes in the same plot (19–31 %) are as large as those
  between plots, so probe position relative to the panel rows matters.
- **Probable irrigation that is not in the data.** From late June to early September 2026 soil
  moisture rises by 7–11 points in every plot, while only ~8 mm of rain fell.
- **Air.** S1 reads 0.3 K warmer than R1 and S2 0.1 K; dew point is identical, and the RH
  differences (−1.2 / +0.2 points) follow from temperature. Offsets this small are within sensor
  tolerance, so a side-by-side calibration check is needed before attributing them to the panels.

### Energy side

- **Module temperature** rises 1.7–2.0 K above ambient per 100 W/m² of 12 h-mean plane-of-array
  irradiance (r = 0.81 for S1, 0.93 for S2). A handful of S1 points sit 13–25 K above ambient and
  should be checked.
- **Plane-of-array insolation** is about 10 kWh/m²/day in June and about 2 in December.
- **Trackers** follow one schedule except twice: during commissioning (23 May–17 Jun 2025, two
  groups about ±30° apart) and on **21 May–4 Jun 2026**, when M01–05, M06–08 and M09–10 held
  different angles. The 2026 split looks like a deliberate strategy trial; worth asking the operator.
- **No PV electrical output** (power, energy, inverter status) is in the export.

### What this means for the intelligent system

1. **Get finer data.** Re-export at 15 min or less, or query the database behind Grafana
   directly. Irrigation detection, heat-stress and frost alerts, and tracker decisions all need
   the diurnal cycle.
2. **Request the missing streams:** PV power and energy, the irrigation log, the crop and
   management calendar (species, sowing, harvest, yield), and tracker setpoints/modes.
3. **Keep QC in the pipeline.** At least five sensors and the PAR logger had multi-week faults in
   15 months; a sensor-health monitor would be useful to the site operator in its own right.
4. **The sample is small** (~400–450 paired days). Start with interpretable, physics-informed
   features (DLI, light transmission, soil water balance, module temperature model) rather
   than data-hungry models.
