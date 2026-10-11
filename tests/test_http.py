import httpx
import respx

from price_extractor.config import AppSettings
from price_extractor.http import HttpClient, RetryableHTTPError


@respx.mock
def test_http_client_retries_on_503() -> None:
    settings = AppSettings(
        max_retries=3,
        retry_backoff_seconds=0.01,
        request_delay_seconds=0,
        timeout_seconds=5,
    )
    route = respx.get("https://example.test/products").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    client = HttpClient(settings)
    try:
        response = client.get("https://example.test/products")
        assert response.json() == {"ok": True}
        assert route.call_count == 2
    finally:
        client.close()


@respx.mock
def test_http_client_raises_after_retry_budget() -> None:
    settings = AppSettings(
        max_retries=2,
        retry_backoff_seconds=0.01,
        request_delay_seconds=0,
        timeout_seconds=5,
    )
    respx.get("https://example.test/fail").mock(return_value=httpx.Response(503))
    client = HttpClient(settings)
    try:
        try:
            client.get("https://example.test/fail")
            raised = False
        except RetryableHTTPError:
            raised = True
        assert raised is True
    finally:
        client.close()
