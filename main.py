
from fastapi import FastAPI, HTTPException
from tide_tooling import TIDE, Trace
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).parent / "bundles"
app = FastAPI(debug=True)

BUNDLES = {}
TRACES = {}

def list_traces():
    return list(TRACES)

def list_bundles():
    return list(trace["bundle_name"] for trace in TRACES.values())

def bundle_by_trace_id(trace_id: str):
    trace = get_trace(trace_id)
    return trace["bundle_name"]

def resolve_bundle(bundle_name: str) -> Path:
    root = ROOT.resolve()
    path = (root / bundle_name).resolve()

    if path.parent != root or path.suffix.lower() != ".json":
        raise HTTPException(400, f"Invalid bundle name {bundle_name}")

    if not path.is_file():
        raise HTTPException(404, f"Bundle not found{bundle_name}")

    return path

def http_exec(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)

def get_bundle_name(trace_id: str) -> str:
    trace = get_trace(trace_id)
    return trace["bundle_name"]

def get_trace(trace_id: str) -> dict:
    trace = TRACES.get(trace_id)
    if trace is None:
        raise http_exec(status_code=404, detail=f"Unknown trace: {trace_id}")
    return trace

def register_bundle_name(bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        bundle_id = uuid.uuid4().hex
        BUNDLES[bundle_id] = bundle_name
    else:
        raise TypeError('bundle_name must be a str identifier.')
    return bundle_id

# REGISTER

@app.post('/register/trace/{bundle_name}')
def register_trace(bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        bundle_id = register_bundle_name(bundle_name)
        trace = TIDE.from_bundle(ROOT / BUNDLES[bundle_id])
        trace_id = uuid.uuid4().hex

        TRACES[trace_id] = {
            "trace": trace,
            "bundle_name": bundle_name
        }

    else:
        raise http_exec(status_code=500, detail='bundle_name must be a str identifier.')
    return trace_id


# SHOW

@app.get('/show/bundles')
def available_bundles():
    bundles = []
    if ROOT.exists():
        for item in ROOT.iterdir():
            if item.is_file():
                bundles.append(item.name)

    return {"result": bundles}

@app.get('/show/traces')
def available_traces():
    return {
        'result': {
            trace_id: get_bundle_name(trace_id)
            for trace_id in list_traces()
        }
    }

@app.get('/show/traces/{trace_id}')
def trace(trace_id: str):
    trace = get_trace(trace_id)["trace"]
    return {'result': trace.show(colour=False)}


# GET

@app.get('/get/traces/{trace_id}/bundle_name')
def bundle_name_by_trace_id(trace_id: str):
    return {'result': str(get_bundle_name(trace_id))}


# INSPECT / DEFAULT LOOKUP BEHAVIOUR

@app.get('/traces/{trace_id}/refs/{ref}')
def inspect_ref(trace_id: str, ref: str):
    trace = get_trace(trace_id)["trace"]

    inspected = trace.inspect_ref(ref).to_dict()
    if inspected["exists"] is False:
        raise http_exec(
            status_code=404,
            detail=f"Ref {ref} not found in trace {trace_id}"
        )
    return {"result": inspected}


# DEV

@app.post('/dev/quick_init')
def quick_init():
    for bundle_name in available_bundles()['result']:
        register_trace(bundle_name)
    return list(TRACES)
