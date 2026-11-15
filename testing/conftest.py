import pytest
from tideapi.persistence import TIDEAPIStore
from tideapi.handlers import ENDPOINT_HANDLERS 
from fastapi import Request
from fastapi.responses import JSONResponse
from tide_tooling import TIDE, Trace
from pathlib import Path
import sqlite3
import shutil

template_bundle_name = "example.json"

@pytest.fixture
def empty_bundle_dir(tmp_path):
    return tmp_path

@pytest.fixture
def empty_dict():
    return {}

@pytest.fixture
def sample_bundle_name():
    return template_bundle_name

@pytest.fixture
def sample_traces_dict():
    return {    
        'example.json': trace(),
    }

@pytest.fixture
def bundle_dir(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("bundle_dir")

    source = Path(__file__).parent / "bundles" / "example.json"
    if not source.exists():
        raise ValueError("Test bundle path could not be found!")
    if not source.is_file():
        raise TypeError("Test bundle was not a file!")
    
    destination = tmp_path / "bundles"

    if destination.exists():
        raise ValueError("Test bundle location already exists... needs an empty path")
    
    destination.mkdir()
    shutil.copy2(source, destination)
    files = list(destination.iterdir())
    assert(len(files)) == 1
    assert files[0].name == 'example.json'
    return destination


@pytest.fixture
def api_db(monkeypatch, tmp_path: Path) -> sqlite3.Connection:
    monkeypatch.setattr(TIDEAPIStore, 'DB_PATH', tmp_path / 'bundles.db')
    return TIDEAPIStore()

@pytest.fixture
def tide_bundle():
    bundles = Path(__file__).parent / 'bundles'
    assert bundles.exists()
    tide_bundle = bundles / 'example.json'
    assert tide_bundle.exists()
    return tide_bundle.read_text(encoding='utf-8')

@pytest.fixture
def sample_endpoints():
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


async def sample_middleware_func_0(request, call_next):
    response = await call_next(request) 
    response.headers['Test-Middleware_0'] = 'example_0'
    return response

async def sample_middleware_func_1(request, call_next):
    response = await call_next(request) 
    response.headers['Test-Middleware_1'] = 'example_1'
    return response

@pytest.fixture
def sample_middleware():
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

def handle_idx_exc(request: Request, exc: IndexError):
    return JSONResponse(
        status_code=404,
        content={
            "error": type(exc).__name__
        },
    )

def handle_val_exc(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
        }
    )

@pytest.fixture
def sample_exception_handlers():
    return {
        IndexError: handle_idx_exc,
        ValueError: handle_val_exc,
    }

@pytest.fixture
def endpoints() -> dict:
    return {endpoint['endpoint'].__name__: endpoint for endpoint in ENDPOINT_HANDLERS}

def trace():
    tide = TIDE()
    tide.event("A", writes={"AO": 'A'})
    tide.event("B", reads=["AO"], writes={"BO": 'B'})
    tide.event("C", reads=["BO"], writes={"CO": 'C'})
    return tide.trace()
    
@pytest.fixture
def tide_trace() -> Trace:
    return trace()

@pytest.fixture
def sample_trace() -> dict:
    return trace()

@pytest.fixture
def sample_actor():
    return "B"

@pytest.fixture
def sample_ref():
    return "BO"

@pytest.fixture
def sample_exec():
    return 2
