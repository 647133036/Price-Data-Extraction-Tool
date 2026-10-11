from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StoreConfig(BaseModel):
    retailer: str
    store_id: str
    name: str
    location: str
    state: str
    postcode: str


class ProductRecord(BaseModel):
    product_id: str
    product_name: str
    brand: str | None = None
    package_size: str | None = None
    current_price: float | None = None
    unit_price: float | None = None
    unit_price_text: str | None = None
    promotional_price: float | None = None
    was_price: float | None = None
    promotion_text: str | None = None
    is_on_promotion: bool = False
    currency: str = "AUD"
    retailer: str
    store_id: str
    store_name: str
    store_location: str
    state: str
    postcode: str
    category: str | None = None
    product_url: str | None = None
    in_stock: bool | None = None
    extraction_date: str
    extracted_at: datetime = Field(default_factory=utc_now)

    @field_validator("product_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    def dedupe_key(self) -> tuple[str, str, str]:
        return (self.retailer.lower(), self.store_id, self.product_id)

    def to_export_dict(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["extracted_at"] = self.extracted_at.isoformat()
        return payload


class ExtractionStats(BaseModel):
    retailer: str
    store_id: str
    store_name: str
    category: str | None = None
    products_collected: int = 0
    pages_fetched: int = 0
    failed_pages: int = 0
    retries: int = 0
    error: str | None = None
    success: bool = True


class RunSummary(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    extraction_date: str
    total_products: int = 0
    unique_products: int = 0
    duplicates_removed: int = 0
    successful_stores: int = 0
    failed_stores: int = 0
    export_paths: list[str] = Field(default_factory=list)
    upload_paths: list[str] = Field(default_factory=list)
    store_stats: list[ExtractionStats] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def mark_finished(self) -> None:
        self.finished_at = utc_now()

    def duration_seconds(self) -> float:
        end = self.finished_at or utc_now()
        return round((end - self.started_at).total_seconds(), 2)

    def to_export_dict(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["started_at"] = self.started_at.isoformat()
        payload["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        payload["duration_seconds"] = self.duration_seconds()
        return payload
