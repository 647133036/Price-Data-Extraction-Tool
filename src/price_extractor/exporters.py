from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from .config import ROOT, OutputSettings
from .models import ProductRecord, RunSummary

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "product_id",
    "product_name",
    "brand",
    "package_size",
    "current_price",
    "unit_price",
    "unit_price_text",
    "promotional_price",
    "was_price",
    "promotion_text",
    "is_on_promotion",
    "currency",
    "retailer",
    "store_id",
    "store_name",
    "store_location",
    "state",
    "postcode",
    "category",
    "product_url",
    "in_stock",
    "extraction_date",
    "extracted_at",
]


class DataExporter:
    def __init__(self, settings: OutputSettings):
        self.settings = settings
        self.directory = ROOT / settings.directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def export(self, records: list[ProductRecord], summary: RunSummary) -> list[Path]:
        stem = f"prices_{summary.extraction_date}"
        written: list[Path] = []
        formats = {item.lower() for item in self.settings.formats}
        rows = [record.to_export_dict() for record in records]
        if "json" in formats:
            written.append(self._write_json(self.directory / f"{stem}.json", rows))
        if "csv" in formats:
            written.append(self._write_csv(self.directory / f"{stem}.csv", rows))
        summary_path = self.directory / f"summary_{summary.extraction_date}.json"
        written.append(self._write_json(summary_path, summary.to_export_dict()))
        summary.export_paths = [str(path) for path in written]
        logger.info("Wrote %s export files to %s", len(written), self.directory)
        return written

    def _write_json(self, path: Path, payload: object) -> Path:
        indent = 2 if self.settings.pretty_json else None
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
        return path

    def _write_csv(self, path: Path, rows: list[dict]) -> Path:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path
