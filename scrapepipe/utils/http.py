import random
import time
from typing import Callable

import requests

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_DEFAULT_MAX_RETRIES = 4
_DEFAULT_BASE_DELAY = 2.0
_DEFAULT_MAX_DELAY = 60.0


class RateLimitedError(Exception):
    def __init__(self, url: str, attempts: int, last_status: int) -> None:
        super().__init__(
            f"Rate-limited after {attempts} attempt(s) on {url} "
            f"(last status: {last_status})."
        )
        self.url = url
        self.attempts = attempts
        self.last_status = last_status


def get_with_retry(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = 15,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    on_retry: Callable[[int, float, int], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET with exponential-backoff retry on 429 and 5xx responses.

    Honors the ``Retry-After`` header when present. Raises
    :class:`RateLimitedError` if all retries are exhausted on a 429.
    """
    last_status = 0
    for attempt in range(max_retries + 1):
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        last_status = response.status_code

        if response.status_code not in _RETRY_STATUS_CODES:
            return response

        if attempt >= max_retries:
            if response.status_code == 429:
                raise RateLimitedError(url, attempt + 1, last_status)
            return response

        delay = _compute_delay(
            response, attempt, base_delay=base_delay, max_delay=max_delay
        )
        if on_retry:
            on_retry(attempt + 1, delay, response.status_code)
        sleep_fn(delay)

    return response


def _compute_delay(
    response: requests.Response,
    attempt: int,
    *,
    base_delay: float,
    max_delay: float,
) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), max_delay)
        except ValueError:
            pass
    backoff = base_delay * (2**attempt)
    jitter = random.uniform(0, base_delay)
    return min(backoff + jitter, max_delay)
