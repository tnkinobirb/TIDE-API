import pytest
import sqlite3
from pathlib import Path
from pytest import TempPathFactory
from tideapi.persistence import TIDEAPIStore
from tideapi.exceptions import (
    APIStoreLookupError,
    DataValidationError,
    AlreadyRegisteredError,
    InvalidAPIStoreConfigurationError,
)

# TEST HELPERS
def init_test_apistore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TIDEAPIStore:
    monkeypatch.setattr(TIDEAPIStore, 'DB_PATH', tmp_path / 'bundles.db')
    db = TIDEAPIStore()
    return db

def sanitise_name(string:str) -> str:
    return '"' + string.replace('"', '""') + '"'

def extract_cols(cursor: sqlite3.Cursor) -> list[str]:
    return [col[0] for col in cursor.description]

def assert_table_cols(cursor:sqlite3.Cursor, table_name:str, expected_cols:list[str]) -> None:
    cursor.execute(f'SELECT * FROM {sanitise_name(table_name)}')
    columns = extract_cols(cursor)
    assert len(columns) == len(expected_cols)
    assert columns == expected_cols

class TestStoreInit:

    def test_create_bundle_store_on_APIStore_init(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        assert not any(list(tmp_path.iterdir()))
        db = init_test_apistore(monkeypatch, tmp_path)
        assert (tmp_path / 'bundles.db').is_file()
        with db.apistore as conn:
            cursor = conn.cursor()

            tables = list(cursor.execute(
                "SELECT name FROM sqlite_schema " \
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))

            assert len(tables) == 1
            assert tables[0][0] == "bundles"

            assert_table_cols(
                cursor,
                table_name='bundles',
                expected_cols=['bundle_name', 'bundle']
            )

    def test_APIStore_init_uses_preexisting_valid_store(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        assert not any(list(tmp_path.iterdir()))
        db = init_test_apistore(monkeypatch, tmp_path)
        assert (tmp_path / 'bundles.db').is_file()
        with db.apistore as conn:
            cursor = conn.cursor()

            assert_table_cols(
                cursor,
                table_name='bundles',
                expected_cols=['bundle_name', 'bundle']
            )

            empty = not list(conn.execute("SELECT * FROM bundles"))
            assert empty is True

            cursor.execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
            before = list(conn.execute("SELECT * FROM bundles"))

        db = init_test_apistore(monkeypatch, tmp_path)

        with db.apistore as conn:
            cursor = conn.cursor()
            assert_table_cols(
                cursor,
                table_name='bundles',
                expected_cols=['bundle_name', 'bundle']
            )

            after = list(conn.execute("SELECT * FROM bundles"))
            assert before == after


    def test_APIStore_init_denies_preexisting_invalid_store(self, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: TempPathFactory) -> None:
        # Test empty database
        empty_path = tmp_path_factory.mktemp("empty_path")

        assert not any(list(empty_path.iterdir()))
        sqlite3.connect(empty_path / 'bundles.db').close()

        with pytest.raises(InvalidAPIStoreConfigurationError):
            init_test_apistore(monkeypatch, empty_path)

        # Test invalid config
        tmp_path = tmp_path_factory.mktemp("tmp_path")

        db = init_test_apistore(monkeypatch, tmp_path)
        assert (tmp_path / 'bundles.db').is_file()
        with db.apistore as conn:
            cursor = conn.cursor()

            assert_table_cols(
                cursor,
                table_name='bundles',
                expected_cols=['bundle_name', 'bundle']
            )

            empty = not list(conn.execute("SELECT * FROM bundles"))
            assert empty is True

            conn.execute('ALTER TABLE bundles ADD invalid TEXT')

            assert_table_cols(
                cursor,
                table_name='bundles',
                expected_cols=['bundle_name', 'bundle', 'invalid']
            )

        with pytest.raises(InvalidAPIStoreConfigurationError):
            init_test_apistore(monkeypatch, tmp_path)

class TestClassOperations:

    def test_store_set(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tide_bundle: str, modified_tide_bundle: str) -> None:
        db = init_test_apistore(monkeypatch, tmp_path)

        assert not db.bundles()

        db.set("example.json", tide_bundle)
        assert db.bundles() == ["example.json"]
        assert db.get("example.json") == tide_bundle

        # invalid inputs
        with pytest.raises(DataValidationError):
            db.set(1, lambda: None)

        # test get still works correctly after failure
        assert db.get("example.json") == tide_bundle

        # duplicate registration
        with pytest.raises(AlreadyRegisteredError):
            db.set("example.json", tide_bundle)
        assert db.get("example.json") == tide_bundle

        with pytest.raises(AlreadyRegisteredError):
            db.set("example.json", modified_tide_bundle)
        assert db.get("example.json") == tide_bundle

        # The database also rejects duplicate keys without store validation.
        with pytest.raises(sqlite3.IntegrityError):
            with db.apistore as conn:
                conn.execute(
                    "INSERT INTO bundles (bundle_name, bundle) VALUES (?, ?)",
                    ("example.json", modified_tide_bundle)
                )

        assert db.bundles() == ["example.json"]
        assert db.get("example.json") == tide_bundle

        # Invalid replacement must preserve the original registration.
        with pytest.raises(DataValidationError):
            db.set("example.json", "1234", replace=True)
        assert db.get("example.json") == tide_bundle
        assert db.bundles() == ["example.json"]

        # replace existing registration
        db.set("example.json", modified_tide_bundle, replace=True)
        assert db.bundles() == ["example.json"]
        assert db.get("example.json") == modified_tide_bundle

    def test_store_get(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tide_bundle: str) -> None:
        db = init_test_apistore(monkeypatch, tmp_path)

        assert not db.bundles()

        # Init store
        db.set("example.json", tide_bundle)

        assert db.bundles() == ["example.json"]

        # Test get
        assert db.get("example.json") == tide_bundle

        # Non-existent target
        with pytest.raises(APIStoreLookupError):
            db.get("nonexistent")

        # Invalid data
        with pytest.raises(DataValidationError):
            db.get(lambda: None)

    def test_store_pop(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tide_bundle: str) -> None:
        db = init_test_apistore(monkeypatch, tmp_path)

        assert not db.bundles()

        # Init store
        db.set("example.json", tide_bundle)

        assert db.bundles() == ["example.json"]

        # Test
        assert db.pop("example.json") == tide_bundle

        assert not db.bundles()

        # Non-existent target
        with pytest.raises(APIStoreLookupError):
            db.pop("nonexistent")

        # Invalid data
        with pytest.raises(DataValidationError):
            db.pop(lambda: None)

    def test_store_exists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tide_bundle: str) -> None:
        db = init_test_apistore(monkeypatch, tmp_path)

        assert not db.bundles()

        # Init store
        db.set("example.json", tide_bundle)

        assert db.bundles() == ["example.json"]

        assert db.exists("example.json")

        # Non-existent target
        assert db.exists("nonexistent") is False

        # Invalid data
        with pytest.raises(DataValidationError):
            db.exists(lambda: None)

    def test_bundles_listing(self, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: TempPathFactory, tide_bundle: str) -> None:
        bundle_path = tmp_path_factory.mktemp('bundles')
        db = init_test_apistore(monkeypatch, bundle_path)

        # Init store
        db.set("example.json", tide_bundle)

        assert list(db.bundles()) == ['example.json']

        empty_path = tmp_path_factory.mktemp('empty')
        empty_db = init_test_apistore(monkeypatch, empty_path)
        assert empty_db.bundles() == []
