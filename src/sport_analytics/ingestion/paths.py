import re
from dataclasses import dataclass
from datetime import date

_RAW_PATH = re.compile(
    r"raw/source=(?P<source>\w+)/run_date=(?P<run_date>\d{4}-\d{2}-\d{2})"
    r"/competition=(?P<competition>\w+)(?:/season=(?P<season>\d{4}))?"
    r"/(?P<entity>\w+)\.(?P<extension>\w+)"
)


@dataclass(frozen=True, slots=True)
class RawObject:
    """A file in the raw layer, as one run of the source sent it."""

    source: str
    run_date: date
    competition: str
    """Native code of the source, such as PL."""
    season: int | None
    """Start year; None for files that span many seasons."""
    entity: str
    extension: str

    @property
    def path(self) -> str:
        season = "" if self.season is None else f"season={self.season}/"
        return (
            f"{run_prefix(self.source, self.run_date)}competition={self.competition}/"
            f"{season}{self.entity}.{self.extension}"
        )


def run_prefix(source: str, run_date: date) -> str:
    """Where all files of one run are, so a load lists a single prefix."""
    return f"raw/source={source}/run_date={run_date.isoformat()}/"


def parse_raw_path(path: str) -> RawObject:
    match = _RAW_PATH.fullmatch(path)
    if match is None:
        raise ValueError(f"not a raw path: {path}")
    season = match["season"]
    return RawObject(
        source=match["source"],
        run_date=date.fromisoformat(match["run_date"]),
        competition=match["competition"],
        season=None if season is None else int(season),
        entity=match["entity"],
        extension=match["extension"],
    )
