"""Command-line entry point: uv run python -m ingest.cli --start 2024-01 --end 2024-03"""

import logging
from datetime import datetime

import duckdb
import httpx
import typer

from ingest import config
from ingest.download import download_file, trip_file_name, trip_file_url
from ingest.load import load_trips, load_zones

app = typer.Typer(help="Ingest NYC yellow taxi trip data into DuckDB.")
logger = logging.getLogger("ingest")


def month_range(start: str, end: str) -> list[tuple[int, int]]:
    """Turn '2024-11', '2025-02' into [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]."""
    try:
        first = datetime.strptime(start, "%Y-%m")
        last = datetime.strptime(end, "%Y-%m")
    except ValueError:
        raise typer.BadParameter("Months must look like YYYY-MM, e.g. 2024-01")
    if last < first:
        raise typer.BadParameter("--end must not be before --start")

    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


@app.command()
def run(
    start: str = typer.Option(..., help="First month to ingest, YYYY-MM"),
    end: str | None = typer.Option(
        None, help="Last month to ingest, YYYY-MM (defaults to --start)"
    ),
) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("httpx").setLevel(
        logging.WARNING
    )  # hide one log line per HTTP request
    months = month_range(start, end or start)

    config.DATA_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH))
    with httpx.Client(timeout=120, follow_redirects=True) as client, con:
        zones_csv = download_file(
            config.ZONE_LOOKUP_URL, config.RAW_DIR / "taxi_zone_lookup.csv", client
        )
        logger.info("Loaded %s taxi zones", load_zones(con, zones_csv))

        for year, month in months:
            dest = config.RAW_DIR / "yellow" / trip_file_name(year, month)
            try:
                download_file(trip_file_url(year, month), dest, client)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Could not download %d-%02d (HTTP %s). Is it published yet?",
                    year,
                    month,
                    exc.response.status_code,
                )
                raise typer.Exit(code=1)
            load_trips(con, dest, f"{year}-{month:02d}")

    logger.info("Done. Database: %s", config.DUCKDB_PATH)


if __name__ == "__main__":
    app()
