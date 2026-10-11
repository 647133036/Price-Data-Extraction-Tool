from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import Settings
from ..http import HttpClient
from ..models import ExtractionStats, ProductRecord, StoreConfig

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    retailer_name: str

    def __init__(self, settings: Settings, client: HttpClient):
        self.settings = settings
        self.client = client
        self.retailer = settings.retailers[self.retailer_name]

    def extraction_date(self) -> str:
        tz = ZoneInfo(self.settings.app.timezone)
        return datetime.now(tz).date().isoformat()

    def should_stop(self, collected: int) -> bool:
        limit = self.settings.app.max_products_per_store
        return limit > 0 and collected >= limit

    @abstractmethod
    def extract_store(
        self,
        store: StoreConfig,
        categories: list[str],
    ) -> tuple[list[ProductRecord], list[ExtractionStats]]:
        raise NotImplementedError

    def dry_run_records(
        self,
        store: StoreConfig,
        categories: list[str],
    ) -> tuple[list[ProductRecord], list[ExtractionStats]]:
        date = self.extraction_date()
        records: list[ProductRecord] = []
        stats: list[ExtractionStats] = []
        samples = [
            ("full-cream-milk-3l", "Full Cream Milk", "3L", 4.50, 1.50, "$1.50 / 1L", None),
            ("bananas", "Cavendish Bananas", "per kg", 3.90, 3.90, "$3.90 / 1kg", 2.90),
            ("white-bread-700g", "White Sandwich Bread", "700g", 2.70, 0.39, "$0.39 / 100g", None),
        ]
        selected = categories or ["sample"]
        for category in selected[:2]:
            for sku, name, size, price, unit, unit_text, promo in samples:
                records.append(
                    ProductRecord(
                        product_id=f"{self.retailer_name}-{store.store_id}-{category}-{sku}",
                        product_name=name,
                        brand=self.retailer_name.title(),
                        package_size=size,
                        current_price=promo or price,
                        unit_price=unit,
                        unit_price_text=unit_text,
                        promotional_price=promo,
                        was_price=price if promo else None,
                        promotion_text="Weekly special" if promo else None,
                        is_on_promotion=promo is not None,
                        retailer=self.retailer_name,
                        store_id=store.store_id,
                        store_name=store.name,
                        store_location=store.location,
                        state=store.state,
                        postcode=store.postcode,
                        category=category,
                        product_url=f"{self.retailer.base_url}/product/{sku}",
                        in_stock=True,
                        extraction_date=date,
                    )
                )
            stats.append(
                ExtractionStats(
                    retailer=self.retailer_name,
                    store_id=store.store_id,
                    store_name=store.name,
                    category=category,
                    products_collected=len(samples),
                    pages_fetched=1,
                )
            )
        return records, stats

    def safe_extract(
        self,
        store: StoreConfig,
        categories: list[str],
    ) -> tuple[list[ProductRecord], list[ExtractionStats]]:
        if self.settings.app.dry_run:
            logger.info("Dry-run extraction for %s store %s", self.retailer_name, store.store_id)
            return self.dry_run_records(store, categories)
        try:
            return self.extract_store(store, categories)
        except Exception as exc:
            logger.exception(
                "Extraction failed for %s store %s: %s",
                self.retailer_name,
                store.store_id,
                exc,
            )
            stats = [
                ExtractionStats(
                    retailer=self.retailer_name,
                    store_id=store.store_id,
                    store_name=store.name,
                    products_collected=0,
                    success=False,
                    error=str(exc),
                )
            ]
            return [], stats
