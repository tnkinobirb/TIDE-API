import uuid

from typing import TYPE_CHECKING
from fastapi import Request, status
from fastapi.responses import RedirectResponse
from threading import Lock
from pathlib import Path
from tide_tooling import TIDE
from fastapi.concurrency import run_in_threadpool
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
    DataValidationError
)

# Secrets + Pre-init
ROOT = Path(__file__).parents[1] / "bundles"
REGISTER_LOCK = Lock()

# Redirect
def redirect_to_docs():
    return RedirectResponse(url='docs/', status_code=status.HTTP_307_TEMPORARY_REDIRECT)

# REGISTER

def register_trace(bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        path = validate_bundle_name(ROOT, bundle_name)
        with REGISTER_LOCK:
            if bundle_name in REGISTERED_BUNDLES:
                return REGISTERED_BUNDLES[bundle_name]

            trace = TIDE.from_bundle(path)
            bundle_id = register_bundle_name(BUNDLES, bundle_name)
            trace_id = uuid.uuid4().hex
            
            TRACES[trace_id] = {
                "trace": trace,
                "bundle_name": bundle_name,
                "bundle_id": bundle_id,
            }

            REGISTERED_BUNDLES[bundle_name] = trace_id
            
            return trace_id
    else:
        raise DataValidationError('`bundle_name` must be a str identifier')
    


# SHOW

def available_bundles():
    bundles = []
    if ROOT.exists():
        for item in ROOT.iterdir():
            if item.is_file() and item.suffix.lower() == ".json":
                bundles.append(item.name)

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
    return {'result': trace.to_dict()}

# GET

def bundle_name_by_trace_id(trace_id: str):
    return {'result': str(get_bundle_name(TRACES, trace_id))}

# INSPECT / DEFAULT LOOKUP BEHAVIOUR

def inspect_ref(trace_id: str, ref: str):
    trace = get_trace(TRACES, trace_id)["trace"]

    inspected = trace.inspect_ref(ref).to_dict()
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
    {"methods": ["GET"], "function": show_trace,                        "path": "/show/traces/{trace_id}"},
    {"methods": ["GET"], "function": inspect_ref,                       "path": "/traces/{trace_id}/ref"},
    {"methods": ["GET"], "function": inspect_exec,                      "path": "/traces/{trace_id}/exec"},
    {"methods": ["GET"], "function": inspect_actor,                     "path": "/traces/{trace_id}/actor"},
]

ENDPOINT_HANDLERS = [
    *INSPECT_ENDPOINTS,
    
    {"methods": ["GET"], "function": redirect_to_docs,                  "path": "/"},
    {"methods": ["GET"], "function": available_traces,                  "path": "/show/traces"},
    {"methods": ["GET"], "function": available_bundles,                 "path": "/show/bundles"},
    {"methods": ["GET"], "function": bundle_name_by_trace_id,           "path": "/get/traces/{trace_id}/bundle_name"},

    {"methods": ["POST"],"function": register_trace,                    "path": "/register/trace/{bundle_name}"},
    {"methods": ["POST"],"function": initialise_traces_from_bundles,    "path": "/dev/initialise_traces"},
    
]

MIDDLEWARE_HANDLERS = [
    {"type": "http", "function": initialise_traces_on_docs_load}
]