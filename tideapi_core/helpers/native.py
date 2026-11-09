import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from tideapi_core.exceptions import (
    APILookupError,
    DataValidationError,
)
from tideapi_core.persistence.tideapi_store import TIDEAPIStore


# BUNDLES

def list_bundles(TRACES: dict) -> list:
    return list(trace["bundle_name"] for trace in TRACES.values())

def is_bundle_registered(REGISTERED_BUNDLES: dict, bundle_name:str) -> bool:
    return bundle_name in REGISTERED_BUNDLES

def register_bundle_name(BUNDLES: dict, bundle_name: str) -> str:
    if isinstance(bundle_name, str):
        bundle_id = uuid.uuid4().hex
        BUNDLES[bundle_id] = bundle_name
    else:
        raise DataValidationError('`bundle_name` must be a str identifier.')
    return bundle_id

def get_bundle_name(TRACES: dict, trace_id: str) -> str:
    trace = get_trace(TRACES, trace_id)
    return trace["bundle_name"]

def validate_bundle_name(bundle_name: str) -> str:
    prohibited = ['/', '\\']    

    if not bundle_name.endswith(".json") or any(p in bundle_name for p in prohibited):
        raise DataValidationError(f"Invalid bundle name {bundle_name}")

    return bundle_name

# TRACES

def list_traces(TRACES: dict) -> list:
    return list(TRACES)

def get_trace(TRACES: dict, trace_id: str) -> dict:
    if not isinstance(trace_id, str):
        raise DataValidationError(f"Invalid trace_id type: {type(trace_id)}") 
    trace = TRACES.get(trace_id)
    if trace is None:
        raise APILookupError(f"Unknown trace: {trace_id}")
    return trace



