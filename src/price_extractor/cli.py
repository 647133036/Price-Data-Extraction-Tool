from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import load_settings
from .logging_utils import setup_logging
from .pipeline import ExtractionPipeline
from .scheduler import start_scheduler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract weekly Coles and Woolworths product prices across Australia."
    )
    parser.add_argument("--config", help="Path to settings.yaml")
    parser.add_argument("--stores", help="Path to stores.yaml")
    parser.add_argument("--categories", help="Path to categories.yaml")
    parser.add_argument(
        "--retailer",
        action="append",
        dest="retailers",
        help="Limit the run to one retailer. Repeat to include both.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate sample records without live requests.",
    )
    parser.add_argument("--schedule", action="store_true", help="Run on the configured weekly schedule.")
    parser.add_argument("--max-products", type=int, help="Cap products collected per store.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings, stores, categories = load_settings(args.config, args.stores, args.categories)
    if args.dry_run:
        settings.app.dry_run = True
    if args.max_products is not None:
        settings.app.max_products_per_store = args.max_products
    setup_logging(settings.logging)
    logger = logging.getLogger("price_extractor")
    pipeline = ExtractionPipeline(settings, stores, categories)

    if args.schedule:
        logger.info("Entering weekly scheduler mode")
        start_scheduler(settings, pipeline)
        return 0

    summary = pipeline.run(args.retailers)
    print(json.dumps(summary.to_export_dict(), indent=2, default=str))
    return 1 if summary.failed_stores and summary.unique_products == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
