from tideapi.persistence import TIDEAPIStore
from tideapi_core.persistence import tideapi_store
from pathlib import Path
import sqlite3
import pytest

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
    monkeypatch.setattr(TIDEAPIStore, 'ROOT', tmp_path)
    monkeypatch.setattr(TIDEAPIStore, 'BUNDLE_PATH', tmp_path / 'bundles.db')
    TIDEAPIStore()
    assert any(next(file.name for file in list(tmp_path.iterdir()) if file.name == 'bundles.db'))

    conn = sqlite3.connect(tmp_path / 'bundles.db')
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

     

    
    