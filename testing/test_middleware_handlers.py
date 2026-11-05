from tideapi.handlers import initialise_traces_on_docs_load
from tideapi.helpers.fastapi import initialise_fastapi_app
from fastapi.testclient import TestClient

from tideapi_core import request_handlers

def test_docs_middleware(sample_trace, sample_trace_uuid, monkeypatch, tmp_path):
    calls = []

    with monkeypatch.context() as m:
        m.setattr(
            request_handlers,
            "initialise_traces_from_bundles",
            lambda: calls.append("initialised") 
        )

        app = initialise_fastapi_app(
            MIDDLEWARE_HANDLERS=[{
                "type": "http",
                "function": request_handlers.initialise_traces_on_docs_load
            }]
        )
    
        client = TestClient(app)
    
        client.get("/openapi.json")
        assert calls == []
    
        client.get("/docs")
        assert calls == ["initialised"]

    with monkeypatch.context() as m:
        m.setattr(request_handlers, 'ROOT', tmp_path)
        m.setattr(request_handlers.TIDE, 'from_bundle', lambda self: {})
        (tmp_path / "example.json").write_text('{}')
        app = initialise_fastapi_app(
            MIDDLEWARE_HANDLERS=[{
                "type": "http",
                "function": request_handlers.initialise_traces_on_docs_load
            }]
        )   

        BUNDLES = getattr(request_handlers, "BUNDLES")
        TRACES = getattr(request_handlers, "TRACES")
        REGISTERED_BUNDLES = getattr(request_handlers, "REGISTERED_BUNDLES")

        assert all([len(ctx) == 0 for ctx in [TRACES, REGISTERED_BUNDLES]]) 

        client = TestClient(app)
        assert client.get("/docs").status_code == 200
        
        assert all([isinstance(ctx, dict) for ctx in [BUNDLES, TRACES, REGISTERED_BUNDLES]])
        assert len(BUNDLES) == 1
        assert len(BUNDLES) == len(TRACES) == len(REGISTERED_BUNDLES)


