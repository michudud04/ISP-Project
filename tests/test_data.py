import numpy as np
import pandas as pd
import pytest

from agrivoltaics.data.catalog import describe_column
from agrivoltaics.data.cleaning import clean_sensors
from agrivoltaics.data.grafana import read_grafana_csv


def write_export(tmp_path, body: str):
    path = tmp_path / "panel.csv"
    path.write_text("﻿sep=,\n" + body, encoding="utf-8")
    return path


def test_units_are_parsed_per_value_and_converted(tmp_path):
    path = write_export(tmp_path, (
        '"Time","rain","wind"\n'
        "2025-07-01 02:00:00,920 µm,3.6 km/h\n"
        "2025-07-01 14:00:00,1.03 mm,\n"
    ))
    gf = read_grafana_csv(path)
    assert gf.units == {"rain": "mm", "wind": "m/s"}
    np.testing.assert_allclose(gf.data["rain"], [0.92, 1.03])
    assert gf.data["wind"].iloc[0] == pytest.approx(1.0)
    assert np.isnan(gf.data["wind"].iloc[1])


def test_local_time_becomes_utc_across_dst(tmp_path):
    path = write_export(tmp_path, (
        '"Time","t"\n'
        "2025-07-01 02:00:00,1 °C\n"   # CEST
        "2025-10-26 02:00:00,1 °C\n"   # ambiguous fall-back hour, single stamp
        "2025-12-01 01:00:00,1 °C\n"   # CET
    ))
    idx = read_grafana_csv(path).data.index
    assert str(idx.tz) == "UTC"
    assert list(idx.strftime("%Y-%m-%d %H:%M")) == ["2025-07-01 00:00", "2025-10-26 00:00", "2025-12-01 00:00"]


def test_identical_duplicate_columns_and_rows_are_dropped(tmp_path):
    path = write_export(tmp_path, (
        '"Time","a","a"\n'
        "2025-07-01 02:00:00,1 %,1 %\n"
        "2025-07-01 02:00:00,1 %,1 %\n"
    ))
    gf = read_grafana_csv(path)
    assert list(gf.data.columns) == ["a"]
    assert gf.dropped_duplicates == ["a.1"]
    assert len(gf.data) == 1


def test_text_columns_stay_categorical(tmp_path):
    path = write_export(tmp_path, '"Time","kind"\n2025-07-01 02:00:00,No precipitation\n')
    gf = read_grafana_csv(path)
    assert gf.data["kind"].dtype == "category"
    assert gf.units["kind"] == ""


def test_unknown_unit_fails_loudly(tmp_path):
    path = write_export(tmp_path, '"Time","x"\n2025-07-01 02:00:00,3 furlongs\n')
    with pytest.raises(ValueError, match="unknown unit"):
        read_grafana_csv(path)


@pytest.mark.parametrize("raw, panel, expected", [
    ("S1d10_Z8AI.air.T__center.degC", "air_temperature", "S1_d10_air_temp_center"),
    ("R1d40_Z8AI.air.WS.kmh", "wind_speed", "R1_d40_wind_speed"),
    ("S2d30_Z8AI.pyra.GPOA.Wm2", "irradiance", "S2_d30_gpoa"),
    ("R1d41_HD3910", "soil_vwc", "R1_d41_vwc"),
    ("R1d41_HD3910", "soil_temperature", "R1_d41_soil_temp"),
    ("S1d19_SQ618 cal_out", "par", "S1_d19_par"),
    ("WS100.Air.TempMax.degC", "air_temperature", "WS_air_temp_max"),
    ("S2 T3", "pv_temperature", "S2_pv_temp_T3"),
    ("tracker_M07 (actual)", "tracker_angle", "TRK_M07_angle"),
])
def test_canonical_names(raw, panel, expected):
    assert describe_column(raw, panel).name == expected


def test_redundant_and_unknown_series():
    assert describe_column("S1d19_SQ618 immersed", "par") is None
    with pytest.raises(KeyError):
        describe_column("S9 mystery", "par")


def test_par_zeros_while_pyranometer_runs_are_removed():
    df = pd.DataFrame({"S1_d12_gpoa": [400.0, 410.0, 390.0, 405.0], "R1_d45_par": [800.0, 820.0, 0.0, 60.0]})
    meta = pd.DataFrame({"quantity": ["gpoa", "par"], "plot": ["S1", "R1"]}, index=df.columns)
    cleaned, _ = clean_sensors(df, meta)
    assert cleaned["R1_d45_par"].isna().tolist() == [False, False, True, True]
    assert cleaned["S1_d12_gpoa"].notna().all()


def test_pv_sensor_deviating_from_siblings_is_removed():
    df = pd.DataFrame({f"S2_pv_temp_T{i}": [30.0, 31.0] for i in range(1, 5)})
    df.loc[1, "S2_pv_temp_T1"] = 95.0
    meta = pd.DataFrame({"quantity": "pv_temp", "plot": "S2"}, index=df.columns)
    cleaned, log = clean_sensors(df, meta)
    assert np.isnan(cleaned.loc[1, "S2_pv_temp_T1"])
    assert cleaned.loc[0, "S2_pv_temp_T1"] == 30.0
    assert log["n"].sum() == 1
