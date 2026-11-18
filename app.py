'''
TIDE-API Application Setup file.

To setup a TIDE-API instance:
    If you do not have an existing project folder with TIDE-API cloned within:
        mkdir tideapi_project
        cd tideapi_project
        git clone https://github.com/tnkinobirb/TIDE-API

    Then enter the following commands:
        
        First, if you haven't setup a virtual environment:
            Windows (powershell):
                python -m venv .venv 
                . .venv/Scripts/activate
            Linux:
                python -m venv .venv 
                . .venv/bin/activate
            
        Then:
            git clone https://github.com/tnkinobirb/TIDE-Tooling
            python -m pip install TIDE-Tooling/. fastapi[standard]
            fastapi TIDE-API/app.py

        Open a browser at https://127.0.0.1:8000/docs and enjoy!

    By default, local .json bundles within the `BUNDLE_DIR` directory will be detected, loaded and persisted.
    To disable this behaviour, set the environment variable `INCLUDE_BUNDLE_DIR_WHEN_LOADING` to 'false'.

    ENV CONFIGURATION:
        Adjust environment variables to change directory locations or desired behaviour.
        
        How to set an environment variable (temporarily):
            Windows (Powershell):
                $Env:VAR='value'
                e.g:
                    $Env:INCLUDE_BUNDLE_DIR_WHEN_LOADING='false'
            Linux:
                export VAR='value'
                e.g:
                    export INCLUDE_BUNDLE_DIR_WHEN_LOADING='false'           
        
        PATHS:
            DB_PATH: Where TIDEAPIStore's database should be created, or is located. 
            BUNDLE_DIR: The directory in which local bundle .json files are discovered.  
        
        BEHAVIOUR CONFIGS:
            INCLUDE_BUNDLE_DIR_WHEN_LOADING: 'true'|'false'
                - 'true': Include local bundle .json files when loading traces
                - 'false': Only load bundles .json strings persisted within `bundles.db`
'''    

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
    debug=True # Remove before prod
)
