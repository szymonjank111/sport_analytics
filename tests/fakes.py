from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import requests
from requests import PreparedRequest, Response
from requests.adapters import BaseAdapter

from sport_analytics.ingestion.loader import RawEntity
from sport_analytics.ingestion.rate_limit import RateLimiter
from sport_analytics.ingestion.sources.football_data import FootballDataClient

FIXTURES = Path(__file__).parent / "fixtures"
PL_MATCHES = (FIXTURES / "football_data/matches_PL_2026.json").read_bytes()
"""An answer of football-data.org for the 2026 Premier League, cut down to three matches."""
CL_MATCHES = (FIXTURES / "football_data/matches_CL_2026.json").read_bytes()
"""The same for the Champions League: the league stage, a knockout tie and the final."""


class InMemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        """Data and content type by path."""

    def write(self, path: str, data: bytes, content_type: str) -> None:
        self.objects[path] = (data, content_type)

    def read(self, path: str) -> bytes:
        return self.objects[path][0]

    def list_paths(self, prefix: str) -> list[str]:
        return sorted(path for path in self.objects if path.startswith(prefix))

    def uri(self, path: str) -> str:
        return f"memory://{path}"


class FakeWarehouse:
    def __init__(self) -> None:
        self.partitions: dict[tuple[str, date], list[dict[str, Any]]] = {}
        """Rows by table and run date."""

    def load_partition(self, entity: RawEntity, run_date: date, rows: list[dict[str, Any]]) -> None:
        self.partitions[entity.table, run_date] = rows


class FakeAdapter(BaseAdapter):
    """Answers each request with the next of the given responses and keeps the requests.

    A response is a status and a body, with headers or without, or an exception, which the
    request then raises, as for a network failure.
    """

    def __init__(
        self, *responses: tuple[int, bytes] | tuple[int, bytes, dict[str, str]] | Exception
    ) -> None:
        super().__init__()
        self.responses = list(responses)
        self.requests: list[PreparedRequest] = []

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        verify: bool | str = True,
        cert: bytes | str | tuple[bytes | str, bytes | str] | None = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        self.requests.append(request)
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status_code, body, *headers = answer
        response = Response()
        response.status_code = status_code
        for header in headers:
            response.headers.update(header)
        response._content = body  # pyright: ignore[reportPrivateUsage]  # It has no public setter.
        response.request = request
        return response

    def close(self) -> None:
        pass


class FakeClock:
    """A monotonic clock whose sleeps only move it forward, and are kept."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def session_with(adapter: FakeAdapter) -> requests.Session:
    session = requests.Session()
    session.mount("https://", adapter)
    return session


def football_data_client(
    adapter: FakeAdapter, limiter: RateLimiter | None = None
) -> FootballDataClient:
    """A client of the fake answers, by default not limited."""
    return FootballDataClient("secret", session_with(adapter), limiter or RateLimiter(0))
