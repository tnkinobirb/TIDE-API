import uuid
import tideapi_core.request_handlers as request_handlers
import json
from typing import TYPE_CHECKING
from types import SimpleNamespace
from fastapi import Request, status
from fastapi.responses import RedirectResponse
from threading import RLock, Lock
from pathlib import Path
from tide_tooling import TIDE
from fastapi.concurrency import run_in_threadpool
from tideapi_core.persistence.tideapi_store import TIDEAPIStore
from tideapi_core.app_context import (
    TRACES, 
    BUNDLES, 
    REGISTERED_BUNDLES
)
from tideapi_core.helpers.native import (
    get_trace,
    list_traces,
    get_bundle_name,
    is_bundle_registered,
    register_bundle_name, 
    validate_bundle_name,
)
from tideapi_core.exceptions import (
    TraceLookupError,
    DataValidationError, 
    InternalExceptionError,
    APILookupError
)

# Secrets + Pre-init
STORE = None
STORE_LOCK = RLock()
REGISTER_LOCK = Lock()
BUNDLE_PATH = Path(__file__).parent / 'bundles'

def init_store() -> TIDEAPIStore:
    global STORE

    with STORE_LOCK:
        if STORE is None:
            STORE = TIDEAPIStore()
    return STORE

# Redirect
def redirect_to_docs():
    return RedirectResponse(url='docs/', status_code=status.HTTP_307_TEMPORARY_REDIRECT)

# Validate bundle

def validate_tide_bundle(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
        bundle = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataValidationError("Invalid TIDE bundle JSON") from exc

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise DataValidationError(message)

    require(isinstance(bundle, dict), "Bundle must be a JSON object")
    require(
        set(bundle) == {"manifest", "cas"},
        "Invalid bundle root structure"
    )

    manifest = bundle["manifest"]
    require(isinstance(manifest, dict), "Manifest must be an object")
    require(
        set(manifest) == {
            "kind", "codec_version", "content", "run",
            "values", "events", "metadata"
        },
        "Invalid manifest structure"
    )

    require(manifest["kind"] == "tide_bundle", "Invalid bundle kind")
    require(
        type(manifest["codec_version"]) is int
        and manifest["codec_version"] == 1,
        "Unsupported bundle codec version"
    )
    require(manifest["content"] == "trace", "Invalid bundle content")

    require(isinstance(manifest["values"], dict), "Invalid values")
    require(isinstance(manifest["metadata"], dict), "Invalid metadata")
    require(isinstance(bundle["cas"], dict), "Invalid CAS")

    run = manifest["run"]
    require(isinstance(run, dict), "Run must be an object")
    require(
        set(run) == {
            "kind", "codec_version", "trace",
            "records", "ready_attempts"
        },
        "Invalid run structure"
    )

    require(run["kind"] == "tide_run", "Invalid run kind")
    require(
        type(run["codec_version"]) is int
        and run["codec_version"] == 1,
        "Unsupported run codec version"
    )
    require(isinstance(run["trace"], dict), "Invalid trace")
    require(isinstance(run["records"], list), "Invalid records")
    require(isinstance(run["ready_attempts"], list), "Invalid ready attempts")

    return raw

# REGISTER

def register_bundle(bundle_name:str, replace:bool=False) -> None:

    validate_bundle_name(bundle_name)
    path = BUNDLE_PATH / Path(bundle_name)
    if path.parent != BUNDLE_PATH:
        raise DataValidationError("bundle_name escaped root path!")

    if not path.exists():
        raise APILookupError(f"Cannot find path {bundle_name} in TIDE-API/bundles/")

    bundle = validate_tide_bundle(path)

    init_store().set(bundle_name, bundle, replace=replace)

def register_trace(bundle_name: str) -> dict[str, str]:
    if isinstance(bundle_name, str):
        validate_bundle_name(bundle_name)
        bundle = json.loads(init_store().get(bundle_name))
        with REGISTER_LOCK:
            if bundle_name in REGISTERED_BUNDLES:
                return {"result": REGISTERED_BUNDLES[bundle_name]}

            trace = TIDE.from_bundle(bundle)
            bundle_id = register_bundle_name(BUNDLES, bundle_name)
            trace_id = uuid.uuid4().hex
            
            TRACES[trace_id] = {
                "trace": trace,
                "bundle_name": bundle_name,
                "bundle_id": bundle_id,
            }

            REGISTERED_BUNDLES[bundle_name] = trace_id
            
            return {"result": trace_id}
    else:
        raise DataValidationError('`bundle_name` must be a str identifier')
    
# SHOW
def available_bundles() -> dict[str, list[str]]:
    bundles = init_store().bundles()
    return {"result": bundles}

def available_traces():
    return {
        'result': {
            trace_id: get_bundle_name(TRACES, trace_id)
            for trace_id in list_traces(TRACES)
        }
    }

def show_trace(trace_id: str):
    trace = get_trace(TRACES, trace_id)["trace"]
    return {'result': trace.to_dict(serialise_events=True)}

# GET

def bundle_name_by_trace_id(trace_id: str):
    return {'result': str(get_bundle_name(TRACES, trace_id))}

# INSPECT / DEFAULT LOOKUP BEHAVIOUR

def inspect_ref(trace_id: str, ref: str):
    trace = get_trace(TRACES, trace_id)["trace"]

    inspected = trace.inspect(value=ref, kind='reference')
    inspected = inspected.to_dict()
    if inspected["exists"] is False:
        raise TraceLookupError(f'Reference {ref} was not found in trace {trace_id}')
    
    return {"result": inspected}

def inspect_exec(trace_id: str, ref: int):
    trace = get_trace(TRACES, trace_id)["trace"]

    inspected = trace.inspect(ref, kind='seq_id').to_dict()
    if inspected["exists"] is False:
        raise TraceLookupError(f'Exec {ref} was not found in trace {trace_id}')
    
    return {"result": inspected}

def inspect_actor(trace_id: str, ref: str):
    trace = get_trace(TRACES, trace_id)["trace"]

    inspected = trace.inspect(ref, kind="actor").to_dict()
    if inspected["exists"] is False:
        raise TraceLookupError(f'Actor {ref} was not found in trace {trace_id}')
    
    return {"result": inspected}


# DEV

def initialise_traces_from_bundles():
    for bundle_name in available_bundles()['result']:
        if is_bundle_registered(REGISTERED_BUNDLES, bundle_name):
            continue
        register_trace(bundle_name)
    return list_traces(TRACES)

# MIDDLEWARE

async def initialise_traces_on_docs_load(request: Request, call_next):
    
    if request.url.path == "/docs":
        await run_in_threadpool(initialise_traces_from_bundles) 

    return await call_next(request)



INSPECT_ENDPOINTS = [
    {"methods": ["GET"], "function": show_trace,                        "path": "/traces/{trace_id}"},
    {"methods": ["GET"], "function": inspect_ref,                       "path": "/traces/{trace_id}/ref"},
    {"methods": ["GET"], "function": inspect_exec,                      "path": "/traces/{trace_id}/exec"},
    {"methods": ["GET"], "function": inspect_actor,                     "path": "/traces/{trace_id}/actor"},
]

ENDPOINT_HANDLERS = [
    *INSPECT_ENDPOINTS,
    
    
    {"methods": ["GET"], "function": redirect_to_docs,                  "path": "/"},
    {"methods": ["GET"], "function": available_traces,                  "path": "/traces"},
    {"methods": ["GET"], "function": available_bundles,                 "path": "/bundles"},
    {"methods": ["GET"], "function": bundle_name_by_trace_id,           "path": "/traces/{trace_id}/bundle_name"},

    {"methods": ["POST"],"function": register_trace,                    "path": "/register/trace/{bundle_name}"},
    {"methods": ["POST"],"function": register_bundle,                   "path": "/register/bundle/{bundle_name}"},
    {"methods": ["POST"],"function": initialise_traces_from_bundles,    "path": "/dev/initialise_traces"},
    
]

MIDDLEWARE_HANDLERS = [
    {"type": "http", "function": initialise_traces_on_docs_load}
]
