import json
from pathlib import Path

from price_extractor.config import Settings
from price_extractor.exporters import DataExporter
from price_extractor.models import ProductRecord, RunSummary, utc_now
from price_extractor.pipeline import ExtractionPipeline


def test_exporter_writes_csv_json_and_summary(tmp_path: Path, monkeypatch) -> None:
    from price_extractor import exporters

    monkeypatch.setattr(exporters, "ROOT", tmp_path)
    settings = Settings.model_validate(
        {
            "app": {},
            "schedule": {},
            "output": {"directory": "out", "formats": ["csv", "json"], "pretty_json": True},
            "logging": {},
            "aws": {"enabled": False, "region": "ap-southeast-2"},
            "retailers": {
                "coles": {"enabled": True, "base_url": "https://www.coles.com.au"},
                "woolworths": {"enabled": True, "base_url": "https://www.woolworths.com.au"},
            },
        }
    )
    record = ProductRecord(
        product_id="1",
        product_name="Milk",
        package_size="3L",
        current_price=4.5,
        unit_price=1.5,
        retailer="coles",
        store_id="0584",
        store_name="Coles Melbourne CBD",
        store_location="Melbourne VIC",
        state="VIC",
        postcode="3000",
        extraction_date="2026-10-11",
    )
    summary = RunSummary(started_at=utc_now(), extraction_date="2026-10-11")
    summary.mark_finished()
    paths = DataExporter(settings.output).export([record], summary)
    names = {path.name for path in paths}
    assert "prices_2026-10-11.csv" in names
    assert "prices_2026-10-11.json" in names
    payload = json.loads((tmp_path / "out" / "prices_2026-10-11.json").read_text(encoding="utf-8"))
    assert payload[0]["product_name"] == "Milk"


def test_pipeline_dry_run_covers_configured_stores() -> None:
    settings = Settings.model_validate(
        {
            "app": {"dry_run": True, "max_products_per_store": 0},
            "schedule": {},
            "output": {"directory": "data/output", "formats": ["json"]},
            "logging": {"directory": "logs"},
            "aws": {"enabled": False, "region": "ap-southeast-2"},
            "retailers": {
                "coles": {"enabled": True, "base_url": "https://www.coles.com.au"},
                "woolworths": {"enabled": False, "base_url": "https://www.woolworths.com.au"},
            },
        }
    )
    stores = [
        {
            "retailer": "coles",
            "store_id": "0584",
            "name": "Coles Melbourne CBD",
            "location": "Melbourne VIC",
            "state": "VIC",
            "postcode": "3000",
        },
        {
            "retailer": "woolworths",
            "store_id": "1255",
            "name": "Woolworths Melbourne Metro",
            "location": "Melbourne VIC",
            "state": "VIC",
            "postcode": "3000",
        },
    ]
    categories = {
        "coles": ["dairy-eggs-fridge"],
        "woolworths": ["dairy-eggs-fridge"],
    }
    pipeline = ExtractionPipeline(settings, stores, categories)
    summary = pipeline.run()
    assert summary.unique_products == 3
    assert summary.failed_stores == 0
    assert summary.successful_stores == 1
