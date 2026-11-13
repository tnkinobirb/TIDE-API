from tideapi.exceptions import AlreadyRegisteredError 
from tideapi.handlers import register_bundle
from tideapi.persistence import TIDEAPIStore
from tideapi_core import request_handlers
from threading import Thread, Barrier, Event
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path 
import sqlite3
import pytest
from threading import Lock, RLock 

class ObservableLock:
    def __init__(self, original_lock: Lock | RLock, attempting: Event, acquired: Event, continue_event: Event | None = None):
        self.original_lock = original_lock
        self.attempting = attempting
        self.acquired = acquired
        self.continue_event = continue_event

    def __enter__(self):
        self.attempting.set()
        self.original_lock.acquire()
        self.acquired.set()

        if self.continue_event is not None:
            if not self.continue_event.wait(timeout=5):
                self.original_lock.release()
                raise TimeoutError("Timed out while waiting to continue")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.original_lock.release()
        self.acquired.clear()
        return False



class TestFunctionLocks:
    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        bundle_dir: Path,
        tmp_path: Path
        
    ) -> None:
        monkeypatch.setattr(request_handlers, "STORE", None)
        monkeypatch.setattr(request_handlers, "TRACES", {})
        monkeypatch.setattr(request_handlers, "BUNDLES", {})
        monkeypatch.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
        monkeypatch.setattr(request_handlers, "REGISTERED_BUNDLES", {})
        monkeypatch.setattr(request_handlers.TIDEAPIStore, "ROOT", tmp_path)

    # Helpers

    def assert_empty_state(self, assert_store=True):
        rh = request_handlers
        assert rh.TRACES == {}
        assert rh.BUNDLES == {}
        assert rh.REGISTERED_BUNDLES == {}
        if assert_store:    
            assert rh.STORE is None
        else: assert isinstance(rh.STORE, TIDEAPIStore) 

    def snapshot_bundles_table(self, conn: sqlite3.Connection):
        tables = list(conn.execute('PRAGMA table_list').fetchall())
        rows = list(conn.execute("SELECT * FROM bundles").fetchall())
        cols = list(conn.execute("PRAGMA table_info(bundles)").fetchall())
        return (tables, cols, rows)
    
    def init_store(self):        
        store = request_handlers.TIDEAPIStore()
        request_handlers.STORE = store
        
        with store.apistore as conn: 
            store_snapshot = self.snapshot_bundles_table(conn)
        
        assert request_handlers.STORE is store 
        return store_snapshot, store

    def assert_tables(self, tables: list[tuple]):
        user_tables = [
            table for table in tables
            if not table[1].startswith("sqlite_")
        ]

        assert user_tables == [
            ('main', 'bundles', 'table', 2, 0, 0)
        ]

    def assert_table_cols(self, cols:list):
        assert cols == [
            (0, 'bundle_name', 'TEXT', 0, None, 1),
            (1, 'bundle', 'TEXT', 1, None, 0),
        ]

    def assert_valid_table_state(self, table_snapshot: tuple):
        tables = table_snapshot[0]
        cols = table_snapshot[1]
    
        self.assert_tables(tables)
        self.assert_table_cols(cols)

    def assert_valid_filled_table_state(self, table_snapshot: tuple[list, list, list], tide_bundle:str):
        self.assert_valid_table_state(table_snapshot)
        rows = table_snapshot[2]
        self.assert_valid_rows(rows, tide_bundle=tide_bundle)

    def assert_empty_store_state(self, table_snapshot: tuple[list, list, list]):
        self.assert_valid_table_state(table_snapshot)
        rows = table_snapshot[2]
        self.assert_valid_rows(rows, empty=True) 

    def assert_valid_rows(self, rows: list[tuple], empty=False, tide_bundle:str=None):
        if empty:
            assert not rows 
        else:
            if tide_bundle is None:
                raise RuntimeError("assert_valid_rows(empty=False,...) expects tide_bundle:str is not None!")
            assert len(rows) == 1
            assert len(rows[0]) == 2
            row = rows[0]
            assert row[0] == 'example.json'
            assert row[1] == tide_bundle

    # Tests
    
    def test_register_bundle_barrier(self, tide_bundle: str):
        self.assert_empty_state()
        barrier = Barrier(2, timeout=2)

        empty_snap, store = self.init_store()
        self.assert_empty_store_state(empty_snap)
        
        def worker():
            barrier.wait()
            register_bundle('example.json')

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(worker)
            b = threadpool.submit(worker)
            errors = [a.exception(), b.exception()]

        assert sum(e is None for e in errors) == 1 
        assert sum(isinstance(e, AlreadyRegisteredError) for e in errors) == 1 

        with store.apistore as conn:
            self.assert_valid_filled_table_state(self.snapshot_bundles_table(conn), tide_bundle)
    

    def test_register_bundle_contention(self, monkeypatch, tide_bundle: str):
        self.assert_empty_state()
        empty_snap, store = self.init_store()
        self.assert_empty_store_state(empty_snap)

        store_lock = store.lock

        a_attempting = Event()
        a_acquired = Event()
        allow_a_to_continue = Event()

        b_attempting = Event()
        b_acquired = Event()

        monkeypatch.setattr(store, "lock", ObservableLock(store_lock, a_attempting, a_acquired, allow_a_to_continue))

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(register_bundle, "example.json")

            assert a_attempting.wait(timeout=5)
            assert a_acquired.wait(timeout=5)

            monkeypatch.setattr(store, "lock", ObservableLock(store_lock, b_attempting, b_acquired))

            b = threadpool.submit(register_bundle, "example.json")

            assert b_attempting.wait(timeout=5)

            # assert `a` has acquired its lock
            assert a_acquired.is_set()
            assert store_lock.locked()

            # assert `b` has attempted lock acquisition but does not yet own it.
            assert not b_acquired.is_set()
            assert store_lock.locked()

            # allow `a` to complete registration and release the lock.
            allow_a_to_continue.set()
            
            # allow `a` has completed and released its lock.
            assert a.result(timeout=5) == {
                "result": "example.json",
            }
            assert not a_acquired.is_set()
            
            # assert `b` has now acquired the lock.
            assert b_acquired.wait(timeout=5)
            assert store_lock.locked()

            with pytest.raises(AlreadyRegisteredError):
                b.result(timeout=5)

            errors = [a.exception(timeout=5), b.exception(timeout=5)]

        assert sum(error is None for error in errors) == 1
        assert sum(isinstance(error, AlreadyRegisteredError) for error in errors) == 1

        with store.apistore as conn:
            self.assert_valid_filled_table_state(self.snapshot_bundles_table(conn), tide_bundle)


                

