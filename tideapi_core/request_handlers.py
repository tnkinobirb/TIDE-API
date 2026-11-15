import uuid
import json
from pathlib import Path

from fastapi import Request, status
from fastapi.responses import RedirectResponse
from fastapi.concurrency import run_in_threadpool

from tide_tooling import TIDE
from tideapi_core.helpers.native import validate_tide_bundle
from tideapi_core.persistence.tideapi_store import TIDEAPIStore
from tideapi_core.locks import (
    BUNDLE_PATH,
    REGISTER_LOCK,
    STORE_INIT_LOCK,
)
from tideapi_core.app_context import (
    STORE,
    TRACES, 
)
from tideapi_core.helpers.native import (
    get_trace,
    list_traces,
    validate_bundle_name,
)
from tideapi_core.exceptions import (
    APILookupError,
    TraceLookupError,
    APIStoreLookupError,
    DataValidationError, 
)

def init_store() -> TIDEAPIStore:
    '''
    Initialise and retrieve the global TIDEAPIStore instance.
    If an instance is already present, retrieve the existing instance instead. 
    '''
    global STORE

    with STORE_INIT_LOCK:
        if STORE is None:
            STORE = TIDEAPIStore()
    return STORE

# Redirects
def redirect_to_docs() -> RedirectResponse:
    '''Used to redirect to /docs'''
    return RedirectResponse(url='/docs', status_code=status.HTTP_307_TEMPORARY_REDIRECT)

# REGISTER

def persist_bundle(bundle_name:str, replace:bool=False) -> dict[str, str]:
    '''Persist a bundle from the `TIDE-API/bundles` dir into TIDEAPIStore's sqlite3 `bundles.db`'''
    validate_bundle_name(bundle_name)
    path = BUNDLE_PATH / Path(bundle_name)
    if path.parent != BUNDLE_PATH:
        raise DataValidationError("bundle_name escaped root path!")

    if not path.exists():
        raise APILookupError(f"Cannot find path {bundle_name} in TIDE-API/bundles/")

    bundle = validate_tide_bundle(path)

    init_store().set(bundle_name, bundle, replace=replace)

    return {'result': bundle_name}

def load_trace(bundle_name: str) -> dict[str, str]:
    '''Load a live trace object via a persisted TIDE bundle from TIDEAPIStore's sqlite3 `bundles.db`'''
    if isinstance(bundle_name, str):
        validate_bundle_name(bundle_name)
        with REGISTER_LOCK:
            if not init_store().exists(bundle_name):
                persist_bundle(bundle_name)
            
            bundle = json.loads(init_store().get(bundle_name))

            if bundle_name in TRACES:
                return {"result": bundle_name}

            trace = TIDE.from_bundle(bundle)
            TRACES[bundle_name] = trace
            
            return {"result": bundle_name}
    else:
        raise DataValidationError('`bundle_name` must be a str identifier')
    
# SHOW
def local_bundles():
    valid = []
    for file in list(BUNDLE_PATH.iterdir()):
        try:
            if not file.is_file():
                continue
            name = file.name
            validate_bundle_name(name)
            
            if name in TRACES:
                # '*' signifies a bundle as already registered  
                name = '*' + name
            valid.append(name)
        except DataValidationError:
            continue
    return {'result': list(valid)} 

def persisted_bundles() -> dict[str, list[str]]:
    '''Return persisted `bundle_name`s from `bundles.db`'''
    bundles = init_store().bundles()
    return {"result": bundles}

def loaded_traces():
    '''Return which bundles are currently loaded as live Trace objects'''
    return {
        'result': list(list_traces(TRACES))
    }

def show_trace(bundle_name: str):
    '''Return a live Trace object as a serialisable dictionary'''
    trace = get_trace(TRACES, bundle_name)
    return {'result': trace.to_dict(serialise_events=True)}


# INSPECT / DEFAULT LOOKUP BEHAVIOUR
def inspect_ref(bundle_name: str, ref: str):
    '''Inspect a live Trace `reference` via `Trace.investigate()`'''
    trace = get_trace(TRACES, bundle_name)
    investigated = trace.investigate(ref, kind='reference')
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Reference {ref} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

def inspect_exec(bundle_name: str, ref: int):
    '''Inspect a live Trace `execution` via `Trace.investigate()`'''    
    trace = get_trace(TRACES, bundle_name)

    investigated = trace.investigate(ref, kind='seq_id')
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Exec {ref} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

def inspect_actor(bundle_name: str, ref: str):
    '''Inspect a live Trace `actor` via `Trace.investigate()`'''    
    trace = get_trace(TRACES, bundle_name)

    investigated = trace.investigate(ref, kind="actor")
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Actor {ref} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

# DEV




def initialise_traces_from_bundles(ignore_invalid:bool=False):
    '''
    Initialise live Trace objects from TIDEAPIStore sqlite3 `bundles.db`.
    If already initialised, skip instead. 
    If bundle_failed to register, log its validation error.
    '''    
    invalid = []
    registered= []
    for bundle_name in persisted_bundles()['result']:
        if bundle_name in TRACES:
            # `*` signifies a previously registered bundle
            registered.append("*" + bundle_name)
            continue
        try:
            load_trace(bundle_name)
            registered.append(bundle_name)
        except Exception as e:
            if not ignore_invalid:
                raise DataValidationError(
                    f"Trace init from {bundle_name} failed due to a {type(e).__name__}({str(e)}) \n" \
                    "Use `initialise_traces_from_bundles(ignore_invalid=True)` to log instead of raising") from e
            invalid.append(bundle_name)
            continue
        
    succeeded = list(registered)
    failed = list(invalid)
    return succeeded, failed

def get_init_meta(request: Request):
    '''Return Trace auto-initialisation results'''
    return {"result": getattr(
        request.app.state,
        "init",
        {}
    )}

# MIDDLEWARE
async def initialise_traces(request: Request, call_next):
    '''Middleware function for initialising traces on load'''
    if not hasattr(request.app.state, 'init'):
        request.app.state.init = {}
    
    if request.url.path == "/docs":
        registered, failed = await run_in_threadpool(initialise_traces_from_bundles, ignore_invalid=True) 

        request.app.state.init['traces'] = {
            "failed": failed,
            "registered": registered
        } 
    
    return await call_next(request)

MIDDLEWARE_HANDLERS = [
    {"type": "http", "function": initialise_traces}
]

TIDE_INSPECT_ENDPOINTS = [
    {"methods": ["GET"], "function": show_trace,                        "path": "/traces/{bundle_name}"},
    {"methods": ["GET"], "function": inspect_ref,                       "path": "/traces/{bundle_name}/ref"},
    {"methods": ["GET"], "function": inspect_exec,                      "path": "/traces/{bundle_name}/exec"},
    {"methods": ["GET"], "function": inspect_actor,                     "path": "/traces/{bundle_name}/actor"},
]

# FASTAPI ENDPOINT-HANDLERS DICTIONARY 
ENDPOINT_HANDLERS = [
    *TIDE_INSPECT_ENDPOINTS,

    {"methods": ["GET"], "function": get_init_meta,                     "path": "/meta/init"},
    {"methods": ["GET"], "function": redirect_to_docs,                  "path": "/"},
    {"methods": ["GET"], "function": local_bundles,                     "path": "/local/bundles"},
    {"methods": ["GET"], "function": loaded_traces,                     "path": "/traces"},
    {"methods": ["GET"], "function": persisted_bundles,                 "path": "/bundles"},

    {"methods": ["POST"],"function": load_trace,                        "path": "/register/trace/{bundle_name}"},
    {"methods": ["POST"],"function": persist_bundle,                    "path": "/register/bundle/{bundle_name}"},
    {"methods": ["POST"],"function": initialise_traces_from_bundles,    "path": "/dev/initialise_traces"},
    
]

