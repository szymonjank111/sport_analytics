from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import cast

from sport_analytics.ingestion.http import USER_AGENT, build_session


class StubServer(ThreadingHTTPServer):
    """Answers each GET with the next of its statuses and keeps the User-Agent of each."""

    def __init__(self, *statuses: int) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.statuses = list(statuses)
        self.user_agents: list[str | None] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server = cast(StubServer, self.server)
        server.user_agents.append(self.headers["User-Agent"])
        self.send_response(server.statuses.pop(0))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serving(*statuses: int) -> Generator[StubServer]:
    with StubServer(*statuses) as server:
        # The interval is how often it checks for shutdown, which otherwise takes half a second.
        Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        try:
            yield server
        finally:
            server.shutdown()


def test_retries_a_passing_failure() -> None:
    with serving(503, 200) as server, build_session(backoff_factor=0) as session:
        response = session.get(server.url)

    assert response.status_code == 200
    assert server.user_agents == [USER_AGENT, USER_AGENT]


def test_gives_up_with_the_last_answer() -> None:
    with serving(*[503] * 6) as server, build_session(backoff_factor=0) as session:
        response = session.get(server.url)

    assert response.status_code == 503
    assert len(server.user_agents) == 6
