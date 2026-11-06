
from tideapi.handlers import (
    show_trace,
    inspect_ref,
    inspect_exec,
    inspect_actor,
    register_trace,
    redirect_to_docs,
    available_traces,
    available_bundles,
    bundle_name_by_trace_id,
    ENDPOINT_HANDLERS,
    INSPECT_ENDPOINTS
)
import json
import pytest
import inspect 
from pathlib import Path
from typing import Any, Callable
import tideapi_core.request_handlers as request_handlers
from tideapi.helpers.fastapi import initialise_fastapi_app
from tideapi.exceptions import APILookupError, TraceLookupError, DataValidationError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from fastapi import Query

def assert_endpoint(endpoint:dict[str, Any], path:str, methods:list[str]|set[str], function:Callable[..., Any]) -> None:
    assert endpoint['methods'] == methods
    assert endpoint['function'] is function
    assert endpoint['path'] == path

def assert_is_tide_api_response(json:dict[str, Any]) -> None:
    assert len(json) == 1 
    assert 'result' in json

def assert_endpoint_configuration(endpoints:dict[str, dict[str, Any]], path:str, methods:list[str]|set[str], function:Callable[..., Any], execute:bool=True, **kwargs:Any) -> tuple[dict[str, Any], Any]:
    endpoint = endpoints[function.__name__]
    assert_endpoint(endpoint, path=path, methods=methods, function=function)
    expected_result = function(**kwargs) if execute else None
    return endpoint, expected_result

def endpoint_tester(method:str, endpoint:dict[str, Any], status_code:int, expected_result:dict[str, Any], replace:list[tuple[str,str]]|None=None, **kwargs:Any) -> tuple[TestClient, Any]:
    app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
    client = TestClient(app)

    path = endpoint['path']
    if replace:
        for target, value in replace:
            path = path.replace(f"{{{target}}}", value)

    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == status_code
    
    rjson = response.json()
    assert rjson == expected_result
    assert_is_tide_api_response(rjson)    
    return client, response

UNKNOWN_INT = 99999*9999*999*99*9
UNKNOWN_STR = 'unknown'

class TestTIDEEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_uuid: str,
        sample_bundle_name: str,
        sample_trace_uuid: str,
        sample_trace: Any
    ) -> None:
        monkeypatch.setattr(request_handlers, "TRACES", {sample_trace_uuid: sample_trace})
        monkeypatch.setattr(request_handlers, "BUNDLES", {sample_bundle_uuid: sample_bundle_name})
        monkeypatch.setattr(request_handlers, "REGISTERED_BUNDLES", {sample_bundle_name: sample_trace_uuid})

    def test_trace_show_is_serialisable(self, sample_trace_uuid: str) -> None:
        json.dumps(show_trace(sample_trace_uuid))

    def test_trace_inspect_ref_is_serialisable(self, sample_trace_uuid: str, sample_ref: str) -> None:
        json.dumps(inspect_ref(sample_trace_uuid, sample_ref))

    def test_show_trace(self, endpoints: dict[str, dict[str, Any]], sample_trace_uuid: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=show_trace,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('trace_id', sample_trace_uuid)]
        )

        with pytest.raises(APILookupError):
            show_trace(UNKNOWN_STR) 
    
    def test_inspect_ref(self, endpoints: dict[str, dict[str, Any]], sample_trace_uuid: str, sample_ref: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_ref,
            methods=['GET'],
            function=inspect_ref,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/ref',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('trace_id', sample_trace_uuid)], 
            params={'ref':sample_ref}
        )

        with pytest.raises(TraceLookupError):
            inspect_ref(trace_id=sample_trace_uuid, ref=UNKNOWN_STR)

    def test_inspect_exec(self, endpoints: dict[str, dict[str, Any]], sample_trace_uuid: str, sample_exec: int) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=inspect_exec,
            path='/traces/{trace_id}/exec',
            trace_id=sample_trace_uuid,
            ref=sample_exec
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('trace_id', sample_trace_uuid)], 
            params={'ref':sample_exec}
        )

        with pytest.raises(TraceLookupError):
            inspect_exec(sample_trace_uuid, ref=UNKNOWN_INT)

    def test_inspect_actor(self, endpoints: dict[str, dict[str, Any]], sample_trace_uuid: str, sample_actor: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_actor,
            methods=['GET'],
            function=inspect_actor,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/actor',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
            replace=[('trace_id', sample_trace_uuid)],
            params={'ref': sample_actor},
        )

        with pytest.raises(TraceLookupError):
            inspect_actor(trace_id=sample_trace_uuid, ref=UNKNOWN_STR)

        


class TestAPIHelperEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_uuid: str,
        sample_bundle_name: str,
        sample_trace_uuid: str,
        sample_trace: Any
    ) -> None:
        monkeypatch.setattr(request_handlers, "TRACES", {sample_trace_uuid: sample_trace})
        monkeypatch.setattr(request_handlers, "BUNDLES", {sample_bundle_uuid: sample_bundle_name})
        monkeypatch.setattr(request_handlers, "REGISTERED_BUNDLES", {sample_bundle_name: sample_trace_uuid})


    def test_redirect_to_docs(self, endpoints: dict[str, dict[str, Any]]) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=redirect_to_docs,
            path='/',
        )

        assert isinstance(expected_result, RedirectResponse) 
        assert expected_result.headers['location'] == 'docs/'
        assert expected_result.status_code == 307

        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
        client = TestClient(app)
        response = client.get('/', follow_redirects=False)

        assert response.status_code == 307
        assert response.headers['location'] == 'docs/'

    def test_available_traces(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=available_traces,
            path='/traces',
        )

        client, _ = endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
        )

        # Test no traces
        with monkeypatch.context() as m:
            m.setattr(request_handlers, "TRACES", {})
            assert client.get(url=f"/traces").status_code == 200

    def test_available_bundles(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> None:
        
        with monkeypatch.context() as m:
            bundle_path = tmp_path_factory.mktemp('bundles')
            (bundle_path / 'example.json').write_text('{}')
            
            m.setattr(request_handlers, 'ROOT', bundle_path)    
            

            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['GET'],
                function=available_bundles,
                path='/bundles',
            )
            
            client, _ = endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                expected_result=expected_result,
            )

        # Test no bundles
        with monkeypatch.context() as m:
            empty_path = tmp_path_factory.mktemp('empty')
            assert not any(empty_path.iterdir())
            m.setattr(request_handlers, "ROOT", empty_path)
            assert client.get(url=f"/bundles").status_code == 200

    def test_bundle_name_by_trace_id(
        self, endpoints: dict[str, dict[str, Any]], sample_trace_uuid: str
    ) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=bundle_name_by_trace_id,
            trace_id=sample_trace_uuid,
            path='/traces/{trace_id}/bundle_name',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
            replace=[('trace_id', sample_trace_uuid)],
        )

        with pytest.raises(APILookupError):
            bundle_name_by_trace_id(UNKNOWN_STR)
        

    @pytest.mark.parametrize("endpoint", INSPECT_ENDPOINTS)
    def test_inspect_endpoints_raises_api_error_on_unknown_trace(self, endpoint: dict[str, Any]) -> None:
        import inspect 
        
        function = endpoint['function']
        parameters = inspect.signature(function).parameters

        assert len(parameters) >= 1
        assert "trace_id" in parameters
    
        for name, parameter in parameters.items():
            if repr(parameter.annotation) == "<class 'str'>":
                if name == "trace_id":
                    continue
                ref = UNKNOWN_STR   
            elif repr(parameter.annotation) == "<class 'int'>":
                ref = UNKNOWN_INT   
            else:
                raise RuntimeError("Invalid input signature type for inspection endpoint")
        
        with pytest.raises(APILookupError):
            if len(parameters) == 1:
                function(trace_id=UNKNOWN_STR)
            else:
                function(trace_id=UNKNOWN_STR, ref=ref)

    @pytest.mark.parametrize("endpoint", [endpoint for endpoint in INSPECT_ENDPOINTS if len(inspect.signature(endpoint['function']).parameters) > 1])
    def test_inspect_endpoints_raises_trace_lookup_error_on_unknown_ref(self, sample_trace_uuid: str, endpoint: dict[str, Any]) -> None:
        
        
        function = endpoint['function']
        parameters = inspect.signature(function).parameters
        replace_params = dict()

        for name, parameter in parameters.items():
            if repr(parameter.annotation) == "<class 'str'>":
                if name == "trace_id":
                    replace_params[f'{parameter.name}'] = sample_trace_uuid
                else:
                    replace_params[f'{parameter.name}'] = UNKNOWN_STR   
            elif repr(parameter.annotation) == "<class 'int'>":
                replace_params[f'{parameter.name}'] = UNKNOWN_INT   
            else:
                raise RuntimeError("Invalid input signature type for inspection endpoint")
        
    
        with pytest.raises(TraceLookupError):
            function(**replace_params)
            
    def test_register_trace(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        with monkeypatch.context() as m:
            m.setattr(request_handlers.TIDE, "from_bundle", lambda self: {})
            m.setattr(request_handlers, "ROOT", tmp_path)
            (tmp_path / "example.json").write_text("{}")
            m.setattr(request_handlers, "BUNDLES", {})
            m.setattr(request_handlers, "TRACES", {})
            m.setattr(request_handlers, "REGISTERED_BUNDLES", {})

            TRACES = getattr(request_handlers, "TRACES")
            BUNDLES = getattr(request_handlers, "BUNDLES")
            REGISTERED_BUNDLES = getattr(request_handlers, "REGISTERED_BUNDLES")

            assert len(TRACES) == 0
            assert len(BUNDLES) == 0
            assert len(REGISTERED_BUNDLES) == 0 
            assert len(list(tmp_path.iterdir())) == 1
            
            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['POST'],
                function=register_trace,
                path='/register/trace/{bundle_name}',
                bundle_name="example.json",
            )
    
            endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                expected_result=expected_result,
                replace=[('bundle_name', 'example.json')],
            )

            assert len(BUNDLES) == 1 
            assert len(TRACES) == 1 
            assert len(REGISTERED_BUNDLES) == 1
            assert len(list(tmp_path.iterdir())) == 1  

            assert list(BUNDLES.values())[0] == 'example.json'
            assert 'example.json' in REGISTERED_BUNDLES  
            assert REGISTERED_BUNDLES['example.json'] == list(TRACES.keys())[0]
            assert list(TRACES.values())[0] == {
                'trace':{}, 
                'bundle_name':'example.json', 
                'bundle_id':list(BUNDLES.keys())[0]
            } 
            
            
            

            
            
            with pytest.raises(DataValidationError):
                register_trace('path/to/dir.json')

            with pytest.raises(APILookupError):
                register_trace('unknown.json')

            
