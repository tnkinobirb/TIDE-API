import pytest, uuid
from tideapi.persistence import TIDEAPIStore
from tideapi.handlers import ENDPOINT_HANDLERS 
from fastapi import Request
from fastapi.responses import JSONResponse
from tide_tooling import TIDE, Trace
from pathlib import Path
import sqlite3
import json
template_bundle_name = "example.json"
template_bundle_uuid4 = uuid.uuid4().hex
template_trace_uuid4 = uuid.uuid4().hex


@pytest.fixture
def sample_bundle_uuid():
    return template_bundle_uuid4

@pytest.fixture
def sample_bundle_name():
    return template_bundle_name

@pytest.fixture
def sample_trace_uuid():
    return template_trace_uuid4

@pytest.fixture
def empty_bundle_dir(tmp_path):
    return tmp_path

@pytest.fixture
def empty_dict():
    return {}

@pytest.fixture
def bundle_dir(tmp_path):
    (tmp_path / template_bundle_name).write_text("{}")
    return tmp_path

@pytest.fixture
def sample_bundles_dict():  
    return {template_bundle_uuid4: template_bundle_name}

@pytest.fixture
def sample_registered_bundles_dict():
    return {template_bundle_name: template_trace_uuid4}

@pytest.fixture
def sample_traces_dict():
    return {    
        template_trace_uuid4: {
            "trace": object(),
            "bundle_name": template_bundle_name,
            "bundle_id": template_bundle_uuid4,
        }
    }

@pytest.fixture
def api_db(monkeypatch, tmp_path: Path) -> sqlite3.Connection:
    db_path =  (tmp_path / 'bundles.db')
    monkeypatch.setattr(TIDEAPIStore, 'ROOT', tmp_path)
    monkeypatch.setattr(TIDEAPIStore, 'BUNDLE_PATH', db_path)
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
        'function':lambda:{'result': 'example'},
        'methods':{'GET', }
       },
       {
        'path':'/hello',
        'function':lambda: {'result': 'example'},
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
        'type': 'http',
        'function':  sample_middleware_func_0
        },
        {
        'type': 'http',
        'function':  sample_middleware_func_1
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
    return {endpoint['function'].__name__: endpoint for endpoint in ENDPOINT_HANDLERS}

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
    return {
        "trace":trace(),
        "bundle_id":template_bundle_uuid4,
        "bundle_name":template_bundle_name    
    }

@pytest.fixture
def sample_actor():
    return "B"

@pytest.fixture
def sample_ref():
    return "BO"

@pytest.fixture
def sample_exec():
    return 2
