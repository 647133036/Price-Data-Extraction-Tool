from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import AppSettings

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
}


class RetryableHTTPError(Exception):
    pass


class HttpClient:
    def __init__(self, settings: AppSettings, extra_headers: dict[str, str] | None = None):
        headers = {**DEFAULT_HEADERS, "User-Agent": settings.user_agent}
        if extra_headers:
            headers.update(extra_headers)
        self.settings = settings
        self._client = httpx.Client(
            timeout=settings.timeout_seconds,
            headers=headers,
            follow_redirects=True,
        )
        self._last_request_at = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _throttle(self) -> None:
        delay = self.settings.request_delay_seconds
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> httpx.Response:
        attempts = max(1, self.settings.max_retries)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(
                multiplier=self.settings.retry_backoff_seconds,
                min=self.settings.retry_backoff_seconds,
                max=20,
            ),
            retry=retry_if_exception_type((RetryableHTTPError, httpx.HTTPError)),
            before_sleep=lambda retry_state: logger.warning(
                "Retrying %s %s (attempt %s): %s",
                method,
                url,
                retry_state.attempt_number,
                retry_state.outcome.exception() if retry_state.outcome else "",
            ),
        )
        def _do() -> httpx.Response:
            self._throttle()
            self._last_request_at = time.monotonic()
            response = self._client.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                cookies=cookies,
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                raise RetryableHTTPError(
                    f"{response.status_code} from {url}"
                )
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{response.status_code} from {url}",
                    request=response.request,
                    response=response,
                )
            return response

        return _do()

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)
