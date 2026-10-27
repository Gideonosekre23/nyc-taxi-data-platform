import duckdb
import pytest
import typer

from ingest.cli import month_range
from ingest.download import trip_file_url
from ingest.load import load_trips


def test_trip_file_url_pads_month():
    assert trip_file_url(2024, 3).endswith("/yellow_tripdata_2024-03.parquet")


def test_month_range_crosses_year_boundary():
    assert month_range("2024-11", "2025-02") == [
        (2024, 11),
        (2024, 12),
        (2025, 1),
        (2025, 2),
    ]


def test_month_range_rejects_end_before_start():
    with pytest.raises(typer.BadParameter):
        month_range("2024-05", "2024-01")


def test_load_trips_is_idempotent(tmp_path):
    # Build a tiny 3-row Parquet file instead of downloading the real 50 MB one.
    parquet = tmp_path / "trips.parquet"
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM (VALUES (1, 10.5), (2, 7.0), (1, 22.25)) t(VendorID, fare_amount)) "
        f"TO '{parquet.as_posix()}' (FORMAT parquet)"
    )

    load_trips(con, parquet, "2024-01")
    rows = load_trips(con, parquet, "2024-01")  # loading the same month twice

    assert rows == 3
    assert con.execute("SELECT count(*) FROM raw.yellow_trips").fetchone()[0] == 3
