from __future__ import annotations

import logging
import re
from typing import Any

from ..models import ExtractionStats, ProductRecord, StoreConfig
from ..parsers import as_bool, as_float, collect_dicts, first, join_url, package_size, walk
from .base import BaseExtractor

logger = logging.getLogger(__name__)

BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')


class ColesExtractor(BaseExtractor):
    retailer_name = "coles"

    def extract_store(
        self,
        store: StoreConfig,
        categories: list[str],
    ) -> tuple[list[ProductRecord], list[ExtractionStats]]:
        build_id = self._discover_build_id()
        records: list[ProductRecord] = []
        stats: list[ExtractionStats] = []
        seen: set[str] = set()
        date = self.extraction_date()

        for category in categories:
            store_stats = ExtractionStats(
                retailer=self.retailer_name,
                store_id=store.store_id,
                store_name=store.name,
                category=category,
            )
            page = 1
            try:
                while True:
                    if self.should_stop(len(records)):
                        break
                    payload = self._fetch_category(build_id, category, page, store.store_id)
                    store_stats.pages_fetched += 1
                    products = self._products_from_payload(payload)
                    if not products:
                        break
                    added = 0
                    for product in products:
                        record = self._to_record(product, store, category, date)
                        if record is None or record.product_id in seen:
                            continue
                        seen.add(record.product_id)
                        records.append(record)
                        added += 1
                        if self.should_stop(len(records)):
                            break
                    store_stats.products_collected += added
                    if added == 0 or not self._has_next_page(payload, page, len(products)):
                        break
                    page += 1
            except Exception as exc:
                logger.warning(
                    "Coles category %s failed for store %s: %s",
                    category,
                    store.store_id,
                    exc,
                )
                store_stats.failed_pages += 1
                store_stats.success = store_stats.products_collected > 0
                store_stats.error = str(exc)
            stats.append(store_stats)
        return records, stats

    def _discover_build_id(self) -> str:
        response = self.client.get(self.retailer.base_url)
        match = BUILD_ID_RE.search(response.text)
        if not match:
            raise RuntimeError("Unable to discover Coles Next.js buildId")
        return match.group(1)

    def _fetch_category(self, build_id: str, category: str, page: int, store_id: str) -> dict[str, Any]:
        slug = category.strip("/")
        url = f"{self.retailer.base_url}/_next/data/{build_id}/browse/{slug}.json"
        params = {"page": page, "slug": slug.split("/")}
        headers = {
            "Referer": f"{self.retailer.base_url}/browse/{slug}",
            "x-coles-store": store_id,
        }
        cookies = {
            "fulfillmentStoreId": store_id,
            "shoppingStoreId": store_id,
        }
        response = self.client.get(url, params=params, headers=headers, cookies=cookies)
        return response.json()

    def _products_from_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        results_page = walk(payload, "pageProps", "searchResults") or walk(
            payload, "pageProps", "results"
        )
        if isinstance(results_page, dict):
            results = results_page.get("results") or results_page.get("products") or []
            if isinstance(results, list) and results:
                return [item for item in results if isinstance(item, dict)]
        return [
            item
            for item in collect_dicts(payload, ("pricing", "id", "name"))
            if item.get("_type") in {None, "PRODUCT", "product"} or "pricing" in item
        ]

    def _has_next_page(self, payload: dict[str, Any], page: int, batch_size: int) -> bool:
        search = walk(payload, "pageProps", "searchResults") or {}
        if isinstance(search, dict):
            no_of_pages = as_float(search.get("noOfPages") or search.get("totalPages"))
            if no_of_pages:
                return page < int(no_of_pages)
            total = as_float(search.get("noOfResults") or search.get("totalResults"))
            if total:
                return page * self.retailer.page_size < int(total)
        return batch_size >= self.retailer.page_size

    def _to_record(
        self,
        product: dict[str, Any],
        store: StoreConfig,
        category: str,
        date: str,
    ) -> ProductRecord | None:
        product_id = str(first(product.get("id"), product.get("productId"), product.get("sku")) or "")
        name = first(product.get("name"), product.get("displayName"), product.get("brandAndName"))
        if not product_id or not name:
            return None
        pricing = product.get("pricing") if isinstance(product.get("pricing"), dict) else {}
        current = as_float(first(pricing.get("now"), product.get("price"), product.get("currentPrice")))
        was = as_float(first(pricing.get("was"), product.get("wasPrice")))
        unit_source = pricing.get("unit") if isinstance(pricing.get("unit"), dict) else {}
        unit_price = as_float(first(unit_source.get("price"), product.get("unitPrice")))
        unit_text = first(
            unit_source.get("ofMeasureUnits"),
            pricing.get("comparable"),
            product.get("unitPriceDescription"),
        )
        if unit_text and unit_price is not None and "$" not in str(unit_text):
            unit_text = f"${unit_price:.2f} / {unit_text}"
        promotion = first(
            pricing.get("promotionDescription"),
            product.get("promotion"),
            walk(pricing, "offerDescription"),
        )
        if was and current and was > current:
            promo_price = current
        else:
            promo_price = as_float(product.get("promotionalPrice"))
        online = product.get("onlineHealing") if isinstance(product.get("onlineHealing"), dict) else {}
        return ProductRecord(
            product_id=product_id,
            product_name=str(name),
            brand=first(product.get("brand"), walk(product, "brand", "name")),
            package_size=package_size(
                product.get("size"),
                product.get("packageSize"),
                product.get("quantity"),
            ),
            current_price=current,
            unit_price=unit_price,
            unit_price_text=str(unit_text) if unit_text else None,
            promotional_price=promo_price if promo_price and promo_price != was else None,
            was_price=was,
            promotion_text=str(promotion) if promotion else None,
            is_on_promotion=bool(promotion or (was and current and was > current)),
            retailer=self.retailer_name,
            store_id=store.store_id,
            store_name=store.name,
            store_location=store.location,
            state=store.state,
            postcode=store.postcode,
            category=category,
            product_url=join_url(
                self.retailer.base_url,
                first(product.get("url"), product.get("seoToken"), f"product/{product_id}"),
            ),
            in_stock=as_bool(first(product.get("availability"), online.get("availability"), True)),
            extraction_date=date,
        )
