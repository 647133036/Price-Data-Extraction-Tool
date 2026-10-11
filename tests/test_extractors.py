from price_extractor.config import Settings
from price_extractor.extractors.coles import ColesExtractor
from price_extractor.extractors.woolworths import WoolworthsExtractor
from price_extractor.http import HttpClient
from price_extractor.models import StoreConfig

SETTINGS = Settings.model_validate(
    {
        "app": {
            "dry_run": False,
            "max_products_per_store": 0,
            "request_delay_seconds": 0,
            "max_retries": 2,
            "retry_backoff_seconds": 0.01,
            "timeout_seconds": 5,
            "user_agent": "test-agent",
        },
        "schedule": {},
        "output": {"directory": "data/output", "formats": ["csv", "json"]},
        "logging": {},
        "aws": {"enabled": False, "region": "ap-southeast-2"},
        "retailers": {
            "coles": {"enabled": True, "base_url": "https://www.coles.com.au", "page_size": 48},
            "woolworths": {
                "enabled": True,
                "base_url": "https://www.woolworths.com.au",
                "page_size": 36,
                "exclude_marketplace": True,
            },
        },
    }
)

STORE = StoreConfig(
    retailer="coles",
    store_id="0584",
    name="Coles Melbourne CBD",
    location="Melbourne VIC",
    state="VIC",
    postcode="3000",
)


def test_coles_maps_product_payload() -> None:
    extractor = ColesExtractor(SETTINGS, HttpClient(SETTINGS.app))
    record = extractor._to_record(
        {
            "id": "8150288",
            "name": "Coles Full Cream Milk",
            "brand": "Coles",
            "size": "3L",
            "pricing": {
                "now": 4.5,
                "was": 5.2,
                "unit": {"price": 1.5, "ofMeasureUnits": "1L"},
                "promotionDescription": "save $0.70",
            },
            "url": "/product/coles-full-cream-milk-3l-8150288",
            "availability": True,
        },
        STORE,
        "dairy-eggs-fridge",
        "2026-10-11",
    )
    extractor.client.close()
    assert record is not None
    assert record.product_name == "Coles Full Cream Milk"
    assert record.current_price == 4.5
    assert record.promotional_price == 4.5
    assert record.unit_price == 1.5
    assert record.store_location == "Melbourne VIC"
    assert "8150288" in (record.product_url or "")


def test_woolworths_skips_marketplace_and_maps_specials() -> None:
    extractor = WoolworthsExtractor(SETTINGS, HttpClient(SETTINGS.app))
    market = {"Stockcode": "9", "Name": "Marketplace Item", "IsMarketplace": True}
    assert extractor._is_marketplace(market) is True
    record = extractor._to_record(
        {
            "Stockcode": 888140,
            "DisplayName": "Woolworths Full Cream Milk 3L",
            "Brand": "Woolworths",
            "PackageSize": "3L",
            "Price": 4.95,
            "WasPrice": 5.5,
            "CupPrice": 1.65,
            "CupString": "$1.65 / 1L",
            "IsOnSpecial": True,
            "IsInStock": True,
            "UrlFriendlyName": "woolworths-full-cream-milk",
        },
        STORE.model_copy(update={"retailer": "woolworths", "store_id": "1255"}),
        "dairy-eggs-fridge",
        "2026-10-11",
    )
    extractor.client.close()
    assert record is not None
    assert record.is_on_promotion is True
    assert record.unit_price_text == "$1.65 / 1L"
    assert record.product_id == "888140"


def test_woolworths_resolves_browse_slugs_to_node_ids() -> None:
    extractor = WoolworthsExtractor(SETTINGS, HttpClient(SETTINGS.app))
    extractor._category_map = lambda: {"dairy-eggs-fridge": "1_6E4F4E4", "milk": "1_ABC"}  # type: ignore[method-assign]
    resolved = extractor._resolve_categories(["dairy-eggs-fridge", "unknown-aisle"])
    extractor.client.close()
    assert resolved == [("1_6E4F4E4", "dairy-eggs-fridge"), ("unknown-aisle", "unknown-aisle")]


def test_dry_run_returns_location_specific_sample_rows() -> None:
    settings = SETTINGS.model_copy(deep=True)
    settings.app.dry_run = True
    extractor = ColesExtractor(settings, HttpClient(settings.app))
    records, stats = extractor.safe_extract(STORE, ["dairy-eggs-fridge", "bakery"])
    extractor.client.close()
    assert len(records) == 6
    assert all(item.store_id == "0584" for item in records)
    assert all(item.retailer == "coles" for item in records)
    assert stats[0].success is True
