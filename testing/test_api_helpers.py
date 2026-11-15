import pytest
import fastapi
import fastapi.testclient

from tideapi.helpers.native import (
    list_traces,
    validate_bundle_name,
    get_trace,
)

from tideapi.helpers.fastapi import (
    initialise_fastapi_app,
    register_endpoint_handlers,
    register_middleware_handlers,
)

from tideapi.exceptions import (DataValidationError, APILookupError, AlreadyRegisteredError)

class TestNativeHelpers:

    def test_valid_bundle_name(self, sample_bundle_name):
        result = validate_bundle_name(sample_bundle_name)
        assert result == sample_bundle_name

    def test_unknown_bundle_name(self, sample_traces_dict):
        with pytest.raises(APILookupError):
            get_trace(sample_traces_dict, "non-existent-id")

    def test_invalid_extension(self):
        with pytest.raises(DataValidationError):
            validate_bundle_name("example.exe")

    @pytest.mark.parametrize("name", [
        "example",
        "\\example",
        "..\\example",
        "../path/to/example.json",
    ])
    def test_invalid_names(self, name):
        with pytest.raises(DataValidationError):
            validate_bundle_name(name)

    def test_list_traces(self, sample_traces_dict, sample_bundle_name):
        bundle_names = list_traces(sample_traces_dict)
        assert type(bundle_names) is list
        assert len(bundle_names) == 1
        assert bundle_names[0] == sample_bundle_name

    def test_get_trace(self, sample_traces_dict, sample_bundle_name):
        trace = get_trace(sample_traces_dict, sample_bundle_name)
        assert trace is sample_traces_dict[sample_bundle_name]

        with pytest.raises(APILookupError):
            get_trace(sample_traces_dict, "unknown")

        with pytest.raises(DataValidationError):
            get_trace(sample_traces_dict, 1)
            

class TestFastAPIHelpers:
    def test_endpoint_registration(self, sample_endpoints):
        app = fastapi.FastAPI()
        preregistered_endpoints = list(app.routes)
        register_endpoint_handlers(app, sample_endpoints)
        registered_endpoints = list(app.routes)
        assert len(registered_endpoints)-len(preregistered_endpoints) == len(sample_endpoints)
        client = fastapi.testclient.TestClient(app)

        for idx, route in enumerate(registered_endpoints[-len(sample_endpoints):]):
            assert route.path == sample_endpoints[idx]['path']
            assert route.methods == set(sample_endpoints[idx]['methods'])
            assert route.endpoint is sample_endpoints[idx]['endpoint']
            response = client.get(route.path)
            assert response.status_code == 200
            assert response.json() == {'result':'example'}

    def test_middleware_registration(self, sample_middleware):
        app = fastapi.FastAPI()
        preregistered_middleware = list(app.user_middleware)
        register_middleware_handlers(app, sample_middleware)
        registered_middleware = list(app.user_middleware)
        assert len(registered_middleware)-len(preregistered_middleware) == len(sample_middleware)

        app.add_api_route(
            '/',
            lambda: {'result': 'example'},
            methods=['GET']
        )

        client = fastapi.testclient.TestClient(app)
        response = client.get('/')
        assert response.status_code == 200
        assert response.headers['Test-Middleware_0'] == 'example_0'
        assert response.headers['Test-Middleware_1'] == 'example_1'

    def test_fastapi_app_initialisation_succeeds_with_no_handlers(self):    
        app = initialise_fastapi_app()
        app.add_api_route(
            '/',
            lambda: {'result': 'example'},
            methods=['GET']
        )
        client = fastapi.testclient.TestClient(app)
        response = client.get('/')
        assert response.status_code == 200
        assert response.json() == {'result':'example'}

    def test_fastapi_app_initialisation(self, sample_endpoints, sample_middleware, sample_exception_handlers):
        app = initialise_fastapi_app(ENDPOINT_HANDLERS=sample_endpoints, EXCEPTION_HANDLERS=sample_exception_handlers, MIDDLEWARE_HANDLERS=sample_middleware, )
        client = fastapi.testclient.TestClient(app)

        def raise_idx_exc(): raise IndexError()
        def raise_val_exc(): raise ValueError()

        for (path, exc, status, error) in [
            ('/idx_exc', raise_idx_exc, 404, IndexError), 
            ('/val_exc', raise_val_exc, 500, ValueError)
        ]:
             
            app.add_api_route(   
                path,
                exc,
                methods=['GET']
            )

            client = fastapi.testclient.TestClient(app)
            response = client.request(method="GET", url=path)

            assert response.status_code == status
            assert response.json() == {"error": error.__name__}
            assert response.headers['Test-Middleware_0'] == 'example_0'
            assert response.headers['Test-Middleware_1'] == 'example_1'        
        
        for endpoint in sample_endpoints:
            response = client.get(endpoint['path'])
            assert response.status_code == 200
            assert response.json() == {'result': 'example'}
            assert response.headers['Test-Middleware_0'] == 'example_0'
            assert response.headers['Test-Middleware_1'] == 'example_1'

    def test_post_on_get_returns_405(self):
        endpoint_handler = {   
            'path':'/',
            'endpoint': lambda: {'result': 'example'},
            'methods':['GET']
        }
        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint_handler, ])
        client = fastapi.testclient.TestClient(app)
        response= client.request(method="POST", url='/')
        assert response.status_code == 405

    def test_fastapi_double_registration_raises(self):
        endpoint_handler = {   
            'path':'/',
            'endpoint': lambda: {'result': 'example'},
            'methods': ['GET']
        }
        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint_handler])
        
        pre_routes = list(app.routes)
        pre_ware = list(app.user_middleware)
        pre_exc = dict(app.exception_handlers)

        with pytest.raises(AlreadyRegisteredError):
            register_endpoint_handlers(app, [endpoint_handler])

        post_routes = list(app.routes)
        post_ware = list(app.user_middleware)
        post_exc = dict(app.exception_handlers)

        assert pre_routes == post_routes
        assert pre_ware == post_ware
        assert pre_exc == post_exc
        
    def test_endpoint_registration_atomicity_on_tide_api_failure(self):
        endpoint_handler = {   
            'path':'/',
            'endpoint': lambda: {'result': 'example'},
            'methods': ['GET']
        }
        app = initialise_fastapi_app()
        pre_routes_len = len(app.routes)
        with pytest.raises(AlreadyRegisteredError):
            register_endpoint_handlers(app, [endpoint_handler, endpoint_handler])
        post_routes_len = len(app.routes)

        assert pre_routes_len == post_routes_len

    
