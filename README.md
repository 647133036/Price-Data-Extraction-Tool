# Coles & Woolworths Price Data Extraction Tool

[![Version](https://img.shields.io/badge/version-0.0.1-blue.svg)](https://github.com/647133036/Price-Data-Extraction-Tool)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Version **0.0.1**. Local weekly collector for Coles and Woolworths product prices across Australian store locations.

Retailer settings, store lists, categories, schedule, and AWS upload are all YAML-driven.

## Features

- Weekly extraction for Coles and Woolworths
- Location-specific prices via configured store IDs and postcodes
- Product name, pack size, current price, unit price, promotion, URL, extraction date
- Deduplication on `(retailer, store_id, product_id)`
- CSV and JSON export, optional S3 upload
- Logging, retries, and a per-run success/failure summary
- Cron or in-process scheduler

## Requirements

- Python 3.11 or newer
- Network access to `coles.com.au` and `woolworths.com.au` for live runs

## Install

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the tool
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` for AWS or proxy overrides.

## Configuration

| File | Purpose |
| --- | --- |
| `config/settings.yaml` | Retailers, retries, output formats, weekly schedule, AWS |
| `config/stores.yaml` | Store IDs and locations for each state and territory |
| `config/categories.yaml` | Browse categories for a full catalogue |

Environment overrides:

- `AWS_S3_BUCKET`
- `AWS_S3_PREFIX`
- `AWS_DEFAULT_REGION`
- `AWS_PROFILE`
- `DRY_RUN=true`

## Usage

```bash
# Sample run that writes local files without calling live sites
python -m price_extractor --dry-run

# Live extraction for every enabled store and retailer
python -m price_extractor

# One retailer only
python -m price_extractor --retailer coles

# Cap volume while testing a live store
python -m price_extractor --retailer woolworths --max-products 50

# Stay resident and run on the configured weekly schedule
python -m price_extractor --schedule
```

`scripts/run_weekly.sh` is the same entrypoint for cron:

```bash
# Wednesday 06:00 Australia/Sydney
0 6 * * 3 /path/to/project/scripts/run_weekly.sh >> /path/to/project/logs/cron.log 2>&1
```

## Output

Files land in `data/output/`:

- `prices_YYYY-MM-DD.csv`
- `prices_YYYY-MM-DD.json`
- `summary_YYYY-MM-DD.json`

Each product row includes:

- product name, brand, package size
- current price and unit price (`$/kg`, `$/L`)
- promotional price, previous price, promotion text
- retailer, store id, store name, location, state, postcode
- product URL and extraction date

The summary records successful stores, failed stores, duplicate counts, export paths, upload paths, and per-category errors.

When `aws.enabled` is true and `s3_bucket` is set, files upload to `s3://<bucket>/<prefix>/<date>/`.

## Logging and retries

- Logs go to stdout and `logs/extractor.log`
- HTTP 429/5xx and network errors retry with exponential backoff
- A failed category continues with the rest of the store
- Failed stores are recorded in the run summary

Live requests use the public catalogue JSON loaded by the retailer websites. Coles store context is sent with fulfillment cookies. Woolworths is bootstrapped against the configured postcode. Both sites may rate-limit datacenter IPs. Use `--dry-run` for a guaranteed local run, or set `HTTP_PROXY` / `HTTPS_PROXY` for an Australian proxy.

## Tests

```bash
pytest
```

## License

MIT. See [LICENSE](LICENSE).

This project is independent and is not affiliated with Coles or Woolworths.
