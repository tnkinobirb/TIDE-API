'''
    FASTAPI EXCEPTION HANDLERS

    The table below describes which exception types must be attributed to which HTML `status_code`.
    `status_code` table:
        LookupErrors: 404
        ValidationErrors: 400
        AlreadyRegisteredErrors: 409
        InternalExceptionErrors: 500

'''
from fastapi import Request
from fastapi.responses import JSONResponse
from tideapi_core.exceptions import (
    APILookupError,         # 404
    TraceLookupError,       # 404
    APIStoreLookupError,    # 404
    DataValidationError,    # 400
    AlreadyRegisteredError, # 409
    InternalExceptionError, # 500
)

def handle_trace_lookup_exception(request: Request, exc: TraceLookupError) -> JSONResponse:
    '''Handle LookupErrors as 404'''
    return JSONResponse(
        status_code=404,
        content={"result":{
            "str": f"{str(exc)}",
            "error": type(exc).__name__
        }},
    )

def handle_api_lookup_exception(request: Request, exc: APILookupError) -> JSONResponse:
    '''Handle LookupErrors as 404'''
    return JSONResponse(
        status_code=404,
        content={"result":{
            "str": f"{str(exc)}",
            "error": type(exc).__name__
        }},
    )

def handle_data_validation_exception(request: Request, exc: DataValidationError) -> JSONResponse:
    '''Handle DataValidationError as 400'''
    return JSONResponse(
        status_code=400,
        content={"result":{
            "str": f"{str(exc)}",
            "error": type(exc).__name__
        }},
    )

def handle_already_registered_exception(request: Request, exc: AlreadyRegisteredError) -> JSONResponse:
    '''Handle AlreadyRegisteredErrors as 409'''
    return JSONResponse(
        status_code=409,
        content={"result":{
            "str": f"{str(exc)}",
            "error": type(exc).__name__
        }},
    )

def handle_internal_exception(request: Request, exc: InternalExceptionError) -> JSONResponse:
    '''Handle InternalExceptionErrors as 500'''
    return JSONResponse(
        status_code=500,
        content={"result":{
            "str": f"{str(exc)}",
            "error": type(exc).__name__
        }},
    )

# FASTAPI EXCEPTION HANDLERS DICTIONARY
EXCEPTION_HANDLERS = {
    APILookupError: handle_api_lookup_exception,
    TraceLookupError: handle_trace_lookup_exception,
    APIStoreLookupError: handle_api_lookup_exception,
    DataValidationError: handle_data_validation_exception,
    InternalExceptionError: handle_internal_exception,
    AlreadyRegisteredError: handle_already_registered_exception
}
