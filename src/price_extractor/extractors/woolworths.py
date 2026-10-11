from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from ..models import ExtractionStats, ProductRecord, StoreConfig
from ..parsers import as_bool, as_float, first, join_url, package_size, walk
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class WoolworthsExtractor(BaseExtractor):
    retailer_name = "woolworths"

    def extract_store(
        self,
        store: StoreConfig,
        categories: list[str],
    ) -> tuple[list[ProductRecord], list[ExtractionStats]]:
        self._bootstrap_session(store)
        resolved = self._resolve_categories(categories)
        records: list[ProductRecord] = []
        stats: list[ExtractionStats] = []
        seen: set[str] = set()
        date = self.extraction_date()

        for category_id, category in resolved:
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
                    payload = self._fetch_category(category_id, category, page)
                    store_stats.pages_fetched += 1
                    bundles = payload.get("Bundles") or payload.get("Products") or []
                    products = self._flatten_bundles(bundles)
                    if not products:
                        break
                    added = 0
                    for product in products:
                        if self.retailer.exclude_marketplace and self._is_marketplace(product):
                            continue
                        record = self._to_record(product, store, category, date)
                        if record is None or record.product_id in seen:
                            continue
                        seen.add(record.product_id)
                        records.append(record)
                        added += 1
                        if self.should_stop(len(records)):
                            break
                    store_stats.products_collected += added
                    total = as_float(walk(payload, "TotalRecordCount") or payload.get("TotalProducts"))
                    if added == 0:
                        break
                    if total and page * self.retailer.page_size >= int(total):
                        break
                    if len(products) < self.retailer.page_size:
                        break
                    page += 1
            except Exception as exc:
                logger.warning(
                    "Woolworths category %s failed for store %s: %s",
                    category,
                    store.store_id,
                    exc,
                )
                store_stats.failed_pages += 1
                store_stats.success = store_stats.products_collected > 0
                store_stats.error = str(exc)
            stats.append(store_stats)
        return records, stats

    def _bootstrap_session(self, store: StoreConfig) -> None:
        self.client.get(self.retailer.base_url)
        self.client.post(
            f"{self.retailer.base_url}/apis/ui/StoreLocator/Search",
            json={"Search": store.postcode, "Max": 5},
        )

    def _resolve_categories(self, categories: list[str]) -> list[tuple[str, str]]:
        mapping = self._category_map()
        resolved: list[tuple[str, str]] = []
        for category in categories:
            key = category.strip("/").lower()
            resolved.append((mapping.get(key, category), category))
        return resolved

    def _category_map(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        try:
            payload = self.client.get(
                f"{self.retailer.base_url}/apis/ui/PiesCategoriesWithSpecials"
            ).json()
        except Exception as exc:
            logger.warning("Woolworths category tree unavailable: %s", exc)
            return mapping

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                node_id = node.get("NodeId") or node.get("CategoryId")
                url = str(node.get("UrlFriendlyName") or node.get("Url") or "").strip("/")
                if node_id and url:
                    mapping[url.lower()] = str(node_id)
                    mapping[url.rsplit("/", 1)[-1].lower()] = str(node_id)
                for child in node.get("Children") or node.get("Categories") or []:
                    _walk(child)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return mapping

    def _fetch_category(self, category_id: str, category: str, page: int) -> dict[str, Any]:
        url = f"{self.retailer.base_url}/apis/ui/browse/category"
        body = {
            "categoryId": category_id,
            "pageNumber": page,
            "pageSize": self.retailer.page_size,
            "sortType": "TraderRelevance",
            "url": f"/shop/browse/{category}",
            "location": f"/shop/browse/{category}",
            "formatObject": "{}",
            "isSpecial": False,
            "isBundle": False,
            "isMobile": False,
            "filters": [],
            "token": "",
            "gpBoost": 0,
            "isHideUnavailableProducts": False,
            "enableAdReRanking": False,
            "groupEdmVariants": True,
            "categoryVersion": "v2",
        }
        headers = {
            "Referer": f"{self.retailer.base_url}/shop/browse/{quote(category)}",
            "Origin": self.retailer.base_url,
            "Content-Type": "application/json",
        }
        response = self.client.post(url, json=body, headers=headers)
        return response.json()

    def _flatten_bundles(self, bundles: list[Any]) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        for bundle in bundles:
            if not isinstance(bundle, dict):
                continue
            nested = bundle.get("Products")
            if isinstance(nested, list) and nested:
                products.extend(item for item in nested if isinstance(item, dict))
            elif bundle.get("Stockcode") or bundle.get("Name"):
                products.append(bundle)
        return products

    @staticmethod
    def _category_name(product: dict[str, Any], fallback: str) -> str:
        attributes = product.get("AdditionalAttributes")
        if isinstance(attributes, dict):
            return str(first(attributes.get("piesdepartmentnamesjson"), fallback))
        return fallback

    def _is_marketplace(self, product: dict[str, Any]) -> bool:
        source = str(first(product.get("Source"), product.get("MarketplaceSource"), "")).lower()
        return "market" in source or bool(product.get("IsMarketplace"))

    def _to_record(
        self,
        product: dict[str, Any],
        store: StoreConfig,
        category: str,
        date: str,
    ) -> ProductRecord | None:
        product_id = str(first(product.get("Stockcode"), product.get("sku"), product.get("Id")) or "")
        name = first(product.get("DisplayName"), product.get("Name"), product.get("Description"))
        if not product_id or not name:
            return None
        current = as_float(first(product.get("Price"), product.get("InstorePrice")))
        was = as_float(first(product.get("WasPrice"), product.get("ListPrice")))
        unit_price = as_float(product.get("CupPrice"))
        unit_text = first(product.get("CupString"), product.get("UnitPriceDescription"))
        promotion = first(
            product.get("CentreTag", {}).get("Data") if isinstance(product.get("CentreTag"), dict) else None,
            (
                product.get("HeaderTag", {}).get("Content")
                if isinstance(product.get("HeaderTag"), dict)
                else None
            ),
            product.get("PromotionString"),
            product.get("SpecialsDisplayName"),
        )
        url_path = first(
            product.get("UrlFriendlyName"),
            f"shop/productdetails/{product_id}",
        )
        if url_path and not str(url_path).startswith("http") and "productdetails" not in str(url_path):
            url_path = f"shop/productdetails/{product_id}/{url_path}"
        return ProductRecord(
            product_id=product_id,
            product_name=str(name),
            brand=first(product.get("Brand"), product.get("BrandName")),
            package_size=package_size(
                product.get("PackageSize"),
                product.get("CupMeasure"),
                product.get("Unit"),
            ),
            current_price=current,
            unit_price=unit_price,
            unit_price_text=str(unit_text) if unit_text else None,
            promotional_price=current if product.get("IsOnSpecial") else None,
            was_price=was if was and was != current else None,
            promotion_text=str(promotion) if promotion else None,
            is_on_promotion=bool(product.get("IsOnSpecial") or product.get("IsHalfPrice") or promotion),
            retailer=self.retailer_name,
            store_id=store.store_id,
            store_name=store.name,
            store_location=store.location,
            state=store.state,
            postcode=store.postcode,
            category=self._category_name(product, category),
            product_url=join_url(self.retailer.base_url, str(url_path)),
            in_stock=as_bool(first(product.get("IsInStock"), product.get("IsAvailable"), True)),
            extraction_date=date,
        )
