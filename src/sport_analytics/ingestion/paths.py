from dataclasses import dataclass
from datetime import date


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
