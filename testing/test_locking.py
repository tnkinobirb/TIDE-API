import pytest
import sqlite3

from pathlib import Path
from types import TracebackType
from typing import Callable, Any
from threading import Lock, RLock, Barrier, Event
from concurrent.futures import ThreadPoolExecutor

from tideapi_core import request_handlers
from tideapi_core.persistence import tideapi_store
from tideapi.handlers import persist_bundle, load_trace
from tideapi.exceptions import AlreadyRegisteredError
from tideapi.persistence import TIDEAPIStore
from tideapi_core.request_handlers import init_store

class ObservableLock:
    def __init__(self, original_lock: Lock | RLock, attempting: Event, acquired: Event, released_event: Event, continue_event: Event | None = None, contended: Event | None = None) -> None:
        self.original_lock = original_lock
        self.attempting = attempting
        self.acquired = acquired
        self.continue_event = continue_event
        self.released = released_event
        self.contended = contended

    def __enter__(self) -> "ObservableLock":
        self.attempting.set()
        if not self.original_lock.acquire(blocking=False):
            if self.contended is not None:
                self.contended.set()
            self.original_lock.acquire()
        self.acquired.set()

        if self.continue_event is not None:
            if not self.continue_event.wait(timeout=5):
                self.original_lock.release()
                raise TimeoutError("Timed out while waiting to continue")
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.original_lock.release()
        self.released.set()
        return False

def locking_test_setups() -> list[Any]:

    load_trace_contention = pytest.param(
        None,
        load_trace,
        None,
        lambda result: result == {'result': list(request_handlers.TRACES.keys())[0]} and len(request_handlers.TRACES.keys()) == 1,
        "example.json",
        None,
        True,
        True,
        "register",
        id="load_trace_contention",
    )

    tideapistore_contention = pytest.param(
        None,
        persist_bundle,
        AlreadyRegisteredError,
        lambda result: result == {"result": "example.json"},
        "example.json",
        None,
        True,
        True,
        "store",
        id="tideapistore_contention",
    )

    store_initialisation_contention = pytest.param(
        None,
        init_store,
        None,
        lambda result: result is request_handlers.STORE,
        None,
        None,
        True,
        False,
        "store_init",
        id="store_initialisation_contention",
    )

    return [
        load_trace_contention,
        tideapistore_contention,
        store_initialisation_contention
    ]

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
        monkeypatch.setattr(request_handlers, "BUNDLE_DIR", bundle_dir)
        monkeypatch.setattr(request_handlers.TIDEAPIStore, "DB_PATH", tmp_path / "bundles.db")

    # HELPERS
    @staticmethod
    def assert_empty_state(assert_store: bool=True) -> bool:

        rh = request_handlers
        assert rh.TRACES == {}
        if assert_store:
            assert rh.STORE is None
        else: assert isinstance(rh.STORE, TIDEAPIStore)

        return True

    @staticmethod
    def snapshot_bundles_table(conn: sqlite3.Connection) -> tuple[list[tuple], list[tuple], list[tuple]]:
        tables = list(conn.execute('PRAGMA table_list').fetchall())
        rows = list(conn.execute("SELECT * FROM bundles").fetchall())
        cols = list(conn.execute("PRAGMA table_info(bundles)").fetchall())
        return (tables, cols, rows)

    @staticmethod
    def helper_init_store() -> tuple[tuple[list[tuple], list[tuple], list[tuple]], TIDEAPIStore]:
        store = request_handlers.TIDEAPIStore()
        request_handlers.STORE = store

        with store.apistore as conn:
            store_snapshot = TestFunctionLocks.snapshot_bundles_table(conn)

        assert request_handlers.STORE is store
        return store_snapshot, store

    @staticmethod
    def assert_tables(tables: list[tuple]) -> None:
        user_tables = [
            table for table in tables
            if not table[1].startswith("sqlite_")
        ]

        assert user_tables == [
            ('main', 'bundles', 'table', 2, 0, 0)
        ]

    @staticmethod
    def assert_table_cols(cols:list) -> None:
        assert cols == [
            (0, 'bundle_name', 'TEXT', 0, None, 1),
            (1, 'bundle', 'TEXT', 1, None, 0),
        ]

    @staticmethod
    def assert_valid_table_state(table_snapshot: tuple) -> None:
        tables = table_snapshot[0]
        cols = table_snapshot[1]

        TestFunctionLocks.assert_tables(tables)
        TestFunctionLocks.assert_table_cols(cols)

    @staticmethod
    def assert_valid_filled_table_state(table_snapshot: tuple[list, list, list], tide_bundle:str) -> None:
        TestFunctionLocks.assert_valid_table_state(table_snapshot)
        rows = table_snapshot[2]
        TestFunctionLocks.assert_valid_rows(rows, tide_bundle=tide_bundle)

    @staticmethod
    def assert_empty_store_state(table_snapshot: tuple[list, list, list]) -> None:
        TestFunctionLocks.assert_valid_table_state(table_snapshot)
        rows = table_snapshot[2]
        TestFunctionLocks.assert_valid_rows(rows, empty=True)

    @staticmethod
    def assert_valid_rows(rows: list[tuple], empty:bool=False, tide_bundle:str|None=None) -> None:
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

    # TESTS
    def test_init_store_concurrently_returns_equal_stores(self) -> None:
        self.assert_empty_state()

        barrier = Barrier(2)

        def worker() -> TIDEAPIStore:
            barrier.wait(timeout=5)
            return init_store()

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(worker)
            b = threadpool.submit(worker)

            store_a = a.result(timeout=5)
            store_b = b.result(timeout=5)

        assert store_a is store_b
        assert request_handlers.STORE is store_a

        stores = list(request_handlers.TIDEAPIStore.DB_PATH.parent.iterdir())

        assert len(stores) == 1
        assert stores[0].name == "bundles.db"

    @pytest.mark.parametrize((
        'init_context',
        'func',
        'expected_contention_error',
        'result_validator',
        'args',
        'kwargs',
        'assert_empty_store_init',
        'assert_filled_store_exit',
        'lock_kind'
    ), locking_test_setups())
    def test_lock_contention(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tide_bundle: str,
        init_context: Callable | None,
        lock_kind:str,
        func: Callable,
        expected_contention_error: type[Exception] | None,
        result_validator: Callable,
        args: Any | tuple[Any, ...],
        kwargs: dict | None,
        assert_empty_store_init:bool,
        assert_filled_store_exit:bool,
    ) -> None:

        if not isinstance(args, tuple):
            if args is None:
                args = ()
            else:
                args = (args,)
        if kwargs is None:
            kwargs = {}

        self.assert_empty_state()

        self.contention_tester(
            monkeypatch=monkeypatch,
            tide_bundle=tide_bundle,
            init_context=init_context,
            func=func,
            lock_kind=lock_kind,
            expected_contention_error=expected_contention_error,
            result_validator=result_validator,
            args=args,
            assert_empty_store_init=assert_empty_store_init,
            assert_filled_store_exit=assert_filled_store_exit,
            **kwargs
        )

    def contention_tester(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tide_bundle: str,
        lock_kind:str,
        func: Callable,
        init_context:Callable|None=None,
        expected_contention_error:type[Exception]|None=None,
        result_validator:Callable|None=None,
        args:tuple[Any, ...]|None=None,
        assert_empty_store_init:bool=True,
        assert_filled_store_exit:bool=True,
        **kwargs: Any
    ) -> None:
        self.assert_empty_state()

        if not isinstance(args, tuple):
            args = (args,)

        if lock_kind == 'store_init':
            assert request_handlers.STORE is None
            assert not request_handlers.TIDEAPIStore.DB_PATH.exists()
            snap = None
            store = None
        else:
            if init_context is not None:
                init_context()
                store = request_handlers.STORE

                with store.apistore as conn:
                    snap = self.snapshot_bundles_table(conn)
            else:
                snap, store = self.helper_init_store()

            if assert_empty_store_init:
                self.assert_empty_store_state(snap)
            else:
                self.assert_valid_filled_table_state(snap, tide_bundle)

        if lock_kind == "store":
            lock_owner = store
            lock_attribute = "lock"
        elif lock_kind == "register":
            lock_owner = request_handlers
            lock_attribute = "REGISTER_LOCK"
        elif lock_kind == 'store_init':
            lock_owner = request_handlers
            lock_attribute = "STORE_INIT_LOCK"
        else:
            raise ValueError(f"Unknown lock kind: {lock_kind}")

        lock = getattr(lock_owner, lock_attribute)

        a_attempting = Event()
        a_acquired = Event()
        a_released = Event()
        allow_a_to_continue = Event()

        b_attempting = Event()
        b_acquired = Event()
        b_released = Event()
        b_contended = Event()

        monkeypatch.setattr(lock_owner, lock_attribute, ObservableLock(lock, a_attempting, a_acquired, a_released, allow_a_to_continue))

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(func, *args, **kwargs)

            assert a_attempting.wait(timeout=5)
            assert a_acquired.wait(timeout=5)

            monkeypatch.setattr(lock_owner, lock_attribute, ObservableLock(lock, b_attempting, b_acquired, b_released, contended=b_contended))


            b = threadpool.submit(func, *args, **kwargs)

            assert b_attempting.wait(timeout=5)
            assert b_contended.wait(timeout=5)

            # assert `a` has acquired its lock
            assert a_acquired.is_set()
            assert lock.locked()

            # assert `b` has attempted lock acquisition but does not yet own it.
            assert not b_acquired.is_set()
            assert lock.locked()

            # allow `a` to complete registration and release the lock.
            allow_a_to_continue.set()

            # allow `a` has completed and released its lock.
            assert result_validator(a.result(timeout=5))
            assert a_released.wait(timeout=5)

            # assert `b` has now acquired the lock.
            assert b_acquired.wait(timeout=5)

            if expected_contention_error is not None:
                with pytest.raises(expected_contention_error):
                    b.result(timeout=5)
            else:
                if not callable(result_validator):
                    raise RuntimeError('result_validator was not a callable!')
                assert result_validator(b.result(timeout=5))
            assert b_released.is_set()

            errors = [a.exception(timeout=5), b.exception(timeout=5)]
        num_of_expected_errors = 0 if expected_contention_error is None else 1
        assert sum(isinstance(error, Exception) for error in errors) == num_of_expected_errors

        if lock_kind == "store_init":
            store = request_handlers.STORE

        with store.apistore as conn:
            snap = self.snapshot_bundles_table(conn)
            if assert_filled_store_exit:
                self.assert_valid_filled_table_state(snap, tide_bundle)
            else:
                self.assert_empty_store_state(snap)

    def test_persist_bundle_barrier(self, monkeypatch: pytest.MonkeyPatch, tide_bundle: str) -> None:
        self.assert_empty_state()
        monkeypatch.setattr(tideapi_store, "validate_tide_bundle", lambda path: tide_bundle)
        barrier = Barrier(2, timeout=5)

        empty_snap, store = self.helper_init_store()
        self.assert_empty_store_state(empty_snap)

        def worker() -> None:
            barrier.wait()
            persist_bundle('example.json')

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(worker)
            b = threadpool.submit(worker)
            errors = [a.exception(timeout=5), b.exception(timeout=5)]

        assert sum(e is None for e in errors) == 1
        assert sum(isinstance(e, AlreadyRegisteredError) for e in errors) == 1

        with store.apistore as conn:
            self.assert_valid_filled_table_state(self.snapshot_bundles_table(conn), tide_bundle)

    def test_persist_bundle_contention(self, monkeypatch: pytest.MonkeyPatch, tide_bundle: str) -> None:
        self.assert_empty_state()
        empty_snap, store = self.helper_init_store()
        self.assert_empty_store_state(empty_snap)

        store_lock = store.lock

        a_attempting = Event()
        a_acquired = Event()
        a_released = Event()
        allow_a_to_continue = Event()

        b_attempting = Event()
        b_acquired = Event()
        b_released = Event()
        b_contended = Event()

        monkeypatch.setattr(store, "lock", ObservableLock(store_lock, a_attempting, a_acquired, a_released, allow_a_to_continue))

        with ThreadPoolExecutor(max_workers=2) as threadpool:
            a = threadpool.submit(persist_bundle, "example.json")

            if not a_attempting.wait(timeout=5):
                if a.done():
                    a.result()  # Re-raises the worker's original exception

                pytest.fail("Worker never attempted to acquire the lock")
            assert a_acquired.wait(timeout=5)

            monkeypatch.setattr(store, "lock", ObservableLock(store_lock, b_attempting, b_acquired, b_released, contended=b_contended))

            b = threadpool.submit(persist_bundle, "example.json")

            assert b_attempting.wait(timeout=5)
            assert b_contended.wait(timeout=5)

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
            assert a_released.is_set()

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
