import os
import pytest
from uuid import uuid4
from psycopg.errors import UniqueViolation
from tideapi_core.persistence.tideapi_store import TIDEPSQLStore
from tideapi.exceptions import (
    APIStoreLookupError,
    DataValidationError,
    AlreadyRegisteredError,
)

# Only run when TIDEAPI_TEST_PSQL testing env is enabled.
pytestmark = pytest.mark.skipif(
    os.getenv("TIDEAPI_TEST_PSQL") != "1",
    reason=(
        "PostgreSQL integration tests not enabled.\n"
        "Ensure PostgreSQL is running: `docker compose up -d postgres`\n"
        "Then enable testing using:\n"
        "Unix: `export TIDEAPI_TEST_PSQL='1'`\n"
        "PowerShell: `$env:TIDEAPI_TEST_PSQL='1'`"
    )
)

# TEST FIXTURES
@pytest.fixture
def db():
    store = TIDEPSQLStore()

    try:
        yield store
    finally:
        store.close()

@pytest.fixture
def bundle_case(db):
    name = f"pytest_{uuid4().hex}.json"

    with db.apistore as conn:
        existing = {
            row[0] for row in conn.execute(
                "SELECT bundle_name FROM tide.bundles"
            ).fetchall()
        }

    assert name not in existing

    try:
        yield name, existing
    finally:
        with db.apistore as conn:
            conn.execute(
                "DELETE FROM tide.bundles WHERE bundle_name = %s",
                (name,)
            )

class TestStoreInit:

    def test_APIStore_init_uses_valid_store(self, db):
        with db.apistore as conn:
            cursor = conn.execute("SELECT * FROM tide.bundles LIMIT 0")

            cols = [col[0] for col in cursor.description]
            assert cols == ["bundle_name", "bundle"]

    def test_APIStore_init_preserves_existing_store(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case
        db.set(name, tide_bundle)
        second_db = TIDEPSQLStore()

        try:
            assert second_db.get(name) == tide_bundle
            assert set(second_db.bundles()) == existing | {name}
        finally:
            second_db.close()

class TestClassOperations:

    def test_store_set(self, db, bundle_case, tide_bundle, modified_tide_bundle):
        name, existing = bundle_case
        assert set(db.bundles()) == existing
        
        db.set(name, tide_bundle)
        assert set(db.bundles()) == existing | {name}
        assert db.get(name) == tide_bundle

        # Invalid inputs
        with pytest.raises(DataValidationError):
            db.set(1, lambda: None)

        assert db.get(name) == tide_bundle

        # Duplicate registration: identical
        with pytest.raises(AlreadyRegisteredError):
            db.set(name, tide_bundle)

        assert db.get(name) == tide_bundle

        # Duplicate registration: different
        with pytest.raises(AlreadyRegisteredError):
            db.set(name, modified_tide_bundle)

        assert db.get(name) == tide_bundle

        # Test database primary key enforcement
        with pytest.raises(UniqueViolation):
            with db.apistore as conn:
                conn.execute(
                    "INSERT INTO tide.bundles "
                    "(bundle_name, bundle) VALUES (%s, %s)",
                    (name, modified_tide_bundle)
                )

        assert set(db.bundles()) == existing | {name}
        assert db.get(name) == tide_bundle

        # Invalid replace leaves existing data unaffected
        with pytest.raises(DataValidationError):
            db.set(name, "1234", replace=True)

        assert db.get(name) == tide_bundle
        assert set(db.bundles()) == existing | {name}

        # Replace existing registration
        db.set(name, modified_tide_bundle, replace=True)

        assert set(db.bundles()) == existing | {name}
        assert db.get(name) == modified_tide_bundle

    def test_store_set_replace_missing(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case
        assert not db.exists(name)

        db.set(name, tide_bundle, replace=True)
        assert db.get(name) == tide_bundle
        assert set(db.bundles()) == existing | {name}

    def test_store_get(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case

        assert set(db.bundles()) == existing

        with pytest.raises(APIStoreLookupError):
            db.get(name)

        db.set(name, tide_bundle)

        assert set(db.bundles()) == existing | {name}
        assert db.get(name) == tide_bundle

        with pytest.raises(DataValidationError):
            db.get(lambda: None)

    def test_store_pop(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case

        assert set(db.bundles()) == existing
        db.set(name, tide_bundle)

        assert set(db.bundles()) == existing | {name}
        assert db.pop(name) == tide_bundle
        assert set(db.bundles()) == existing

        with pytest.raises(APIStoreLookupError):
            db.pop(name)

        with pytest.raises(DataValidationError):
            db.pop(lambda: None)

    def test_store_exists(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case

        assert not db.exists(name)
        db.set(name, tide_bundle)

        assert db.exists(name)
        assert set(db.bundles()) == existing | {name}

        with pytest.raises(DataValidationError):
            db.exists(lambda: None)

        db.pop(name)
        assert not db.exists(name)

    def test_bundles_listing(self, db, bundle_case, tide_bundle):
        name, existing = bundle_case
        assert set(db.bundles()) == existing

        db.set(name, tide_bundle)
        assert set(db.bundles()) == existing | {name}

        db.pop(name)
        assert set(db.bundles()) == existing