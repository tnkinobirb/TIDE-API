from tideapi_core.lifespan import lifespan 
from tideapi.helpers.fastapi import initialise_fastapi_app
from tideapi.handlers import (
    ENDPOINT_HANDLERS,
    EXCEPTION_HANDLERS,
    MIDDLEWARE_HANDLERS,
)

# INITIALISE FASTAPI APPLICATION
app = initialise_fastapi_app(
    ENDPOINT_HANDLERS=ENDPOINT_HANDLERS,
    EXCEPTION_HANDLERS=EXCEPTION_HANDLERS,
    MIDDLEWARE_HANDLERS=MIDDLEWARE_HANDLERS,
    lifespan=lifespan,
    debug=True
)
