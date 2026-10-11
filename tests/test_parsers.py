from price_extractor.parsers import as_bool, as_float, collect_dicts, join_url, package_size


def test_as_float_parses_currency_and_numbers() -> None:
    assert as_float("$3.90 / 1kg") == 3.9
    assert as_float(4) == 4.0
    assert as_float(None) is None
    assert as_float("n/a") is None


def test_as_bool_understands_stock_labels() -> None:
    assert as_bool("In Stock") is True
    assert as_bool("out of stock") is False
    assert as_bool(None) is None


def test_join_url_and_package_size() -> None:
    assert join_url("https://www.coles.com.au", "product/123") == "https://www.coles.com.au/product/123"
    assert join_url("https://www.coles.com.au", "https://cdn.example/a") == "https://cdn.example/a"
    assert package_size(" 3L ", None) == "3L"


def test_collect_dicts_finds_nested_products() -> None:
    payload = {"pageProps": {"results": [{"id": "1", "pricing": {"now": 2.5}}]}}
    found = collect_dicts(payload, ("pricing", "id"))
    assert found[0]["id"] == "1"
