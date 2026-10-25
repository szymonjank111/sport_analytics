import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

USER_AGENT = "sport-analytics/0.1 (+https://github.com/szymonjank111/sport_analytics)"
TIMEOUT = (5, 30)
"""Seconds to connect and to wait for each read."""
NETWORK_ERRORS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
"""What the source or the network is to blame for; a bad header or URL is a fault of the setup."""


def build_session(backoff_factor: float = 2.0) -> requests.Session:
    """A session that retries GETs failed for a passing reason: the network or an outage."""
    retry = Retry(
        total=5,
        backoff_factor=backoff_factor,
        # Not 429: the source sends no Retry-After, so a retry would spend more of the quota
        # while it is used up. The rate limiter keeps clear of it.
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        # A 503 may ask to wait for hours; failing within minutes says more.
        retry_after_max=60,
        # The last answer is returned instead, so the client can tell what the source said.
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session
