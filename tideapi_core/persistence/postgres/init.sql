-- DB Password
\getenv tideapi_psql_password TIDEAPI_PSQL_DB_PASSWORD

-- Create bundles table
CREATE SCHEMA IF NOT EXISTS tide;

CREATE TABLE IF NOT EXISTS tide.bundles (
    bundle_name TEXT PRIMARY KEY,
    bundle TEXT NOT NULL
);

-- TIDE-API Role
SELECT NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'tideapi'
) AS role_missing
\gset

\if :role_missing
    CREATE ROLE tideapi
        LOGIN
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        PASSWORD :'tideapi_psql_password';
\endif

ALTER ROLE tideapi SET search_path TO tide;

GRANT USAGE ON SCHEMA tide TO tideapi;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE tide.bundles TO tideapi;