'''
    TIDE-API CONFIGURATION

    PATH CONFIGS:
        TIDEAPI_DIR - The TIDE-API directory
        BUNDLE_DIR  - The directory search for local bundle.json
        SQLITE_DB_PATH     - The path of a TIDEAPIStore's sqlite3 `bundles.db` instance

    BUNDLES:
'''
import os
from pathlib import Path

# PATH CONFIGS
TIDEAPI_DIR = Path(__file__).parents[1]

# Point to a local directory containing bundle.json files
BUNDLE_DIR = Path(
    os.environ.get("TIDEAPI_BUNDLE_DIR", TIDEAPI_DIR / "bundles")
).expanduser().resolve()

# Point to a TIDEAPIStore initiated sqlite3-database instance
SQLITE_DB_PATH = Path(
    os.environ.get("TIDEAPI_SQLITE_DB_PATH", TIDEAPI_DIR / "data" /  "bundles.db")
).expanduser().resolve()

# BEHAVIOUR TOGGLES

# Include bundle
INCLUDE_BUNDLE_DIR_WHEN_LOADING = os.environ.get("TIDEAPI_INCLUDE_BUNDLE_DIR_WHEN_LOADING", "true").lower() == "true"
