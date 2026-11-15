from pathlib import Path
from threading import RLock, Lock

# Locks
BUNDLE_PATH = Path(__file__).parents[2] / 'bundles'
REGISTER_LOCK = Lock()
STORE_INIT_LOCK = RLock()
