"""Load raw files into DuckDB's `raw` schema."""

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


def load_trips(
    con: duckdb.DuckDBPyConnection, parquet_path: Path, source_month: str
) -> int:
    """Load one month of trips into raw.yellow_trips. Safe to re-run for the same month."""
    path = str(parquet_path)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    # Create the table from the file's own schema (LIMIT 0 = columns only, no rows).
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.yellow_trips AS
        SELECT *, ?::VARCHAR AS source_month, current_timestamp AS ingested_at
        FROM read_parquet(?)
        LIMIT 0
        """,
        [source_month, path],
    )

    # Delete-then-insert inside one transaction: re-running a month replaces it instead of duplicating it.
    con.begin()
    try:
        con.execute(
            "DELETE FROM raw.yellow_trips WHERE source_month = ?", [source_month]
        )
        con.execute(
            """
            INSERT INTO raw.yellow_trips BY NAME
            SELECT *, ? AS source_month, current_timestamp AS ingested_at
            FROM read_parquet(?)
            """,
            [source_month, path],
        )
        con.commit()
    except Exception:
        con.rollback()
        raise

    row_count = con.execute(
        "SELECT count(*) FROM raw.yellow_trips WHERE source_month = ?", [source_month]
    ).fetchone()[0]
    logger.info("Loaded %s rows for %s", f"{row_count:,}", source_month)
    return row_count


def load_zones(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Replace raw.taxi_zones with the contents of the zone lookup CSV."""
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        "CREATE OR REPLACE TABLE raw.taxi_zones AS SELECT * FROM read_csv(?, header = true)",
        [str(csv_path)],
    )
    return con.execute("SELECT count(*) FROM raw.taxi_zones").fetchone()[0]
