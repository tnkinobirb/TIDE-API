'''
    NATIVE TIDE-ECOSYSTEM HELPERS
'''
import json
from pathlib import Path

from tide_tooling import TIDE, Trace
from tideapi_core.exceptions import (
    APILookupError,
    DataValidationError,
)

def validate_bundle_name(bundle_name: str) -> str:
    '''Validate a bundle_name string'''
    prohibited = ['/', '\\']    

    if not bundle_name.endswith(".json") or any(p in bundle_name for p in prohibited):
        raise DataValidationError(f"Invalid bundle name {bundle_name}")

    return bundle_name

# Bundle validation
def validate_tide_bundle(path: Path) -> str:
    '''Validate structure of a TIDE bundle.json file via Path'''
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

    try:
        TIDE.from_bundle(bundle)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise DataValidationError("Invalid TIDE bundle format") from exc

    return raw

# TRACES
def list_traces(TRACES: dict[str, Trace]) -> list[str]:
    '''List which bundles are loaded as TIDE Traces'''
    return list(TRACES)

def get_trace(TRACES: dict[str, Trace], bundle_name: str) -> Trace:
    '''Retrieve a loaded TIDE Trace via its associated bundle_name'''
    if not isinstance(bundle_name, str):
        raise DataValidationError(f"Invalid bundle_name type: {type(bundle_name)}") 
    trace = TRACES.get(bundle_name)
    if trace is None:
        raise APILookupError(f"Unknown trace: {bundle_name}")
    return trace



