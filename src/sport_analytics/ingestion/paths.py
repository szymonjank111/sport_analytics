import re
from dataclasses import dataclass
from datetime import date

PRIVATE_SOURCES = frozenset({"football_data_co_uk", "understat"})
"""Sources whose terms allow private use only, or which ask robots to stay away, so their files
stay apart, under raw_private/."""

_RAW_PATH = re.compile(
    r"raw(?:_private)?/source=(?P<source>\w+)/run_date=(?P<run_date>\d{4}-\d{2}-\d{2})"
    r"/competition=(?P<competition>\w+)(?:/season=(?P<season>\d{4}))?"
    r"(?:/match=(?P<match_id>\d+))?"
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
    match_id: int | None = None
    """Source ID of the match, for files of a single match."""

    @property
    def path(self) -> str:
        season = "" if self.season is None else f"season={self.season}/"
        match = "" if self.match_id is None else f"match={self.match_id}/"
        return (
            f"{run_prefix(self.source, self.run_date)}competition={self.competition}/"
            f"{season}{match}{self.entity}.{self.extension}"
        )


def source_prefix(source: str) -> str:
    root = "raw_private" if source in PRIVATE_SOURCES else "raw"
    return f"{root}/source={source}/"


def run_prefix(source: str, run_date: date) -> str:
    """Where all files of one run are, so a load lists a single prefix."""
    return f"{source_prefix(source)}run_date={run_date.isoformat()}/"


def parse_raw_path(path: str) -> RawObject:
    match = _RAW_PATH.fullmatch(path)
    if match is None:
        raise ValueError(f"not a raw path: {path}")
    season = match["season"]
    match_id = match["match_id"]
    raw = RawObject(
        source=match["source"],
        run_date=date.fromisoformat(match["run_date"]),
        competition=match["competition"],
        season=None if season is None else int(season),
        entity=match["entity"],
        extension=match["extension"],
        match_id=None if match_id is None else int(match_id),
    )
    # The round trip also catches a source under the wrong root, such as a private one in raw/.
    if raw.path != path:
        raise ValueError(f"not a raw path: {path}")
    return raw
