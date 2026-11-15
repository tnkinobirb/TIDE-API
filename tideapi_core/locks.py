from threading import RLock, Lock

REGISTER_LOCK = Lock()
STORE_INIT_LOCK = RLock()
