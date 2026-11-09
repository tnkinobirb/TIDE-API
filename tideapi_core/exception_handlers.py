from fastapi import Request  
from fastapi.responses import JSONResponse
from tideapi_core.exceptions import (
    TraceLookupError,
    APILookupError,
    DataValidationError,
    InternalExceptionError,
    RouteAlreadyRegisteredError,
)

def handle_trace_lookup_exception(request: Request, exc: TraceLookupError):
    return JSONResponse(
        status_code=404,
        content={
            "str": f"Oops! {str(exc)}. Now, where was i....?",
            "error": type(exc).__name__
        },
    )

def handle_api_lookup_exception(request: Request, exc: APILookupError):
    return JSONResponse(
        status_code=404,
        content={
            "str": f"Oops! {str(exc)}. Oh - There goes a bird....",
            "error": type(exc).__name__
        },
    )

def handle_data_validation_exception(request: Request, exc: DataValidationError):
    return JSONResponse(
        status_code=418, # or 400 for seriousness
        content={
            "str": f"Cannae make a cawfee with a teepaet! {str(exc)}. |:<",
            "error": type(exc).__name__
        },
    )
    
def handle_internal_exception(request: Request, exc: InternalExceptionError):
    return JSONResponse(
        status_code=500,
        content={
            "str": f"Ah - my bad...: {str(exc)}. Sorry!",
            "error": type(exc).__name__
        },
    )


# EXCEPTION HANDLERS DICT

EXCEPTION_HANDLERS = {
    APILookupError: handle_api_lookup_exception,
    TraceLookupError: handle_trace_lookup_exception,
    InternalExceptionError: handle_internal_exception,
    DataValidationError: handle_data_validation_exception,
}
