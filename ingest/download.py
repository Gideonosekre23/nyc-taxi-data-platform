# download raw files fron nyc tlc site

import logging
from pathlib import Path

import httpx

from ingest.config import TLC_BASE_URL

logger = logging.getLogger(__name__)


def trip_file_name(year: int, month: int) -> str:
    return f"yellow_tripdata_{year}-{month:02d}.parquet"


def trip_file_url(year: int, month: int) -> str:
    return f"{TLC_BASE_URL}/{trip_file_name(year, month)}"


def download_file(url: str, dest: Path, client: httpx.Client) -> Path:
    """Download url to dest. Skips the download if dest already exists."""
    if dest.exists():
        logger.info("Skipping %s (already downloaded)", dest.name)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary .part file first, so a crash never leaves a half-written file behind.
    tmp = dest.with_suffix(dest.suffix + ".part")

    logger.info("Downloading %s", url)
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)

    tmp.replace(dest)
    return dest
