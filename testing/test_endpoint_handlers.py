
from tideapi.handlers import (
    init_store,
    show_trace,
    inspect_ref,
    inspect_exec,
    inspect_actor,
    register_trace,
    register_bundle,
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
import sqlite3
from pathlib import Path
from typing import Any, Callable
import tideapi_core.request_handlers as request_handlers
from tideapi.persistence import TIDEAPIStore
from tideapi.helpers.fastapi import initialise_fastapi_app
from tideapi.exceptions import AlreadyRegisteredError, APILookupError, TraceLookupError, DataValidationError, APIStoreLookupError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from tide_tooling import Trace, TIDE
from tideapi.handlers import EXCEPTION_HANDLERS
from fastapi import Query

def assert_endpoint(endpoint:dict[str, Any], path:str, methods:list[str]|set[str], function:Callable[..., Any]) -> None:
    assert endpoint['methods'] == methods
    assert endpoint['function'] is function
    assert endpoint['path'] == path

def assert_is_tide_api_response(json:dict[str, Any]) -> None:
    json_len = len(json) 
    assert json_len == 1 
    assert 'result' in json

def assert_endpoint_configuration(endpoints:dict[str, dict[str, Any]], path:str, methods:list[str]|set[str], function:Callable[..., Any], execute:bool=True, **kwargs:Any) -> tuple[dict[str, Any], Any]:
    endpoint = endpoints[function.__name__]
    assert_endpoint(endpoint, path=path, methods=methods, function=function)
    expected_result = function(**kwargs) if execute else None
    return endpoint, expected_result

def endpoint_tester(method:str, endpoint:dict[str, Any], status_code:int, expected_result:dict[str, Any]|None=None, replace:list[tuple[str,str]]|None=None, compare_result:bool=True, **kwargs:Any) -> tuple[TestClient, Any]:
    app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint], EXCEPTION_HANDLERS=EXCEPTION_HANDLERS)
    client = TestClient(app, raise_server_exceptions=False)
    
    path = endpoint['path']
    if replace:
        for target, value in replace:
            path = path.replace(f"{{{target}}}", value)

    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == status_code
    
    rjson = response.json()
    assert_is_tide_api_response(rjson)    
    if compare_result:
        assert rjson == expected_result
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

        
class TestStoreHelpers:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_uuid: str,
        sample_bundle_name: str,
        sample_trace_uuid: str,
        sample_trace: Any,
        bundle_dir: Path,
        tmp_path: Path
        
    ) -> None:
        monkeypatch.setattr(request_handlers, "STORE", None)
        monkeypatch.setattr(request_handlers, "TRACES", {sample_trace_uuid: sample_trace})
        monkeypatch.setattr(request_handlers, "BUNDLES", {sample_bundle_uuid: sample_bundle_name})
        monkeypatch.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
        monkeypatch.setattr(request_handlers, "REGISTERED_BUNDLES", {sample_bundle_name: sample_trace_uuid})
        monkeypatch.setattr(request_handlers.TIDEAPIStore, "ROOT", tmp_path)

    def test_apistore_init(self, tide_bundle):
        assert getattr(request_handlers, "STORE") is None
        apistore_root = getattr(request_handlers.TIDEAPIStore, "ROOT")
        assert not list(apistore_root.iterdir())
        
        STORE = init_store()
        stores = list(apistore_root.iterdir())
        assert len(stores) == 1
        assert stores[0].name == "bundles.db"
        
        init_store().set("example.json", json.dumps(tide_bundle))
        bundle_json = json.loads(init_store().get(
            "example.json"
        ))

        trace = TIDE.from_bundle(json.loads(bundle_json))
        trace.show()

        # init_store re-uses already registered store
        assert init_store() is STORE 

    def test_register_bundle(self, monkeypatch:pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory, endpoints: dict[str, dict[str, Any]], bundle_dir, tide_bundle):
        def assert_rows():
            with sqlite3.connect(request_handlers.TIDEAPIStore.ROOT / "bundles.db") as conn:
                rows = conn.execute("SELECT * FROM bundles").fetchall()
            assert len(rows) == 1
            assert rows == [('example.json', tide_bundle)]

        with monkeypatch.context() as m:
            m.setattr(request_handlers, "STORE", None)
            m.setattr(request_handlers, "TRACES", {})
            m.setattr(request_handlers, "BUNDLES", {})
            m.setattr(request_handlers, "REGISTERED_BUNDLES", {})
            m.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
            m.setattr(request_handlers.TIDEAPIStore, "ROOT", tmp_path_factory.mktemp("123")) 
            assert request_handlers.STORE is None
            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['POST'],
                function=register_bundle,
                path='/register/bundle/{bundle_name}',
                bundle_name = "example.json" 
            )


        assert getattr(request_handlers, "STORE") is None
        apistore_root = getattr(request_handlers.TIDEAPIStore, "ROOT")
        print(list(apistore_root.iterdir()))
        assert not list(apistore_root.iterdir())

        endpoint_tester(
            status_code=200, 
            endpoint=endpoint, 
            method=endpoint['methods'][0],
            expected_result=expected_result, 
            replace=[('bundle_name', 'example.json')], 
            params={'replace': False}
        )

        endpoint_tester(
            status_code=409, 
            endpoint=endpoint, 
            compare_result=False, 
            method=endpoint['methods'][0],
            replace=[('bundle_name', 'example.json')], 
            params={'replace': False}
        )

        endpoint_tester(
            status_code=404, 
            endpoint=endpoint, 
            compare_result=False, 
            method=endpoint['methods'][0],
            replace=[('bundle_name', 'unknown.json')], 
            params={'replace': False}
        )

        endpoint_tester(
            status_code=418, 
            endpoint=endpoint, 
            compare_result=False, 
            method=endpoint['methods'][0],
            replace=[('bundle_name', 'invalid')], 
            params={'replace': False}
        )

        stores = list(apistore_root.iterdir())
        assert len(stores) == 1
        assert stores[0].name == "bundles.db"

        assert_rows()

        with pytest.raises(DataValidationError):
            register_bundle('../example.json')
        assert_rows()
                        

        with pytest.raises(AlreadyRegisteredError):
            register_bundle('example.json')
        assert_rows()
    

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
            response = client.get("/traces")
            
            assert response.status_code == 200
            assert response.json() == {"result": {}}


    def test_available_bundles(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> None:
        
        # Test no bundles
        with monkeypatch.context() as m:
            m.setattr(request_handlers, "STORE", None)
            test_path = tmp_path_factory.mktemp('test')
            m.setattr(request_handlers.TIDEAPIStore, "ROOT", test_path)

            store = init_store()

            assert not store.bundles() 
            store.set("example.json", "1234")
            bundles = store.bundles()
            assert len(bundles) == 1
            assert bundles[0] == "example.json"
            

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

        # Test bundles
        with monkeypatch.context() as m:
            m.setattr(request_handlers, "STORE", None)
            empty_path = tmp_path_factory.mktemp('empty')
            assert not any(empty_path.iterdir())
            m.setattr(TIDEAPIStore, "ROOT", empty_path)
            init_store()
            response = client.get("/bundles")

            assert response.status_code == 200
            assert response.json() == {"result": []}
        



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

    def test_tide_from_bundle_integration(self, tide_bundle):
        TIDE.from_bundle(json.loads(tide_bundle))

        # reject invalid
        with pytest.raises(TypeError):
            TIDE.from_bundle(json.loads('1234'))
        
        with pytest.raises(TypeError):
            TIDE.from_bundle(json.loads('{"invalid": "json"}'))


    def test_register_trace(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path_factory, tide_bundle:str) -> None:

        def init_context(m: pytest.MonkeyPatch, root):
            m.setattr(request_handlers, "BUNDLES", {})
            m.setattr(request_handlers, "TRACES", {})
            m.setattr(request_handlers, "REGISTERED_BUNDLES", {})
            m.setattr(request_handlers.TIDEAPIStore, "ROOT", root)
            m.setattr(request_handlers, "STORE", None)

            return init_store()


        def assert_context():
            TRACES = request_handlers.TRACES
            BUNDLES = request_handlers.BUNDLES
            REGISTERED_BUNDLES = request_handlers.REGISTERED_BUNDLES

            assert len(TRACES) == 1
            assert len(BUNDLES) == 1
            assert len(REGISTERED_BUNDLES) == 1
            assert len(request_handlers.STORE.bundles()) == 1  

            trace_id = list(TRACES.keys())[0]
            assert list(BUNDLES.values())[0] == 'example.json'
            assert REGISTERED_BUNDLES['example.json'] == trace_id
            
            assert trace_id in TRACES
            assert 'example.json' in REGISTERED_BUNDLES
            assert isinstance(TRACES[trace_id]['trace'], Trace)
            assert TRACES[trace_id]['bundle_name'] == 'example.json' 
            assert TRACES[trace_id]['bundle_id'] == list(BUNDLES.keys())[0]

        def assert_empty_context():
            assert len(request_handlers.TRACES) == 0
            assert len(request_handlers.BUNDLES) == 0
            assert len(request_handlers.REGISTERED_BUNDLES) == 0

        
        with monkeypatch.context() as m:
            test_dir = tmp_path_factory.mktemp("test")
            store = init_context(m, test_dir)

            assert_empty_context()

            # Test malformed trace
            bundles = tmp_path_factory.mktemp("bundles")
            m.setattr(request_handlers, 'BUNDLE_PATH', bundles)

            malformed = json.loads(tide_bundle)
            malformed["manifest"]["run"]["trace"] = {}

            (bundles / "invalid.json").write_text(
                json.dumps(malformed),
                encoding="utf-8",
            )
            
            with pytest.raises(DataValidationError):
                register_bundle("invalid.json")

            assert init_store().bundles() == []

            # Test missing bundle
            assert_empty_context()
            with pytest.raises(APIStoreLookupError):
                register_trace('unknown.json')
            
            # Test invalid input
            assert_empty_context()
            with pytest.raises(DataValidationError):
                register_trace('path/to/dir.json')

            store.set("example.json", '{"fake_bundle": "lol"}')
            assert len(store.bundles()) == 1

            assert_empty_context()
            with pytest.raises(TypeError):
                register_trace("example.json")
            
            assert_empty_context()
        
        with monkeypatch.context() as m:
            store = init_context(m, tmp_path_factory.mktemp("temp"))
            store.set("example.json", tide_bundle)
            assert len(store.bundles()) == 1
            

            
            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['POST'],
                function=register_trace,
                path='/register/trace/{bundle_name}',
                bundle_name="example.json",
            )
            trace_id = list(request_handlers.TRACES.keys())[0]

            # duplicate call returns same trace_id and does not change structure
            result = register_trace('example.json')
            assert_context()
            duplicate_id = list(result.values())[0]
            assert trace_id == duplicate_id
            assert result == expected_result

        with monkeypatch.context() as m:
            store = init_context(m, tmp_path_factory.mktemp("store"))
            store.set("example.json", tide_bundle)
            assert len(store.bundles()) == 1

            endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                replace=[('bundle_name', 'example.json')],
                compare_result=False,
            )
            
            assert_context()
            
            with pytest.raises(DataValidationError):
                register_trace('path/to/dir.json')
            assert_context()
            
            with pytest.raises(APIStoreLookupError):
                register_trace('unknown.json')
            assert_context()

        with monkeypatch.context() as m:
            store = init_context(m, tmp_path_factory.mktemp("store"))
            
                            


        
        
