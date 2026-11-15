from tideapi.helpers.fastapi import initialise_fastapi_app
from tideapi_core import request_handlers
from tideapi.exceptions import DataValidationError


from fastapi.testclient import TestClient
import pytest

class TestMiddleware:
    
    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(request_handlers, "TRACES", {})

    def test_initialise_traces(self, monkeypatch, api_db, tide_bundle):
        calls = []
        
        # Test docs_load calls `initialise_traces` 
        with monkeypatch.context() as m:
            def wrapped(ignore_invalid=False):
                calls.append("initialised")
                return ['example.json'], []

            m.setattr(
                request_handlers,
                "initialise_traces_from_bundles",
                wrapped
            )

            app = initialise_fastapi_app(
                MIDDLEWARE_HANDLERS=[{
                    "middleware_type": "http",
                    "func": request_handlers.initialise_traces
                }]
            )
        
            client = TestClient(app)
        
            client.get("/openapi.json")
            assert calls == []
        
            client.get("/docs")
            assert calls == ["initialised"]

        # Test valid bundles
        with monkeypatch.context() as m:
            monkeypatch.setattr(request_handlers, "STORE", api_db)
            api_db.set('example.json', tide_bundle)
            api_db.set('invalid.json', '1234')

            app = initialise_fastapi_app(
                MIDDLEWARE_HANDLERS=[{
                    "middleware_type": "http",
                    "func": request_handlers.initialise_traces
                }]
            )   

            TRACES = getattr(request_handlers, "TRACES")

            assert len(TRACES) == 0

            client = TestClient(app)
            assert not hasattr(client.app.state, "init")

            response = client.get("/docs")
            assert response.status_code == 200
            
            init_meta = getattr(client.app.state, "init")
            assert init_meta is not None
            assert 'traces' in init_meta
            assert len(init_meta['traces']) == 2
            assert all([name in init_meta['traces'] for name in ['registered', 'failed']]) 
            assert init_meta['traces']['registered'] == ['example.json'] 
            assert init_meta['traces']['failed'] == ['invalid.json'] 

            assert isinstance(TRACES, dict)
            assert len(TRACES) == 1



class TestMiddlewareHelpers:
    
    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(request_handlers, "TRACES", {})

    def test_initialise_traces_from_bundles(self, monkeypatch, endpoints, api_db, tide_bundle):
        api_db.set('example.json', tide_bundle)
        monkeypatch.setattr(request_handlers, "STORE", api_db)
        
        TRACES = getattr(request_handlers, "TRACES")
        
        assert len(TRACES) == 0
        registered, failed = request_handlers.initialise_traces_from_bundles()
        assert failed == []
        assert registered == ['example.json']
        
        pre_state = dict(TRACES)
        assert len(pre_state) == 1
        
        api_db.set('invalid.json', '1234')
        with pytest.raises(DataValidationError):
            request_handlers.initialise_traces_from_bundles()
        fail_state = dict(TRACES)
        assert pre_state == fail_state         

        # Test failure state with ignore_invalid=True
        registered, failed = request_handlers.initialise_traces_from_bundles(ignore_invalid=True)
        assert failed == ['invalid.json']
        assert registered == ['*example.json']
        
        assert len(TRACES) == 1
        
        post_state = dict(TRACES)
        assert pre_state == post_state

        

        
