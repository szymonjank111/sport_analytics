import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from google.cloud import bigquery

from sport_analytics.ingestion.errors import NothingToLoadError
from sport_analytics.ingestion.paths import parse_raw_path, run_prefix
from sport_analytics.ingestion.sources.football_data import split_matches
from sport_analytics.ingestion.storage import Storage

logger = logging.getLogger(__name__)

RAW_SCHEMA = [
    bigquery.SchemaField("_run_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("_competition", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_season", "INT64"),
    bigquery.SchemaField("_gcs_uri", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("payload", "JSON", mode="REQUIRED", description="One source record."),
]


@dataclass(frozen=True, slots=True)
class RawEntity:
    source: str
    entity: str
    split: Callable[[bytes], list[dict[str, Any]]]
    """Splits a raw file into the records of the source."""

    @property
    def table(self) -> str:
        return f"{self.source}__{self.entity}"


FOOTBALL_DATA_MATCHES = RawEntity("football_data", "matches", split_matches)


def build_rows(
    storage: Storage, entity: RawEntity, run_date: date, loaded_at: datetime
) -> list[dict[str, Any]]:
    """One row for each record in the files of the entity from the run."""
    prefix = run_prefix(entity.source, run_date)
    files = [parse_raw_path(path) for path in storage.list_paths(prefix)]
    files = [raw for raw in files if raw.entity == entity.entity]
    if not files:
        # Loading nothing would still truncate the partition, wiping what the run loaded before.
        raise NothingToLoadError(f"no {entity.entity} files under {prefix}")
    return [
        {
            "_run_date": run_date.isoformat(),
            "_competition": raw.competition,
            "_season": raw.season,
            "_gcs_uri": storage.uri(raw.path),
            "_loaded_at": loaded_at.isoformat(),
            # A dict, not a JSON string: a string would load as a JSON scalar.
            "payload": record,
        }
        for raw in files
        for record in entity.split(storage.read(raw.path))
    ]


class Warehouse(Protocol):
    def load_partition(self, entity: RawEntity, run_date: date, rows: list[dict[str, Any]]) -> None:
        """Replaces the partition of the run in the raw table of the entity with the rows."""
        ...


class BigQueryWarehouse:
    def __init__(self, client: bigquery.Client, dataset: str) -> None:
        self._client = client
        self._dataset = dataset

    def load_partition(self, entity: RawEntity, run_date: date, rows: list[dict[str, Any]]) -> None:
        table_id = f"{self._client.project}.{self._dataset}.{entity.table}"
        table = bigquery.Table(table_id, schema=RAW_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(field="_run_date")
        table.clustering_fields = ["_competition"]
        self._client.create_table(table, exists_ok=True)
        # The decorator narrows WRITE_TRUNCATE to the partition of the run, so a rerun replaces it.
        job_config = bigquery.LoadJobConfig(
            schema=RAW_SCHEMA, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        self._client.load_table_from_json(
            rows, f"{table_id}${run_date:%Y%m%d}", job_config=job_config
        ).result()
        logger.info("loaded table=%s run_date=%s rows=%d", entity.table, run_date, len(rows))
