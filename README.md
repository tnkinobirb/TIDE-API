# TIDE-API

**An HTTP API for TIDE-Tooling.**

TIDE-API loads TIDE bundles and exposes their recorded execution evidence through FastAPI endpoints.

This is intended to be used only as a local service for listing, loading and investigating TIDE traces. If exposing the API to external networks, do so at your own risk.

## Install

```bash
git clone https://github.com/tnkinobirb/TIDE-API.git
cd TIDE-API

python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
. .venv/Scripts/activate

# Linux
. .venv/bin/activate
```

Then install and run:

```bash
python -m pip install .
fastapi run app.py
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## First use

Place a TIDE bundle in the default `bundles/` directory:

```text
TIDE-API/
└── bundles/
    └── example.json
```

Start TIDE-API:

```bash
fastapi run app.py
```

On startup, TIDE-API:

1. Creates or validates `bundles.db`.
2. Loads bundles already persisted in the database.
3. Discovers valid local bundles when local loading is enabled.
4. Persists discovered bundles as JSON strings.
5. Loads the bundles as TIDE traces.

Load a specific trace:

```bash
curl -X POST http://127.0.0.1:8000/register/trace/example.json
```

Retrieve its serialisable trace:

```bash
curl http://127.0.0.1:8000/traces/example.json
```

## Storage behaviour

TIDE-API stores bundle JSON in a configurable SQLite `bundles.db` database.

- Existing databases are validated before use.
- Bundle persistence rejects duplicated by default; replacement must be explicitly enabled.
- Loaded traces are held in memory for the lifetime of the process.
- Local bundle discovery is optional. When disabled, only persisted bundles are loaded.

## API

Query parameters without a shown default are required.

| Method | Path                             | Query                  | Behaviour                                                |
| ------ | -------------------------------- | ---------------------- | -------------------------------------------------------- |
| `GET`  | `/local/bundles`                 | —                      | List bundles available in the configured local directory |
| `GET`  | `/bundles`                       | —                      | List persisted bundles                                   |
| `GET`  | `/traces`                        | —                      | List loaded traces                                       |
| `GET`  | `/traces/{bundle_name}`          | —                      | Return a serialisable trace                              |
| `GET`  | `/traces/{bundle_name}/ref`      | `ref`                  | Investigate a reference                                  |
| `GET`  | `/traces/{bundle_name}/exec`     | `exec_seq_id`          | Investigate an execution                                 |
| `GET`  | `/traces/{bundle_name}/actor`    | `actor`                | Investigate an actor                                     |
| `POST` | `/register/bundle/{bundle_name}` | `replace=false`        | Validate and persist a local bundle                      |
| `POST` | `/register/trace/{bundle_name}`  | —                      | Load a bundle as a trace                                 |
| `POST` | `/initialise_traces`             | `ignore_invalid=false` | Load all available bundles                               |
| `GET`  | `/meta/init`                     | —                      | Return startup initialisation results                    |

See `/docs` for full request parameters, query types and response schemas.

## Configuration

Configuration is read from environment variables when the application starts.

Set environment variables via:

```bash
# Linux
export ENV_VAR=false

# Windows PowerShell
$Env:ENV_VAR='false'
```

| Variable | Default | Behaviour |
|---|---|---|
| `TIDEAPI_BUNDLE_DIR` | `TIDE-API/bundles` | Directory containing local bundle files |
| `TIDEAPI_DATABASE_PATH` | `TIDE-API/bundles.db` | Full path of the SQLite database |
| `TIDEAPI_INCLUDE_BUNDLE_DIR_WHEN_LOADING` | `true` | Include and persist local bundles while loading traces |

For example:

```bash
# Linux
export TIDEAPI_INCLUDE_BUNDLE_DIR_WHEN_LOADING=false

# Windows PowerShell
$Env:TIDEAPI_INCLUDE_BUNDLE_DIR_WHEN_LOADING='false'
```

## Tests

```bash
python -m pytest -q
```
