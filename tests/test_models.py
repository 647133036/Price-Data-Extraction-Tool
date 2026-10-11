from price_extractor.models import ProductRecord, utc_now
from price_extractor.pipeline import deduplicate


def _record(product_id: str, store_id: str = "0584") -> ProductRecord:
    return ProductRecord(
        product_id=product_id,
        product_name="Milk",
        package_size="3L",
        current_price=4.5,
        unit_price=1.5,
        unit_price_text="$1.50 / 1L",
        retailer="coles",
        store_id=store_id,
        store_name="Coles Melbourne CBD",
        store_location="Melbourne VIC",
        state="VIC",
        postcode="3000",
        product_url="https://www.coles.com.au/product/milk",
        extraction_date=utc_now().date().isoformat(),
    )


def test_deduplicate_keeps_one_row_per_store_product() -> None:
    records = [_record("1"), _record("1"), _record("2"), _record("1", "0474")]
    unique, duplicates = deduplicate(records)
    assert duplicates == 1
    assert len(unique) == 3
    keys = {item.dedupe_key() for item in unique}
    assert ("coles", "0584", "1") in keys
    assert ("coles", "0474", "1") in keys
