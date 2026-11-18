import pytest
from tideapi.handlers import EXCEPTION_HANDLERS
from fastapi.responses import Response
from fastapi.testclient import TestClient
from tideapi.fastapi import initialise_fastapi_app
from tideapi.exceptions import (
    APILookupError, 
    TraceLookupError, 
    APIStoreLookupError,
    DataValidationError, 
    AlreadyRegisteredError,
    InternalExceptionError,
)

exceptions = {
    test[0].__name__: test for test in 
    [
        (APILookupError, 404), 
        (TraceLookupError, 404),
        (APIStoreLookupError, 404),
        (DataValidationError, 400),
        (AlreadyRegisteredError, 409),
        (InternalExceptionError, 500),
    ]
}

# ENSURE ALL REGISTERED EXCS ARE TESTED
should_test = [exc.__name__ for exc in EXCEPTION_HANDLERS.keys()]
assert set(should_test) <= set(exceptions.keys()), f"Missing exception tests: {set(should_test) - set(exceptions.keys())}"

# ENDPOINT FUNCTION
def raise_error(exc: str) -> None:
    if exc in exceptions:
        raise exceptions[exc][0]('testing')
    raise RuntimeError('Cannot raise invalid exception')

# TEST HELPERS
def exc_endpoint() -> dict:
    return {'path':'/exc', 'endpoint': raise_error, 'methods':['POST']}

def init_exc_endpoint(exc: Exception) -> TestClient:
    if exc not in EXCEPTION_HANDLERS:
        raise RuntimeError('Cannot handle invalid exception')
    
    exc_handlers = {exc: EXCEPTION_HANDLERS[exc]}
    app = initialise_fastapi_app(EXCEPTION_HANDLERS=exc_handlers, ENDPOINT_HANDLERS=[exc_endpoint()])    
    client = TestClient(app)
    return client

def is_valid_exc_response(exc: Exception, exc_response: Response):
    return exc_response.json() == {
        "result": {
            "str": "testing",
            "error": exc.__name__
            }
        }

def exc_tester(exc: Exception, status_code:int):
    client = init_exc_endpoint(exc)
    response = client.post('/exc', params={'exc': exc.__name__})
    assert response.status_code == status_code
    assert is_valid_exc_response(exc, response) 

# TESTER
@pytest.mark.parametrize(['exc', 'status_code'], tuple(exceptions.values()))
def test_handle_api_lookup_exception(exc, status_code):
    exc_tester(exc, status_code)
