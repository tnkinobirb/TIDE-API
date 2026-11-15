from fastapi import FastAPI
from tideapi.exceptions import AlreadyRegisteredError

def register_middleware_handlers(app: FastAPI, MIDDLEWARE_HANDLERS: dict) -> None:
    for handler in MIDDLEWARE_HANDLERS:
        app.middleware(handler['type'])(handler['function'])
    
def register_endpoint_handlers(app: FastAPI, ENDPOINT_HANDLERS: list[dict]) -> None:
    seen = {}
    for handler in ENDPOINT_HANDLERS:
        if next(iter(
            route for route in list(app.routes) if route.path == handler['path']
        ), None) or handler['path'] in seen:
            raise AlreadyRegisteredError(f"Route for {handler['path']} already exists!")

        seen[handler['path']] = handler
        
    for handler in list(seen.values()):
        app.add_api_route(
            path=handler['path'], 
            methods=handler['methods'],
            endpoint=handler['function'], 
        )

def initialise_fastapi_app(
    ENDPOINT_HANDLERS: list[dict] | None = None,
    EXCEPTION_HANDLERS: dict | None = None,
    MIDDLEWARE_HANDLERS: list[dict] | None = None,
    **kwargs
) -> FastAPI:
    ENDPOINT_HANDLERS = {} if ENDPOINT_HANDLERS is None else ENDPOINT_HANDLERS
    EXCEPTION_HANDLERS = {} if EXCEPTION_HANDLERS is None else EXCEPTION_HANDLERS
    MIDDLEWARE_HANDLERS = {} if MIDDLEWARE_HANDLERS is None else MIDDLEWARE_HANDLERS
    
    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, **kwargs)
    register_middleware_handlers(app, MIDDLEWARE_HANDLERS)
    register_endpoint_handlers(app, ENDPOINT_HANDLERS)
    return app


