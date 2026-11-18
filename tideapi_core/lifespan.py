'''
    TIDE-API LIFESPAN MANAGEMENT
'''
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from tideapi.handlers import initialise_traces_from_bundles

# TIDE-API FASTAPI-LIFESPAN FUNCTION
@asynccontextmanager
async def lifespan(app: FastAPI):
    '''Lifespan manager function for TIDE-API FastAPI application instances'''
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
