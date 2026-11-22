"""Project-wide paths and constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "grafana_export_2026-09-24"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"

# Grafana renders timestamps in the browser's local time. The 12 h buckets sit at
# 01:00/13:00 in winter and 02:00/14:00 in summer, i.e. 00:00/12:00 UTC under
# CET/CEST rules. Any EU zone that follows CET/CEST gives identical results.
EXPORT_TZ = "Europe/Berlin"

# Plot codes used in sensor names (meaning inferred from the data: R1 receives
# roughly twice the PAR of S1/S2, so it is the unshaded reference).
PLOTS = {
    "R1": "Reference plot (open field, no PV)",
    "S1": "Agrivoltaic section 1 (under trackers)",
    "S2": "Agrivoltaic section 2 (under trackers)",
    "WS": "WS100 weather station (precipitation radar + air temperature)",
    "TRK": "PV single-axis trackers M01-M10",
    "SITE": "Site-level daily weather summary (source system unknown)",
}
