import pytest
import fastapi
import fastapi.testclient

from tideapi.helpers.native import (
    list_bundles,
    validate_bundle_name,
    get_bundle_name,
    get_trace,
    register_bundle_name,
    is_bundle_registered,
)

from tideapi.helpers.fastapi import (
    initialise_fastapi_app,
    register_endpoint_handlers,
    register_middleware_handlers,
)

from tideapi.exceptions import (DataValidationError, APILookupError)

class TestNativeHelpers:

    def test_valid_bundle_name(self, bundle_dir, sample_bundle_name):
        result = validate_bundle_name(bundle_dir, sample_bundle_name)
        assert result == bundle_dir / sample_bundle_name

    def test_unknown_bundle_name(self, bundle_dir):
        with pytest.raises(APILookupError):
            validate_bundle_name(bundle_dir, "non-existent.json")

    def test_unknown_trace_id(self, sample_traces_dict):
        with pytest.raises(APILookupError):
            get_trace(sample_traces_dict, "non-existent-id")

    def test_invalid_extension(self, bundle_dir):
        with pytest.raises(DataValidationError):
            validate_bundle_name(bundle_dir, "example.exe")

    @pytest.mark.parametrize("name", [
        "example",
        "\\example",
        "..\\example",
        "../path/to/example.json",
    ])
    def test_invalid_names(self, bundle_dir, name):
        with pytest.raises(DataValidationError):
            validate_bundle_name(bundle_dir, name)

    def test_get_bundle_name(self, sample_traces_dict, sample_trace_uuid):        
        name = get_bundle_name(sample_traces_dict, sample_trace_uuid)
        assert name == 'example.json'

    def test_register_bundle_name(self, empty_dict, sample_bundle_name):
        bundle_id = register_bundle_name(empty_dict, sample_bundle_name)
        assert len(empty_dict) == 1
        assert empty_dict.get(bundle_id) == sample_bundle_name
        assert type(bundle_id) is str
        assert len(bundle_id) == 32

    def test_list_bundles(self, sample_traces_dict, sample_bundle_name):
        bundles = list_bundles(sample_traces_dict)
        assert type(bundles) is list
        assert len(bundles) == 1
        assert bundles[0] == sample_bundle_name

    def test_get_trace(self, sample_traces_dict, sample_trace_uuid, sample_bundle_uuid, sample_bundle_name):
        trace = get_trace(sample_traces_dict, sample_trace_uuid)
        expected_trace_keys = ["trace", "bundle_id", "bundle_name"] 
        assert type(trace) is dict
        assert len(trace) == 3
        assert all([name in list(trace.keys()) for name in expected_trace_keys])
        assert trace is sample_traces_dict[sample_trace_uuid]
        assert trace["bundle_id"] == sample_bundle_uuid
        assert trace["bundle_name"] == sample_bundle_name

    @pytest.mark.parametrize(
        ["name", "should_exist"],
        [
            (None, True),
            ("nonexistent.json", False),
        ]
    )
    def test_is_bundle_registered(self, sample_registered_bundles_dict, sample_bundle_name, name, should_exist):    
        if name is None and should_exist:
            name = sample_bundle_name
        registered = is_bundle_registered(sample_registered_bundles_dict, name)
        assert type(registered) is bool
        assert registered is should_exist


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
            assert route.methods == sample_endpoints[idx]['methods']
            assert route.endpoint == sample_endpoints[idx]['function']
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
            methods={'GET'}
        )

        client = fastapi.testclient.TestClient(app)
        response = client.get('/')
        assert response.status_code == 200
        assert response.headers['Test-Middleware'] == 'example'


