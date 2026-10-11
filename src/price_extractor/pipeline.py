from __future__ import annotations

import logging
from typing import Any

from .config import Settings
from .exporters import DataExporter
from .extractors.coles import ColesExtractor
from .extractors.woolworths import WoolworthsExtractor
from .http import HttpClient
from .models import ExtractionStats, ProductRecord, RunSummary, StoreConfig, utc_now
from .uploader import S3Uploader

logger = logging.getLogger(__name__)

EXTRACTORS = {
    "coles": ColesExtractor,
    "woolworths": WoolworthsExtractor,
}


class ExtractionPipeline:
    def __init__(
        self,
        settings: Settings,
        stores: list[dict[str, Any]],
        categories: dict[str, list[str]],
    ):
        self.settings = settings
        self.stores = [StoreConfig.model_validate(item) for item in stores]
        self.categories = categories

    def run(self, retailers: list[str] | None = None) -> RunSummary:
        selected = {item.lower() for item in retailers} if retailers else None
        summary = RunSummary(started_at=utc_now(), extraction_date="")
        records: list[ProductRecord] = []
        all_stats: list[ExtractionStats] = []

        for store in self.stores:
            retailer = store.retailer.lower()
            if selected and retailer not in selected:
                continue
            retailer_cfg = self.settings.retailers.get(retailer)
            if not retailer_cfg or not retailer_cfg.enabled:
                logger.info("Skipping disabled retailer %s", retailer)
                continue
            extractor_cls = EXTRACTORS.get(retailer)
            if extractor_cls is None:
                message = f"No extractor registered for retailer '{retailer}'"
                logger.error(message)
                summary.errors.append(message)
                continue
            extra_headers = {"Origin": retailer_cfg.base_url, "Referer": retailer_cfg.base_url}
            with HttpClient(self.settings.app, extra_headers=extra_headers) as client:
                extractor = extractor_cls(self.settings, client)
                if not summary.extraction_date:
                    summary.extraction_date = extractor.extraction_date()
                logger.info("Extracting %s store %s (%s)", retailer, store.store_id, store.name)
                store_records, store_stats = extractor.safe_extract(
                    store,
                    self.categories.get(retailer, []),
                )
                records.extend(store_records)
                all_stats.extend(store_stats)

        unique, duplicates = deduplicate(records)
        summary.total_products = len(records)
        summary.unique_products = len(unique)
        summary.duplicates_removed = duplicates
        summary.store_stats = all_stats
        store_keys = {(stat.retailer, stat.store_id) for stat in all_stats}
        failed_keys = {(stat.retailer, stat.store_id) for stat in all_stats if not stat.success}
        summary.failed_stores = len(failed_keys)
        summary.successful_stores = len(store_keys - failed_keys)
        summary.errors.extend(
            f"{stat.retailer}/{stat.store_id}/{stat.category}: {stat.error}"
            for stat in all_stats
            if stat.error
        )
        if not summary.extraction_date:
            summary.extraction_date = utc_now().date().isoformat()
        summary.mark_finished()

        exporter = DataExporter(self.settings.output)
        files = exporter.export(unique, summary)
        try:
            uploaded = S3Uploader(self.settings.aws).upload(files, summary.extraction_date)
            summary.upload_paths = uploaded
        except Exception as exc:
            message = f"Upload failed: {exc}"
            logger.exception(message)
            summary.errors.append(message)

        log_summary(summary)
        return summary


def deduplicate(records: list[ProductRecord]) -> tuple[list[ProductRecord], int]:
    unique: dict[tuple[str, str, str], ProductRecord] = {}
    duplicates = 0
    for record in records:
        key = record.dedupe_key()
        if key in unique:
            duplicates += 1
            continue
        unique[key] = record
    return list(unique.values()), duplicates


def log_summary(summary: RunSummary) -> None:
    logger.info(
        "Run complete: unique=%s duplicates_removed=%s successful_stores=%s failed_stores=%s duration=%ss",
        summary.unique_products,
        summary.duplicates_removed,
        summary.successful_stores,
        summary.failed_stores,
        summary.duration_seconds(),
    )
    if summary.export_paths:
        logger.info("Exports: %s", ", ".join(summary.export_paths))
    if summary.upload_paths:
        logger.info("Uploads: %s", ", ".join(summary.upload_paths))
    if summary.errors:
        logger.warning("Errors (%s): %s", len(summary.errors), "; ".join(summary.errors[:10]))
