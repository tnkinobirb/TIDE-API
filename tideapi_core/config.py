import os
from pathlib import Path

PROJECT_DIR = Path(__file__).parents[1]

BUNDLE_DIR = Path(
    os.environ.get("TIDEAPI_BUNDLE_DIR", PROJECT_DIR / "bundles")
).expanduser().resolve()

DB_PATH = Path(
    os.environ.get("TIDEAPI_DATABASE_PATH", PROJECT_DIR / "bundles.db")
).expanduser().resolve()
