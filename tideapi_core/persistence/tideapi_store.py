'''
    TIDE-API PERSISTENCE INTERFACE

    SUPPORTED STORES:
    - SQLITE3
    - POSTGRESQL

    ROLE: PROVIDE AN INTERFACE TO ENABLE THE PERSISTENCE OF TIDE OBJECTS

    SUPPORTED TIDE OBJECTS:
        - BUNDLE (as JSON string)
'''
import os
import sqlite3
import psycopg
from dotenv import load_dotenv
from pathlib import Path
from threading import Lock
from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.errors import UniqueViolation
from collections.abc import Generator
from tideapi_core.helpers.native import validate_tide_bundle, validate_bundle_name
from tideapi_core.config import SQLITE_DB_PATH as DEFAULT_DB_PATH
from tideapi_core.exceptions import (
    APIStoreLookupError,
    DataValidationError,
    AlreadyRegisteredError,
    InvalidAPIStoreConfigurationError,
)

class TIDEPSQLStore:
    '''
    TIDE-API POSTGRESQL PERSISTENCE INTERFACE
        Connects to a PostgreSQL `bundles` database.
        Provides CRUD operations over persisted TIDE objects supported by TIDE-API.

        SUPPORTED TIDE OBJECTS:
            - BUNDLE (as JSON string)
    '''
    def __init__(self):
        load_dotenv()

        self.pool = ConnectionPool(
            conninfo="host=127.0.0.1 port=5432 dbname=bundles user=tideapi",
            kwargs={
                "password": os.environ["TIDEAPI_PSQL_DB_PASSWORD"],
                "connect_timeout": 5,
            },
            min_size=1,
            max_size=10,
            open=True,
        )

        try:
            with self.apistore as conn:
                self._assert_expected_api_store_config(conn)
        except Exception:
            self.pool.close()
            raise

    @staticmethod
    def get_cursor(conn: psycopg.Connection) -> psycopg.Cursor:
        '''Retrieve PostgreSQL database cursor'''
        if not isinstance(conn, psycopg.Connection):
            raise TypeError("Invalid connection type")
        return conn.cursor()

    @property
    @contextmanager
    def apistore(self) -> Generator[psycopg.Connection, None, None]:
        with self.pool.connection() as conn:
            yield conn

    def set(self, bundle_name: str, bundle: Path | str, replace:bool=False) -> None:
        '''Persist a .json string as a bundle keyed via bundle_name'''
        validate_bundle_name(bundle_name)
        bundle = validate_tide_bundle(bundle)

        if not isinstance(replace, bool):
            raise DataValidationError("Store.set(replace=...) must be a bool!")

        if any(not isinstance(inp, str) for inp in [bundle_name, bundle]):
            raise DataValidationError("Store.set() only accepts str values")

        with self.apistore as conn:
            try:
                if replace:
                    self.get_cursor(conn).execute(
                        "INSERT INTO tide.bundles (bundle_name, bundle) VALUES (%s, %s)"
                        " ON CONFLICT (bundle_name) DO UPDATE SET bundle = EXCLUDED.bundle",
                        (bundle_name, bundle)
                    )
                else:
                    self.get_cursor(conn).execute(
                        "INSERT INTO tide.bundles (bundle_name, bundle) "
                        "VALUES (%s, %s)", (bundle_name, bundle)
                    )
            except UniqueViolation as e:
                raise AlreadyRegisteredError(
                    f"{bundle_name} is already registered in tide.bundles" \
                    "\n Please use .set(replace=True) to override bundle contents"
                ) from e

    def get(self, bundle_name: str) -> str:
        '''Retrieve a persisted bundle via bundle_name'''
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.get() only accepts str values")
        with self.apistore as conn:
            cursor = self.get_cursor(conn).execute(
                "SELECT bundle FROM tide.bundles WHERE bundle_name=%s LIMIT 1", (bundle_name,)
            )
            row = cursor.fetchone()
            if row is None:
                raise APIStoreLookupError(f"bundle_name {bundle_name} not found!")
            return row[0]

    def pop(self, bundle_name: str) -> str:
        '''Retrieve and remove a persisted bundle from the database via bundle_name'''
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.pop() only accepts str values")

        with self.apistore as conn:
            cursor = self.get_cursor(conn).execute(
                "DELETE FROM tide.bundles WHERE bundle_name=%s RETURNING bundle", (bundle_name, )
            )
            row = cursor.fetchone()
            if row is None:
                raise APIStoreLookupError(f"bundle_name {bundle_name} not found!")
            return row[0]

    def exists(self, bundle_name: str) -> bool:
        '''Confirm whether a bundle is persisted via bundle_name'''
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.exists() only accepts str values")

        with self.apistore as conn:
            cursor = self.get_cursor(conn).execute(
                "SELECT EXISTS(SELECT 1 FROM tide.bundles WHERE bundle_name = %s)", (bundle_name, )
            )
            exists = bool(cursor.fetchone()[0])
            return exists

    def bundles(self) -> list[str]:
        '''List available persisted bundles via their associated bundle_name'''
        with self.apistore as conn:
            cursor = self.get_cursor(conn).execute("SELECT bundle_name FROM tide.bundles")
            row = cursor.fetchall()
            if row is None:
                return []

            return [tpl[0] for tpl in row]

    def close(self) -> None:
        self.pool.close()

    def _assert_expected_api_store_config(self, conn: psycopg.Connection) -> None:
        '''Assert the expected configuration of the PostgreSQL bundle store'''
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(message)

        cols = []
        try:
            cursor = self.get_cursor(conn)

            cursor.execute("SELECT current_database()")
            require(cursor.fetchone()[0] == 'bundles', "Database name must be bundles")

            cursor.execute(
                "SELECT c.relname, c.relkind "
                "FROM pg_catalog.pg_class AS c "
                "JOIN pg_catalog.pg_namespace AS n "
                "ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'tide' "
                "AND c.relkind IN ('r', 'p', 'f')"
            )
            tables = cursor.fetchall()

            require(len(tables) == 1, f"len(tables) {len(tables)} == 1")
            require(tables[0] == ('bundles', 'r'), "Expected bundles table")

            cursor.execute("SELECT * FROM tide.bundles LIMIT 0")
            cols = [col[0] for col in cursor.description]

            require(len(cols) == 2, "len(cols) == 2")
            require(cols[0] == "bundle_name", 'cols[0] == "bundle_name"')
            require(cols[1] == "bundle", 'cols[1] == "bundle"')

            expected_cols = [
                (1, 'bundle_name', 'text', 'NO', None, None),
                (2, 'bundle', 'text', 'NO', None, None)
            ]

            cursor.execute(
                "SELECT ordinal_position, column_name, data_type, "
                "is_nullable, column_default, domain_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'tide' "
                "AND table_name = 'bundles' "
                "ORDER BY ordinal_position"
            )
            cols = cursor.fetchall()

            require(len(cols) == len(expected_cols), "Column length mismatch")
            require(cols == expected_cols, f"Column mismatch: {cols}")

            cursor.execute(
                "SELECT a.attname "
                "FROM pg_catalog.pg_constraint AS c "
                "JOIN pg_catalog.pg_attribute AS a "
                "ON a.attrelid = c.conrelid "
                "AND a.attnum = ANY(c.conkey) "
                "WHERE c.conrelid = 'tide.bundles'::regclass "
                "AND c.contype = 'p'"
            )
            primary_key = cursor.fetchall()

            require(
                primary_key == [('bundle_name',)],
                f"Primary key mismatch: {primary_key}"
            )

        except Exception as e:
            raise InvalidAPIStoreConfigurationError(
                "PostgreSQL bundle store configuration is invalid. \n"
                "Expects a store with a `bundles` table containing "
                "`bundle_name` and `bundle` cols ONLY! \n"
                "This error is used to avoid accidental data corruption \n"
                f"e = {type(e).__name__} {str(e)}"
                + (f". \n cols = {cols}." if cols else ".")
            ) from e

class TIDEAPIStore:
    '''
    TIDE-API SQLite PERSISTENCE INTERFACE
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
        self.lock = Lock()

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
        except Exception:
            conn.rollback()
            raise
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

    def set(self, bundle_name: str, bundle: Path | str, replace:bool=False) -> None:
        '''Persist a .json string as a bundle keyed via bundle_name'''
        validate_bundle_name(bundle_name)
        bundle = validate_tide_bundle(bundle)

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
                    raise APIStoreLookupError(f"bundle_name {bundle_name} not found!")
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
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(message)

        cols = []
        try:
            require(self.DB_PATH.name.lower() == 'bundles.db', "DB_PATH name must be bundles.db")
            cursor = self.get_cursor(conn)
            tables = list(cursor.execute(
                "SELECT name FROM sqlite_schema " \
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))

            require(len(tables) == 1, f"len(tables) {len(tables)} == 1")
            require(len(tables[0]) == 1, "len(tables[0]) == 1")
            require(tables[0][0] == 'bundles', "tables[0][0] == 'bundles'")

            cursor.execute("SELECT * FROM bundles")
            cols = [col[0] for col in cursor.description]
            require(len(cols) == 2, "len(cols) == 2")
            require(cols[0] == "bundle_name", 'cols[0] == "bundle_name"')
            require(cols[1] == "bundle", 'cols[1] == "bundle"')

            expected_cols = [
                (0, 'bundle_name', 'TEXT', 0, None, 1),
                (1, 'bundle', 'TEXT', 1, None, 0)
            ]

            cursor = cursor.execute("PRAGMA table_info(bundles)")
            cols = cursor.fetchall()
            require(len(cols) == len(expected_cols), "PRAGMA length mismatch")
            require(all([cols[idx] == expected_cols[idx] for idx, _ in enumerate(cols)]), f"PRAGMA col mismatch: {cols}")
        except Exception as e:
            raise InvalidAPIStoreConfigurationError(
                "`bundles.db` exists but its configuration is invalid. \n" \
                "Expects a store with a `bundles` table containing `bundle_name` and `bundle` cols ONLY! \n" \
                "This error is used to avoid accidental data corruption \n" \
                f"e = {type(e).__name__} {str(e)}"
                + (f". \n cols = {cols}." if cols else ".")
            )
