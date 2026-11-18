'''
    FAST-API INTEGRATION
'''

from tideapi_core.lifespan import lifespan
from tideapi_core.helpers.fastapi import (
    initialise_fastapi_app,
    register_endpoint_handlers,
    register_middleware_handlers,
)
