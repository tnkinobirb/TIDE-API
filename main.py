from tideapi.handlers import (
    ENDPOINT_HANDLERS,
    EXCEPTION_HANDLERS,
    MIDDLEWARE_HANDLERS,
)

from tideapi.helpers.fastapi import (
    initialise_fastapi_app,
)

app = initialise_fastapi_app(
    ENDPOINT_HANDLERS=ENDPOINT_HANDLERS,
    EXCEPTION_HANDLERS=EXCEPTION_HANDLERS,  
    MIDDLEWARE_HANDLERS=MIDDLEWARE_HANDLERS,
    debug=True)