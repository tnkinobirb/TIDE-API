import sqlite3
from pathlib import Path 
from contextlib import contextmanager
from threading import RLock
from tideapi.exceptions import InvalidAPIStoreConfigurationError, DataValidationError, APIStoreLookupError

class TIDEAPIStore:

    ROOT = Path(__file__).parent 
    BUNDLE_PATH = ROOT / 'bundles.db'
    VERBOSE=True

    def __init__(self):
        self.create_bundle_store()
        self.lock = RLock()

    def connect_to_bundle_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.BUNDLE_PATH)
        return conn

    @staticmethod
    def get_cursor(conn: sqlite3.Connection) -> sqlite3.Cursor:
        if not isinstance(conn, sqlite3.Connection):
            raise TypeError("Invalid connection type")
        return conn.cursor()

    @property
    @contextmanager
    def apistore(self):
        conn = self.connect_to_bundle_db()

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_bundle_store(self):
        if self.BUNDLE_PATH.exists():
            if self.BUNDLE_PATH.is_file():
                with self.apistore as conn:
                    self._assert_expected_api_store_config(conn)
                    if self.VERBOSE:
                        print("`bundles.db` exists and is valid. Using connection.")
            else:
                raise InvalidAPIStoreConfigurationError(
                    f"BUNDLE_PATH {self.BUNDLE_PATH} exists but is not a file!"
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

                if self.VERBOSE:
                    print("`bundles.db` initialised and configured.")    

    def set(self, bundle_name: str, bundle: str) -> None:
        if any(not isinstance(inp, str) for inp in [bundle_name, bundle]):
            raise DataValidationError("Store.set() only accepts str values")
        with self.lock:
    	    with self.apistore as conn:
                self.get_cursor(conn).execute(
                    "INSERT INTO bundles (bundle_name, bundle)" \
                    "VALUES (?, ?)", (bundle_name, bundle) 
	        )

    def get(self, bundle_name: str) -> str:
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
        if not isinstance(bundle_name, str):
            raise DataValidationError("Store.pop() only accepts str values")

        result = self.get(bundle_name)

        with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute(
                    "DELETE FROM bundles WHERE bundle_name=?", (bundle_name, )
                )
                return result

    def exists(self, bundle_name: str) -> str:
         if not isinstance(bundle_name, str):
            raise DataValidationError("Store.exists() only accepts str values")

         with self.lock:
            with self.apistore as conn:
                cursor = self.get_cursor(conn).execute(
                    "SELECT EXISTS(SELECT 1 FROM bundles WHERE bundle_name = ?)", (bundle_name, )
                )
                exists = bool(cursor.fetchone()[0])
                return exists

    def _init_bundles_db(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        cursor = self.get_cursor(conn)
        cursor.execute('create table bundles(bundle_name TEXT, bundle TEXT)')

    def _assert_expected_api_store_config(self, conn: sqlite3.Connection) -> None:
        cols = []
        try:
            assert self.BUNDLE_PATH.name.lower() == 'bundles.db'
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

            "TEXT" == str(cursor.execute("SELECT typeof (bundle) FROM bundles"))
            "TEXT" == str(cursor.execute("SELECT typeof (bundle_name) FROM bundles"))

            return
        except Exception as e:
            if self.VERBOSE:
                print("bundles.db` exists but its configuration is invalid") 
            raise InvalidAPIStoreConfigurationError(
                "`bundles.db` exists but its configuration is invalid. \n" \
                "Expects a store with a `bundles` table containing `bundle_name` and `bundle` cols ONLY! \n" \
                "This error is used to avoid accidental data corruption \n" \
                f"e = {type(e).__name__} {str(e)}{f'. \n cols = {cols}.' if cols else '.'}" \
            )

if __name__ == "__main__":
    CORRUPT = False
    try:
        if CORRUPT:
            cur = sqlite3.connect(TIDEAPIStore.BUNDLE_PATH).cursor()
            cur.execute("ALTER TABLE bundles ADD extra TEXT")
    except:
        pass

    TIDEAPIStore()
