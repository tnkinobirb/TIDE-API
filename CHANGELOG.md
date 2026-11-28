# Changelog

## v0.0.4 (pre-alpha)

Persistence:
- Initial containerised PostgreSQL support through `TIDEPSQLStore`, with connection pooling and integration tests.
- Added `TIDEAPI_STORE_BACKEND` to select the persistence backend. `sqlite3` is the default. `postgresql` is available.

Configuration:
- Added `tideapi.env.template` for TIDE-API environment settings.

## v0.0.3 (pre-alpha)

Repo-Structure:
- Moved `bundles.db` into the new `data/` directory.

Docker:
- Added initial Docker and Docker Compose support.

## v0.0.2 (pre-alpha)

Testing:
- Strengthened concurrency test assertions.
- Fixed bundle verification timeout error.
