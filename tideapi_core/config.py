'''
    TIDE-API CONFIGURATION
'''

import os
from pathlib import Path

# PATH CONFIGS
TIDEAPI_DIR = Path(__file__).parents[1]

BUNDLE_DIR = Path(
    os.environ.get("TIDEAPI_BUNDLE_DIR", TIDEAPI_DIR / "bundles")
).expanduser().resolve()

DB_PATH = Path(
    os.environ.get("TIDEAPI_DATABASE_PATH", TIDEAPI_DIR / "bundles.db")
).expanduser().resolve()

# BEHAVIOUR TOGGLES

INCLUDE_BUNDLE_DIR_AT_INIT = os.environ.get("TIDEAPI_INCLUDE_BUNDLE_DIR_AT_INIT", "true").lower() == "true"
