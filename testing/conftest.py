import json
import pytest
from typing import Any
from collections.abc import Awaitable, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from tideapi.persistence import TIDEAPIStore
from tideapi.handlers import ENDPOINT_HANDLERS
from tideapi_core import request_handlers
from tide_tooling import TIDE, Trace
from pathlib import Path

# TEMPLATE FUNCTIONS FOR FIXTURES
async def sample_middleware_func_0(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers['Test-Middleware_0'] = 'example_0'
    return response

async def sample_middleware_func_1(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers['Test-Middleware_1'] = 'example_1'
    return response

def handle_idx_exc(request: Request, exc: IndexError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": type(exc).__name__
        },
    )

def handle_val_exc(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
        }
    )

# STORAGE | DIRECTORY FIXTURES
@pytest.fixture(autouse=True)
def default_test_store_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    '''Keep existing API tests isolated from the configured PostgreSQL backend.'''
    monkeypatch.setattr(request_handlers, 'STORE_BACKEND', 'sqlite3')

@pytest.fixture
def api_db(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> TIDEAPIStore:
    monkeypatch.setattr(TIDEAPIStore, 'DB_PATH', tmp_path_factory.mktemp('tmp') / 'bundles.db')
    return TIDEAPIStore()

@pytest.fixture
def bundle_dir(tmp_path_factory: pytest.TempPathFactory, tide_bundle: str) -> Path:
    tmp_path = tmp_path_factory.mktemp('tmp')
    (tmp_path / 'example.json').write_text(tide_bundle, encoding='utf-8')
    files = list(tmp_path.iterdir())
    assert(len(files)) == 1
    assert files[0].name == 'example.json'
    return tmp_path

# TIDE OBJECT FIXTURES
def trace() -> Trace:
    tide = TIDE()
    tide.event("A", writes={"AO": 'A'})
    tide.event("B", reads=["AO"], writes={"BO": 'B'})
    tide.event("C", reads=["BO"], writes={"CO": 'C'})
    return tide.trace()

@pytest.fixture(scope='session')
def tide_bundle() -> str:
    bundles = Path(__file__).parent / 'bundles'
    assert bundles.exists()
    tide_bundle = bundles / 'example.json'
    assert tide_bundle.exists()
    return tide_bundle.read_text(encoding='utf-8')

@pytest.fixture(scope='session')
def modified_tide_bundle(tide_bundle: str) -> str:
    modified = json.loads(tide_bundle)
    modified['manifest']['run']['trace']['name'] = 'new'
    serialised_bundle = json.dumps(modified)
    assert modified != json.loads(tide_bundle)
    assert serialised_bundle != tide_bundle
    return serialised_bundle

@pytest.fixture
def sample_trace() -> Trace:
    return trace()

@pytest.fixture
def sample_actor() -> str:
    return "B"

@pytest.fixture
def sample_ref() -> str:
    return "BO"

@pytest.fixture
def sample_exec() -> int:
    return 2

@pytest.fixture
def sample_bundle_name() -> str:
    return "example.json"

@pytest.fixture
def endpoints() -> dict[str, dict[str, Any]]:
    return {endpoint['endpoint'].__name__: endpoint for endpoint in ENDPOINT_HANDLERS}

@pytest.fixture
def sample_traces_dict(sample_bundle_name: str, sample_trace: Trace) -> dict[str, Trace]:
    return {
        sample_bundle_name: sample_trace,
    }

@pytest.fixture
def sample_exception_handlers() -> dict[type[Exception], Callable[..., JSONResponse]]:
    return {
        IndexError: handle_idx_exc,
        ValueError: handle_val_exc,
    }

@pytest.fixture
def sample_middleware() -> list[dict[str, Any]]:
    return [
        {
        'middleware_type': 'http',
        'func': sample_middleware_func_0
        },
        {
        'middleware_type': 'http',
        'func': sample_middleware_func_1
        },
    ]

@pytest.fixture
def sample_endpoints() -> list[dict[str, Any]]:
    return [
        {
            'path':'/example',
            'endpoint':lambda:{'result': 'example'},
            'methods':{'GET', }
        },
        {
            'path':'/hello',
            'endpoint':lambda: {'result': 'example'},
            'methods':{'GET', }
        }
    ]

