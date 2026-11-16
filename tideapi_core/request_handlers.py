'''
    FASTAPI ENDPOINT AND MIDDLEWARE HANDLERS
'''

import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.concurrency import run_in_threadpool

from tide_tooling import TIDE
from tideapi_core.config import BUNDLE_DIR
from tideapi_core.helpers.native import validate_tide_bundle
from tideapi_core.persistence.tideapi_store import TIDEAPIStore
from tideapi_core.locks import (
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
    DataValidationError, 
)

# STORE INITIALISER
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

# REDIRECTS
def redirect_to_docs() -> RedirectResponse:
    '''Used to redirect to /docs'''
    return RedirectResponse(url='/docs', status_code=status.HTTP_307_TEMPORARY_REDIRECT)

# REGISTER
def persist_bundle(bundle_name:str, replace:bool=False) -> dict[str, str]:
    '''Persist a bundle from the `TIDE-API/bundles` dir into TIDEAPIStore's sqlite3 `bundles.db`'''
    validate_bundle_name(bundle_name)
    path = BUNDLE_DIR / Path(bundle_name)
    if path.parent != BUNDLE_DIR:
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
    
# SHOW | LIST 
def local_bundles() -> dict[str, list[str]]:
    '''List local bundle .json files available within TIDE-API/bundles'''
    valid = []
    for file in list(BUNDLE_DIR.iterdir()):
        try:
            if not file.is_file():
                continue
            name = file.name
            validate_bundle_name(name)
            
            if name in TRACES:
                # '*' signifies that the bundle has a loaded trace
                name = '*' + name
            valid.append(name)
        except DataValidationError:
            continue
    return {'result': list(valid)} 

def persisted_bundles() -> dict[str, list[str]]:
    '''Return persisted `bundle_name`s from `bundles.db`'''
    bundles = init_store().bundles()
    return {"result": bundles}

def loaded_traces() -> dict[str, list[str]]:
    '''Return which bundles are currently loaded as live Trace objects'''
    return {
        'result': list(list_traces(TRACES))
    }

# INVESTIGATE / DEFAULT LOOKUP BEHAVIOUR
def investigate_ref(bundle_name: str, ref: str) -> dict[str, Any]:
    '''Investigate a live Trace `reference` via `Trace.investigate()`'''
    trace = get_trace(TRACES, bundle_name)
    investigated = trace.investigate(ref, kind='reference')
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Reference {ref} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

def investigate_exec(bundle_name: str, exec_seq_id: int) -> dict[str, Any]:
    '''Investigate a live Trace `execution` via `Trace.investigate()`'''    
    trace = get_trace(TRACES, bundle_name)

    investigated = trace.investigate(exec_seq_id, kind='seq_id')
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Exec {exec_seq_id} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

def investigate_actor(bundle_name: str, actor: str) -> dict[str, Any]:
    '''Investigate a live Trace `actor` via `Trace.investigate()`'''    
    trace = get_trace(TRACES, bundle_name)

    investigated = trace.investigate(actor, kind="actor")
    if investigated.inspected.exists is False:
        raise TraceLookupError(f'Actor {actor} was not found in trace {bundle_name}')
    
    return {"result": investigated.to_dict()}

def trace_to_dict(bundle_name: str) -> dict[str, Any]:
    '''Return a live Trace object as a serialisable dictionary'''
    trace = get_trace(TRACES, bundle_name)
    return {'result': trace.to_dict(serialise_events=True)}

def initialise_traces_from_bundles(ignore_invalid:bool=False) -> tuple[list[str], list[str]]:
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

def get_init_meta(request: Request) -> dict[str, Any]:
    '''Return Trace auto-initialisation results'''
    return {"result": getattr(
        request.app.state,
        "init",
        {}
    )}

# MIDDLEWARE
async def initialise_traces(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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

# DICTIONARIES FOR ENDPOINT REGISTRATION 
MIDDLEWARE_HANDLERS = [
    {"middleware_type": "http", "func": initialise_traces}
]

TIDE_TRACE_ENDPOINTS = [
    {"methods": ["GET"], "endpoint": trace_to_dict,                     "path": "/traces/{bundle_name}"},
    {"methods": ["GET"], "endpoint": investigate_ref,                   "path": "/traces/{bundle_name}/ref"},
    {"methods": ["GET"], "endpoint": investigate_exec,                  "path": "/traces/{bundle_name}/exec"},
    {"methods": ["GET"], "endpoint": investigate_actor,                 "path": "/traces/{bundle_name}/actor"},
]

# FASTAPI ENDPOINT-HANDLERS DICTIONARY 
ENDPOINT_HANDLERS = [
    *TIDE_TRACE_ENDPOINTS,

    {"methods": ["GET"], "endpoint": get_init_meta,                     "path": "/meta/init"},
    {"methods": ["GET"], "endpoint": redirect_to_docs,                  "path": "/"},
    {"methods": ["GET"], "endpoint": local_bundles,                     "path": "/local/bundles"},
    {"methods": ["GET"], "endpoint": loaded_traces,                     "path": "/traces"},
    {"methods": ["GET"], "endpoint": persisted_bundles,                 "path": "/bundles"},

    {"methods": ["POST"],"endpoint": load_trace,                        "path": "/register/trace/{bundle_name}"},
    {"methods": ["POST"],"endpoint": persist_bundle,                    "path": "/register/bundle/{bundle_name}"},
    {"methods": ["POST"],"endpoint": initialise_traces_from_bundles,    "path": "/dev/initialise_traces"},
    
]

