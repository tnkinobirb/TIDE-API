import uuid
from typing import TYPE_CHECKING
from tideapi_core.exceptions import (
    APILookupError,
    DataValidationError,
)

if TYPE_CHECKING:
    from pathlib import Path


# BUNDLES

def list_bundles(TRACES: dict) -> list:
    return list(trace["bundle_name"] for trace in TRACES.values())

def is_bundle_registered(REGISTERED_BUNDLES: dict, bundle_name:str) -> bool:
    return bundle_name in REGISTERED_BUNDLES

def register_bundle_name(BUNDLES:dict, bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        bundle_id = uuid.uuid4().hex
        BUNDLES[bundle_id] = bundle_name
    else:
        raise DataValidationError('`bundle_name` must be a str identifier.')
    return bundle_id

def get_bundle_name(TRACES: dict, trace_id: str) -> str:
    trace = get_trace(TRACES, trace_id)
    return trace["bundle_name"]

def resolve_bundle(ROOT: Path, bundle_name: str) -> Path:
    root = ROOT.resolve()
    path = (root / bundle_name).resolve()

    if path.parent != root or path.suffix.lower() != ".json":
        raise APILookupError(f"Invalid bundle name {bundle_name}")

    if not path.is_file():
        raise APILookupError(f"Bundle not found{bundle_name}")

    return path

# TRACES

def list_traces(TRACES: dict) -> list:
    return list(TRACES)

def get_trace(TRACES: dict, trace_id: str) -> dict:
    trace = TRACES.get(trace_id)
    if trace is None:
        raise APILookupError(f"Unknown trace: {trace_id}")
    return trace



