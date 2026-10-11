from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


class AppSettings(BaseModel):
    name: str = "Coles & Woolworths Price Data Extraction Tool"
    timezone: str = "Australia/Sydney"
    dry_run: bool = False
    max_products_per_store: int = 0
    request_delay_seconds: float = 0.4
    max_retries: int = 3
    retry_backoff_seconds: float = 1.5
    timeout_seconds: float = 30
    user_agent: str = "Mozilla/5.0"


class ScheduleSettings(BaseModel):
    enabled: bool = False
    weekday: str = "wed"
    hour: int = 6
    minute: int = 0


class OutputSettings(BaseModel):
    directory: str = "data/output"
    formats: list[str] = Field(default_factory=lambda: ["csv", "json"])
    pretty_json: bool = True


class LoggingSettings(BaseModel):
    level: str = "INFO"
    directory: str = "logs"
    filename: str = "extractor.log"


class AwsSettings(BaseModel):
    enabled: bool = False
    region: str = "ap-southeast-2"
    s3_bucket: str = ""
    s3_prefix: str = "grocery-prices"
    profile_name: str = ""


class RetailerSettings(BaseModel):
    enabled: bool = True
    base_url: str
    page_size: int = 36
    exclude_marketplace: bool = True


class Settings(BaseModel):
    app: AppSettings
    schedule: ScheduleSettings
    output: OutputSettings
    logging: LoggingSettings
    aws: AwsSettings
    retailers: dict[str, RetailerSettings]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def load_settings(
    config_path: str | Path | None = None,
    stores_path: str | Path | None = None,
    categories_path: str | Path | None = None,
) -> tuple[Settings, list[dict[str, Any]], dict[str, list[str]]]:
    load_dotenv(ROOT / ".env")
    config_file = resolve_path(config_path or os.getenv("CONFIG_PATH", "config/settings.yaml"))
    stores_file = resolve_path(stores_path or os.getenv("STORES_PATH", "config/stores.yaml"))
    categories_file = resolve_path(
        categories_path or os.getenv("CATEGORIES_PATH", "config/categories.yaml")
    )

    raw = _read_yaml(config_file)
    settings = Settings.model_validate(raw)
    _apply_env_overrides(settings)

    stores_raw = _read_yaml(stores_file)
    stores = stores_raw.get("stores", stores_raw if isinstance(stores_raw, list) else [])
    categories = _read_yaml(categories_file)
    return settings, stores, categories


def _apply_env_overrides(settings: Settings) -> None:
    if os.getenv("AWS_S3_BUCKET"):
        settings.aws.s3_bucket = os.getenv("AWS_S3_BUCKET", settings.aws.s3_bucket)
        settings.aws.enabled = True
    if os.getenv("AWS_S3_PREFIX"):
        settings.aws.s3_prefix = os.getenv("AWS_S3_PREFIX", settings.aws.s3_prefix)
    if os.getenv("AWS_DEFAULT_REGION"):
        settings.aws.region = os.getenv("AWS_DEFAULT_REGION", settings.aws.region)
    if os.getenv("AWS_PROFILE"):
        settings.aws.profile_name = os.getenv("AWS_PROFILE", settings.aws.profile_name)
    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        settings.app.dry_run = True
