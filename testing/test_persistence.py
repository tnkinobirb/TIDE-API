from tideapi.persistence import TIDEAPIStore
from tideapi.exceptions import InvalidAPIStoreConfigurationError, DataValidationError, APIStoreLookupError
from pathlib import Path
import sqlite3
import pytest
from pytest import TempPathFactory

def init_test_apistore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(TIDEAPIStore, 'ROOT', tmp_path)
    monkeypatch.setattr(TIDEAPIStore, 'VERBOSE', False)
    apistore = TIDEAPIStore()
    conn = sqlite3.connect(tmp_path / 'bundles.db')
    return conn, apistore

def sanitise_name(string:str) -> str:
    return '"' + string.replace('"', '""') + '"'

def extract_cols(cursor):
    return [col[0] for col in cursor.description]

def assert_table_cols(cursor:sqlite3.Cursor, table_name:str, expected_cols:list[str,]):
    cursor.execute(f'SELECT * FROM {sanitise_name(table_name)}')
    columns = extract_cols(cursor)
    assert len(columns) == len(expected_cols)
    assert columns == expected_cols
    
def test_create_bundle_store_on_APIStore_init(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    assert not any(list(tmp_path.iterdir()))                                                                             
    conn, _ = init_test_apistore(monkeypatch, tmp_path)
    assert any(next(file.name for file in list(tmp_path.iterdir()) if file.name == 'bundles.db'))
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

def test_APIStore_init_uses_preexisting_valid_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    assert not any(list(tmp_path.iterdir()))                                                                             
    conn, _ = init_test_apistore(monkeypatch, tmp_path)
    assert any(next(file.name for file in list(tmp_path.iterdir()) if file.name == 'bundles.db'))
    cursor = conn.cursor()
    
    assert_table_cols(
        cursor, 
        table_name='bundles', 
        expected_cols=['bundle_name', 'bundle']
    )

    empty = not list(conn.execute("SELECT * FROM bundles"))
    assert empty is True

    cursor.execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
    conn.commit()
    before = list(conn.execute("SELECT * FROM bundles"))

    conn, _ = init_test_apistore(monkeypatch, tmp_path)

    assert_table_cols(
        cursor, 
        table_name='bundles', 
        expected_cols=['bundle_name', 'bundle']
    )

    after = list(conn.execute("SELECT * FROM bundles"))
    assert before == after

    conn.close()
    
    

def test_APIStore_init_denies_preexisting_invalid_store(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: TempPathFactory):
    # Empty database
    empty_path = tmp_path_factory.mktemp("empty_path")

    assert not any(list(empty_path.iterdir()))        
    conn = sqlite3.connect(empty_path / 'bundles.db')

    with pytest.raises(InvalidAPIStoreConfigurationError):
        init_test_apistore(monkeypatch, empty_path)
    conn.close()

    # Invalid config
    tmp_path = tmp_path_factory.mktemp("tmp_path")

    conn, _ = init_test_apistore(monkeypatch, tmp_path)
    assert any(next(file.name for file in list(tmp_path.iterdir()) if file.name == 'bundles.db'))

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
    
    with pytest.raises(AssertionError):
        assert_table_cols(
            cursor, 
            table_name='bundles', 
            expected_cols=['bundle_name', 'bundle']
        )

    with pytest.raises(InvalidAPIStoreConfigurationError):
        init_test_apistore(monkeypatch, tmp_path)

    conn.close()

def test_store_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    conn, apistore = init_test_apistore(monkeypatch, tmp_path)
    
    empty = not list(conn.execute("SELECT * FROM bundles"))
    assert empty 

    apistore.set("example.json", "1234")
    rows = list(conn.execute("SELECT * FROM bundles"))
    assert rows 
    assert rows[0] == ("example.json", "1234")

    # invalid inputs
    with pytest.raises(DataValidationError):
        apistore.set(1, lambda: None)

    conn.close()

# @pytest.mark.skip()
def test_store_get(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    conn, apistore = init_test_apistore(monkeypatch, tmp_path)

    empty = not list(conn.execute("SELECT * FROM bundles"))
    assert empty 

    # Init store    
    conn.cursor().execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
    conn.commit()

    rows = list(conn.execute("SELECT * FROM bundles"))
    assert rows 
    assert rows[0] == ("example.json", "1234")

    # Test
    assert apistore.get("example.json") == "1234"

    # Non-existent target
    with pytest.raises(APIStoreLookupError):
        apistore.get("nonexistent")

    # Invalid data
    with pytest.raises(DataValidationError):
        apistore.get(lambda: None)

    conn.close()

# @pytest.mark.skip()
def test_store_pop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    conn, apistore = init_test_apistore(monkeypatch, tmp_path)

    empty = not list(conn.execute("SELECT * FROM bundles"))
    assert empty 

    # Init store    
    conn.cursor().execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
    conn.commit()
    
    rows = list(conn.execute("SELECT * FROM bundles"))
    assert rows 
    assert len(rows) == 1
    assert rows[0] == ("example.json", "1234")
    
    # Test
    assert apistore.pop("example.json") == "1234"
    conn.commit()
    
    after_rows = list(conn.execute("SELECT * FROM bundles"))
    assert not after_rows 

    # Non-existent target
    with pytest.raises(APIStoreLookupError):
        apistore.pop("nonexistent")

    # Invalid data
    with pytest.raises(DataValidationError):
        apistore.pop(lambda: None)
    
    conn.close()

# @pytest.mark.skip()
def test_store_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    conn, apistore = init_test_apistore(monkeypatch, tmp_path)

    empty = not list(conn.execute("SELECT * FROM bundles"))
    assert empty 

    # Init store    
    conn.cursor().execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
    conn.commit()
    
    rows = list(conn.execute("SELECT * FROM bundles"))
    assert rows 
    assert len(rows) == 1
    assert rows[0] == ("example.json", "1234")
    
    assert apistore.exists("example.json") 
    
    # Non-existent target
    assert apistore.exists("nonexistent") is False

    # Invalid data
    with pytest.raises(DataValidationError):
        apistore.exists(lambda: None)
    
    conn.close()

def test_list_bundles(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: TempPathFactory):
    bundle_path = tmp_path_factory.mktemp('bundles')
    conn, apistore = init_test_apistore(monkeypatch, bundle_path)
   
    # Init store    
    conn.cursor().execute("INSERT INTO bundles (bundle_name, bundle) VALUES ('example.json', '1234')")
    conn.commit()

    assert list(apistore.bundles()) == ['example.json']
    conn.close()

    empty_path = tmp_path_factory.mktemp('empty')
    e_conn, e_apistore = init_test_apistore(monkeypatch, empty_path)
    assert e_apistore.bundles() == []
    e_conn.close()
