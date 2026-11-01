from typing import TYPE_CHECKING
from fastapi import FastAPI, APIRouter

def register_middleware_handlers(app: FastAPI, MIDDLEWARE_HANDLERS: dict) -> None:
    for handler in MIDDLEWARE_HANDLERS:
        app.middleware(handler['type'])(handler['function'])
    
def register_endpoint_handlers(app: FastAPI, ENDPOINT_HANDLERS: list[dict]) -> None:
    for handler in ENDPOINT_HANDLERS:
        app.add_api_route(
            path=handler['path'], 
            endpoint=handler['function'], 
            methods=handler['methods']
        )

def initialise_fastapi_app(
    ENDPOINT_HANDLERS: list[dict] | None = None,
    EXCEPTION_HANDLERS: dict | None = None,
    MIDDLEWARE_HANDLERS: list[dict] | None = None,
    **kwargs
) -> FastAPI:

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, **kwargs)
    register_middleware_handlers(app, MIDDLEWARE_HANDLERS)
    register_endpoint_handlers(app, ENDPOINT_HANDLERS)
    return app
