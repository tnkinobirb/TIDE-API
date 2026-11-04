from tideapi.handlers import (
    show_trace,
    inspect_ref,
    inspect_exec,
    inspect_actor,
    redirect_to_docs,
    available_traces,
    available_bundles,
    bundle_name_by_trace_id,
    ENDPOINT_HANDLERS
)
import json
import pytest
import tideapi_core.request_handlers as request_handlers
from tideapi.helpers.fastapi import initialise_fastapi_app
from fastapi.testclient import TestClient
from fastapi import Query

def assert_endpoint(endpoint:dict, path:str, methods:list|set, function:callable):
    assert endpoint['methods'] == methods
    assert endpoint['function'] is function
    assert endpoint['path'] == path

def assert_is_tide_api_response(json:dict) -> None:
    assert len(json) == 1 
    assert 'result' in json

def assert_endpoint_configuration(endpoints:dict, path:str, methods:list|set, function:callable, execute:bool=True, **kwargs):
    endpoint = endpoints[function.__name__]
    assert_endpoint(endpoint, path=path, methods=methods, function=function)
    expected_result = function(**kwargs) if execute else None
    return endpoint, expected_result

def endpoint_tester(endpoint: dict, status_code:int, expected_result:dict, replace:list[tuple[str,str]]=None, **kwargs):
    app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
    client = TestClient(app)

    path = endpoint['path']
    if replace:
        for target, value in replace:
            path = path.replace(f"{{{target}}}", value)
        
    response = client.get(path, **kwargs)
    assert response.status_code == status_code
    
    rjson = response.json()
    assert rjson == expected_result
    assert_is_tide_api_response(rjson)    
    return response

class TestTIDEEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch,
        sample_bundle_uuid,
        sample_bundle_name,
        sample_trace_uuid,
        sample_trace
    ):
        monkeypatch.setattr(request_handlers, "TRACES", {sample_trace_uuid: sample_trace})
        monkeypatch.setattr(request_handlers, "BUNDLES", {sample_bundle_uuid: sample_bundle_name})
        monkeypatch.setattr(request_handlers, "REGISTERED_BUNDLES", {sample_bundle_name: sample_trace_uuid})

    def test_trace_show_is_serialisable(self, sample_trace_uuid):
        json.dumps(show_trace(sample_trace_uuid))

    def test_trace_inspect_ref_is_serialisable(self, sample_trace_uuid, sample_ref):
        json.dumps(inspect_ref(sample_trace_uuid, sample_ref))

    def test_show_trace(self, endpoints, sample_trace_uuid):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=show_trace,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}',
        )

        endpoint_tester(endpoint=endpoint, status_code=200, expected_result=expected_result, replace=[('trace_id', sample_trace_uuid)])
    
    def test_inspect_ref(self, endpoints, sample_trace_uuid, sample_ref):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_ref,
            methods=['GET'],
            function=inspect_ref,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/ref',
        )

        endpoint_tester(endpoint=endpoint, status_code=200, expected_result=expected_result, replace=[('trace_id', sample_trace_uuid)], params={'ref':sample_ref})

    def test_inspect_exec(self, endpoints, sample_trace_uuid, sample_exec):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=inspect_exec,
            path='/traces/{trace_id}/exec',
            trace_id=sample_trace_uuid,
            ref=sample_exec
        )

        endpoint_tester(
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('trace_id', sample_trace_uuid)], 
            params={'ref':sample_exec}
        ),

    def test_inspect_actor(self, endpoints, sample_trace_uuid, sample_actor):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_actor,
            methods=['GET'],
            function=inspect_actor,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/actor',
        )

        endpoint_tester(
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
            replace=[('trace_id', sample_trace_uuid)],
            params={'ref': sample_actor},
        )


class TestAPIHelperEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(self, monkeypatch, sample_trace_uuid, sample_trace):
        monkeypatch.setattr(
            request_handlers,
            "TRACES",
            {sample_trace_uuid: sample_trace}
        )

    def test_redirect_to_docs(self, endpoints):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=redirect_to_docs,
            path='/',
        )

        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
        client = TestClient(app)
        response = client.get('/', follow_redirects=False)

        assert response.status_code == 307
        assert response.headers['location'] == 'docs/'
        
    def test_available_traces(self, endpoints):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=available_traces,
            path='/traces',
        )

        endpoint_tester(
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
        )

    def test_available_bundles(self, endpoints):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=available_bundles,
            path='/bundles',
        )

        endpoint_tester(
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
        )

    def test_bundle_name_by_trace_id(
        self, endpoints, sample_trace_uuid
    ):
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=bundle_name_by_trace_id,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/bundle_name',
        )

        endpoint_tester(
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
            replace=[('trace_id', sample_trace_uuid)],
        )
