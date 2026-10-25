"""Drops the datasets of a CI run: its target dataset and those dbt adds a layer suffix to.

The dbt job of CI calls it at the end, whether the build passed or not:

    uv run python scripts/drop_ci_datasets.py ci_1234567890
"""

import argparse
from collections.abc import Iterable
from typing import Any, cast

from google.cloud import bigquery

from sport_analytics.settings import GcpSettings


def run_datasets(datasets: Iterable[str], run_dataset: str) -> list[str]:
    # An exact match on the run, so that ci_12 never takes ci_123_staging of another run along.
    return [name for name in datasets if name == run_dataset or name.startswith(f"{run_dataset}_")]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("run_dataset", help="target dataset of the run, such as ci_1234567890")
    args = parser.parse_args()
    if not args.run_dataset.startswith("ci_"):
        parser.error("only datasets of CI runs, which start with ci_, may be dropped")
    # Fields are read from the environment, which pyright cannot see.
    settings = GcpSettings()  # pyright: ignore[reportCallIssue]
    client = bigquery.Client(project=settings.gcp_project_id, location=settings.gcp_location)
    # It yields DatasetListItem, whose properties declare no types.
    datasets = cast(Iterable[Any], client.list_datasets())
    names: list[str] = [dataset.dataset_id for dataset in datasets]
    for name in run_datasets(names, args.run_dataset):
        client.delete_dataset(name, delete_contents=True, not_found_ok=True)
        print(f"dropped dataset={name}")


if __name__ == "__main__":
    main()
