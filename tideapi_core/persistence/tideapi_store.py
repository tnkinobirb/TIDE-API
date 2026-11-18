'''
    TIDE-API PERSISTENCE INTERFACE

    STORE: SQLITE3

    ROLE: PROVIDE AN INTERFACE TO ENABLE THE PERSISTENCE OF TIDE OBJECTS

    SUPPORTED TIDE OBJECTS: 
        - BUNDLE (as JSON string)
'''

import sqlite3
from pathlib import Path
from threading import RLock
from contextlib import contextmanager
from collections.abc import Generator
from tideapi_core.config import DB_PATH as DEFAULT_DB_PATH
from tideapi_core.exceptions import (
    APIStoreLookupError,
    DataValidationError,
    AlreadyRegisteredError,
    InvalidAPIStoreConfigurationError,
)

class TIDEAPIStore:
    '''
    TIDE-API PERSISTENCE INTERFACE
        Initialises or connects to a TIDEAPIStore sqlite3 `bundles.db` database.
        Provides CRUD operations over persisted TIDE objects supported by TIDE-API. 

        SUPPORTED TIDE OBJECTS: 
            - BUNDLE (as JSON string)

        TIDEAPIStore's default database path may be configured
    '''

    DB_PATH = DEFAULT_DB_PATH
    def __init__(self, db_path: Path | None = None) -> None:
        '''Initialise sqlite3 database and associated lock'''
        self.DB_PATH = self.__class__.DB_PATH if db_path is None else db_path
        self.create_bundle_store()
        self.lock = RLock()

    def connect_to_bundle_db(self) -> sqlite3.Connection:
        '''Initialise connection to sqlite3 database'''
        conn = sqlite3.connect(self.DB_PATH)
        return conn

    @staticmethod 
    def get_cursor(conn: sqlite3.Connection) -> sqlite3.Cursor:
        '''Retrieve sqlite3 database cursor'''
        if not isinstance(conn, sqlite3.Connection):
            raise TypeError("Invalid connection type")
        return conn.cursor()

    @property
    @contextmanager
    def apistore(self) -> Generator[sqlite3.Connection, None, None]:
        '''Context manager for handling and closing database connections'''
        conn = self.connect_to_bundle_db()

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_bundle_store(self) -> None:
        '''
        Initialise sqlite3 database if one doesn't exist.
        Otherwise, assert the existing .db configuration.
        '''
        if self.DB_PATH.exists():
            if self.DB_PATH.is_file():
                with self.apistore as conn:
                    self._assert_expected_api_store_config(conn)
            else:
                raise InvalidAPIStoreConfigurationError(
                    f"DB_PATH {self.DB_PATH} exists but is not a file!"
                )
        else:
            with self.apistore as conn:
                self._init_bundles_db(conn)

                try:
                    self._assert_expected_api_store_config(conn)
                except Exception as e:
                    raise InvalidAPIStoreConfigurationError(
                        "`bundles.db` creation failed during configuration. \n" \
                        "This must be a programming error. \n" \
                        f"e = {type(e).__name__} {str(e)}. \n" 
                    )

    def set(self, bundle_name: str, bundle: str, replace:bool=False) -> None:
        '''Persist a .json string as a bundle keyed via bundle_name'''
        if not isinstance(replace, bool):
            raise DataValidationError("Store.set(replace=...) must be a bool!")

        if any(not isinstance(inp, str) for inp in [bundle_name, bundle]):
            raise DataValidationError("Store.set() only accepts str values")

        with self.lock:
    	    with self.apistore as conn:
                # exists
                cursor = self.get_cursor(conn).execute(
                    "SELECT EXISTS(SELECT 1 FROM bundles WHERE bundle_name = ?)", (bundle_name, )
                )

                exists = bool(cursor.fetchone()[0])

                if exists:
                    if replace:
                        cursor = self.get_cursor(conn).execute(
                            "DELETE FROM bundles WHERE bundle_name=? RETURNING bundle", (bundle_name, )
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise APIStoreLookupError(f"Store.set(replace=True) via bundle_name: {bundle_name} not found!")                
                    else:
                        raise AlreadyRegisteredError(
                            f"{bundle_name} is already registered in bundles.db" \
                            "\n Please use .set(replace=True) to override bundle contents"
                            )

                self.get_cursor(conn).execute(
                    "INSERT INTO bundles (bundle_name, bundle)" \
                    "VALUES (?, ?)", (bundle_name, bundle) 
	            )

    def get(self, bundle_name: str) -> str:
        '''Retrieve a persisted bundle via bundle_name'''
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.get() only accepts str values")
        with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute(
                    "SELECT bundle FROM bundles WHERE bundle_name=? LIMIT 1", (bundle_name,)
                )
                row = cursor.fetchone()
                if row is None:
                    raise APIStoreLookupError(f"bundle_name {bundle_name} not found!")
                return row[0]

    def pop(self, bundle_name: str) -> str:
        '''Retrieve and remove a persisted bundle from the database via bundle_name''' 
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.pop() only accepts str values")

        with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute(
                    "DELETE FROM bundles WHERE bundle_name=? RETURNING bundle", (bundle_name, )
                )
                row = cursor.fetchone()
                if row is None:
                    raise APIStoreLookupError("bundle_name {bundle_name} not found!")
                return row[0]

    def exists(self, bundle_name: str) -> bool:
        '''Confirm whether a bundle is persisted via bundle_name'''
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.exists() only accepts str values")

        with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute(
                    "SELECT EXISTS(SELECT 1 FROM bundles WHERE bundle_name = ?)", (bundle_name, )
                )
                exists = bool(cursor.fetchone()[0])
                return exists

    def bundles(self) -> list[str]:
        '''List available persisted bundles via their associated bundle_name'''
        with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute("SELECT bundle_name FROM bundles")
                row = cursor.fetchall()
                if row is None:
                    return []

                return [tpl[0] for tpl in row]

    def _init_bundles_db(self, conn: sqlite3.Connection) -> None:
        '''Configure the `bundles` table'''
        cursor = self.get_cursor(conn)
        cursor.execute('create table bundles(bundle_name TEXT PRIMARY KEY, bundle TEXT NOT NULL)')

    def _assert_expected_api_store_config(self, conn: sqlite3.Connection) -> None:
        '''Assert the expected configuration of `bundles.db`'''
        cols = []
        try:
            assert self.DB_PATH.name.lower() == 'bundles.db'
            cursor = self.get_cursor(conn)
            tables = list(cursor.execute(
                "SELECT name FROM sqlite_schema " \
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))

            assert len(tables) == 1, f"len(tables) {len(tables)} == 1"
            assert len(tables[0]) == 1, "len(tables[0]) == 1"
            assert tables[0][0] == 'bundles', f"tables[0][0] == 'bundles'"

            cursor.execute("SELECT * FROM bundles")
            cols = [col[0] for col in cursor.description]
            assert len(cols) == 2, "len(cols) == 2"
            assert cols[0] == "bundle_name", 'cols[0] == "bundle_name"'
            assert cols[1] == "bundle", 'cols[1] == "bundle"'

            expected_cols = [
                (0, 'bundle_name', 'TEXT', 0, None, 1),
                (1, 'bundle', 'TEXT', 1, None, 0)
            ]

            cursor = cursor.execute("PRAGMA table_info(bundles)")
            cols = cursor.fetchall()
            assert len(cols) == len(expected_cols), "PRAGMA lrn mismatch"
            assert all([cols[idx] == expected_cols[idx] for idx, _ in enumerate(cols)]), f"PRAGMA col mismatch: {cols}"
        except Exception as e:
            raise InvalidAPIStoreConfigurationError(
                "`bundles.db` exists but its configuration is invalid. \n" \
                "Expects a store with a `bundles` table containing `bundle_name` and `bundle` cols ONLY! \n" \
                "This error is used to avoid accidental data corruption \n" \
                f"e = {type(e).__name__} {str(e)}{f'. \n cols = {cols}.' if cols else '.'}" \
            )
