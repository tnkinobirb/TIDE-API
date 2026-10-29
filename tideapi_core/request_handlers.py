import uuid

from typing import TYPE_CHECKING
from fastapi import Request

from pathlib import Path
from tide_tooling import TIDE
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
)

# Secrets + Pre-init
ROOT = Path(__file__).parents[1] / "bundles"

# REGISTER

def register_trace(bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        path = validate_bundle_name(ROOT, bundle_name)
        bundle_id = register_bundle_name(BUNDLES, bundle_name)
        trace = TIDE.from_bundle(path)
        trace_id = uuid.uuid4().hex

        TRACES[trace_id] = {
            "trace": trace,
            "bundle_name": bundle_name,
            "bundle_id": bundle_id,
        }

        REGISTERED_BUNDLES[bundle_name] = trace_id

    else:
        raise DataValidationError('`bundle_name` must be a str identifier')
    return trace_id


# SHOW

def available_bundles():
    bundles = []
    if ROOT.exists():
        for item in ROOT.iterdir():
            if item.is_file():
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
    return {'result': trace.show(colour=False)}

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
        initialise_traces_from_bundles() 

    return await call_next(request)



ENDPOINT_HANDLERS = [
    
    {"methods": ["GET"], "function": show_trace,                        "path": "/show/traces/{trace_id}"},
    {"methods": ["GET"], "function": inspect_ref,                       "path": "/traces/{trace_id}/ref"},
    {"methods": ["GET"], "function": available_traces,                  "path": "/show/traces"},
    {"methods": ["GET"], "function": available_bundles,                 "path": "/show/bundles"},
    {"methods": ["GET"], "function": bundle_name_by_trace_id,           "path": "/get/traces/{trace_id}/bundle_name"},
    
    {"methods": ["POST"],"function": register_trace,                    "path": "/register/trace/{bundle_name}"},
    {"methods": ["POST"],"function": initialise_traces_from_bundles,    "path": "/dev/initialise_traces"},
    
]

MIDDLEWARE_HANDLERS = [
    {"type": "http", "function": initialise_traces_on_docs_load}
]