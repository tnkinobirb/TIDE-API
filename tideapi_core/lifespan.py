'''
    TIDE-API LIFESPAN MANAGEMENT
'''
from fastapi import FastAPI
from contextlib import asynccontextmanager
from tideapi_core import request_handlers
from tideapi.handlers import initialise_traces_from_bundles
from fastapi.concurrency import run_in_threadpool
from tideapi_core.persistence.tideapi_store import TIDEPSQLStore

# TIDE-API FASTAPI-LIFESPAN FUNCTION
@asynccontextmanager
async def lifespan(app: FastAPI):
    '''Lifespan manager function for TIDE-API FastAPI application instances'''
    try:
        registered, failed  = await run_in_threadpool(
            initialise_traces_from_bundles,
            ignore_invalid=True
        )

        app.state.init = {
            "traces": {
                "registered": registered,
                "failed": failed
            }
        }

        yield
        
    finally:
        if isinstance(request_handlers.STORE, TIDEPSQLStore):
            await run_in_threadpool(request_handlers.STORE.close)

