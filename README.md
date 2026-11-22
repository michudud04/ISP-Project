# Agrivoltaic farm — intelligent decision support

An intelligent system that helps the different stakeholders of an agrivoltaic farm (farmer /
agronomist, PV operator, researchers, landowner) understand and manage the trade-off between
crop production and solar energy on the same land.

Current status: **data ingestion, quality control and exploratory analysis**. See
[reports/eda_summary.md](reports/eda_summary.md) for what the data shows so far.

## Project layout

```
├── data/
│   ├── raw/grafana_export_2026-09-24/   original Grafana CSV exports (never edited)
│   ├── interim/                         scratch outputs (git-ignored)
│   ├── processed/                       cleaned parquet tables, rebuilt by scripts/make_dataset.py (git-ignored)
│   └── README.md                        data dictionary: sensors, naming, export quirks, QC rules
├── notebooks/
│   └── 01_eda.ipynb                     exploratory data analysis
├── reports/
│   ├── eda_summary.md                   key findings
│   └── figures/                         figures written by the notebooks
├── scripts/
│   └── make_dataset.py                  raw export -> data/processed/
├── src/agrivoltaics/
│   ├── config.py                        paths, timezone, plot codes
│   ├── data/                            Grafana parser, sensor catalog, QC rules, dataset builder
│   ├── features/                        derived indicators (DLI, plot means, daily aggregation)
│   ├── models/                          forecasting / anomaly detection / optimisation (not started)
│   ├── stakeholders/                    role-specific decision logic and reports (not started)
│   └── viz/                             shared plotting style
├── tests/                               pytest suite for parsing, naming and QC
└── pyproject.toml
```

## Setup

Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate elsewhere)
pip install -e ".[dev]"
python -m ipykernel install --sys-prefix --name agrivoltaics --display-name "Python (agrivoltaics)"
```

## Workflow

```bash
python scripts/make_dataset.py    # parse + clean the raw export -> data/processed/ (~30 s)
pytest                            # parser / catalog / QC tests
python -m nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb   # re-run the EDA
```

In VS Code, open the notebook and pick the `.venv` interpreter (or the "Python (agrivoltaics)" kernel).
Use `python -m nbconvert` rather than `jupyter nbconvert`, so the venv's own nbconvert runs even if
another Jupyter install is earlier on PATH.

## Data at a glance

The raw data is a Grafana export from 2026-09-24. Most series are **12-hour means** covering
mid-2025 to September 2026; precipitation is at 30 s resolution. Sensors sit in an open-field
reference plot (`R1`) and two crop beds under single-axis PV trackers (`S1`, `S2`). Details,
caveats and the QC rules are in [data/README.md](data/README.md).
