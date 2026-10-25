"""Proposes canonical teams for the source teams that the seeds do not map yet.

Prints CSV rows to review and then copy into dbt/seeds/teams.csv and team_mapping.csv:

    uv run python scripts/propose_team_mapping.py dbt_szymon_intermediate > proposals.csv
"""

import argparse
import csv
import re
import sys
import unicodedata
from collections.abc import Iterable
from typing import cast

from google.cloud import bigquery

from sport_analytics.settings import GcpSettings

CLUB_AFFIXES = frozenset({"fc", "afc", "cf"})


def canonical_name(source_name: str) -> str:
    return " ".join(word for word in source_name.split() if word.lower() not in CLUB_AFFIXES)


def slug(name: str) -> str:
    # NFKD splits accents off letters, but the Polish ł has no such decomposition.
    decomposed = unicodedata.normalize("NFKD", name.translate(str.maketrans("łŁ", "lL")))
    ascii_name = decomposed.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "dataset", help="dataset of the intermediate models, such as dbt_szymon_intermediate"
    )
    args = parser.parse_args()
    # Fields are read from the environment, which pyright cannot see.
    settings = GcpSettings()  # pyright: ignore[reportCallIssue]
    client = bigquery.Client(project=settings.gcp_project_id, location=settings.gcp_location)
    # A dataset name cannot be a query parameter; this one is typed by the person running it.
    query = client.query(
        f"""
        select source, team_key, team_name, country
        from `{settings.gcp_project_id}.{args.dataset}.int_unmapped_teams`
        order by source, team_name
        """
    )
    # The iterator of query results declares no item type.
    rows = cast(Iterable[bigquery.Row], query.result())
    writer = csv.writer(sys.stdout)
    writer.writerow(["source", "source_team_key", "team_id", "name", "country"])
    for row in rows:
        # get() is the typed way to read a field; the selected fields are all there.
        name = canonical_name(row.get("team_name"))
        writer.writerow(
            [row.get("source"), row.get("team_key"), slug(name), name, row.get("country")]
        )


if __name__ == "__main__":
    main()
