
import json
import pytest
import inspect 
import sqlite3

from pathlib import Path
from typing import Any, Callable
from fastapi.testclient import TestClient
from fastapi.responses import RedirectResponse

import tideapi_core.request_handlers as request_handlers
from tide_tooling import Trace, TIDE
from tideapi.handlers import EXCEPTION_HANDLERS
from tideapi.persistence import TIDEAPIStore
from tideapi.helpers.fastapi import initialise_fastapi_app
from tideapi.handlers import (
    init_store,
    show_trace,
    inspect_ref,
    inspect_exec,
    inspect_actor,
    get_init_meta,
    load_trace,
    persist_bundle,
    redirect_to_docs,
    local_bundles,
    loaded_traces,
    persisted_bundles,
    TIDE_INSPECT_ENDPOINTS
)
from tideapi.exceptions import (
    APILookupError, 
    TraceLookupError, 
    APIStoreLookupError,
    DataValidationError, 
    AlreadyRegisteredError, 
)

UNKNOWN_STR = 'unknown'
UNKNOWN_INT = 99999*9999*999*99*9

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

def endpoint_tester(method:str, endpoint:dict[str, Any], status_code:int, expected_result:dict[str, Any]|None=None, replace:list[tuple[str,str]]|None=None, compare_result:bool=True, use_client:TestClient|None=None, **kwargs:Any) -> tuple[TestClient, Any]:
    if use_client is None:
        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint], EXCEPTION_HANDLERS=EXCEPTION_HANDLERS)
        client = TestClient(app, raise_server_exceptions=False)
    else:
        if not isinstance(use_client, TestClient):
            raise RuntimeError(f"endpoint_test(use_client=...) must be a fastapi.testclient.TestClient, was a {type(use_client)}")
        client = use_client
    
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

class TestTIDEEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_name: str,
        sample_trace: Any
    ) -> None:
        monkeypatch.setattr(request_handlers, "TRACES", {sample_bundle_name: sample_trace})

    def test_trace_show_is_serialisable(self, sample_bundle_name: str) -> None:
        json.dumps(show_trace(sample_bundle_name))

    def test_trace_inspect_ref_is_serialisable(self, sample_bundle_name: str, sample_ref: str) -> None:
        json.dumps(inspect_ref(sample_bundle_name, sample_ref))

    def test_show_trace(self, endpoints: dict[str, dict[str, Any]], sample_bundle_name: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=show_trace,
            bundle_name=sample_bundle_name,
            path='/traces/{bundle_name}',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('bundle_name', sample_bundle_name)]
        )

        with pytest.raises(APILookupError):
            show_trace(UNKNOWN_STR) 
    
    def test_inspect_ref(self, endpoints: dict[str, dict[str, Any]], sample_bundle_name: str, sample_ref: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_ref,
            methods=['GET'],
            function=inspect_ref,
            bundle_name=sample_bundle_name,
            path='/traces/{bundle_name}/ref',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('bundle_name', sample_bundle_name)], 
            params={'ref':sample_ref}
        )

        with pytest.raises(TraceLookupError):
            inspect_ref(bundle_name=sample_bundle_name, ref=UNKNOWN_STR)

    def test_inspect_exec(self, endpoints: dict[str, dict[str, Any]], sample_bundle_name: str, sample_exec: int) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=inspect_exec,
            path='/traces/{bundle_name}/exec',
            bundle_name=sample_bundle_name,
            ref=sample_exec
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint, 
            status_code=200, 
            expected_result=expected_result, 
            replace=[('bundle_name', sample_bundle_name)], 
            params={'ref':sample_exec}
        )

        with pytest.raises(TraceLookupError):
            inspect_exec(sample_bundle_name, ref=UNKNOWN_INT)

    def test_inspect_actor(self, endpoints: dict[str, dict[str, Any]], sample_bundle_name: str, sample_actor: str) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            ref=sample_actor,
            methods=['GET'],
            function=inspect_actor,
            bundle_name=sample_bundle_name,
            path='/traces/{bundle_name}/actor',
        )

        endpoint_tester(
            method=endpoint['methods'][0],
            endpoint=endpoint,
            status_code=200,
            expected_result=expected_result,
            replace=[('bundle_name', sample_bundle_name)],
            params={'ref': sample_actor},
        )

        with pytest.raises(TraceLookupError):
            inspect_actor(bundle_name=sample_bundle_name, ref=UNKNOWN_STR)

        
class TestStoreHelpers:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_name: str,
        sample_trace: Any,
        bundle_dir: Path,
        tmp_path: Path
        
    ) -> None:
        monkeypatch.setattr(request_handlers, "STORE", None)
        monkeypatch.setattr(request_handlers, "TRACES", {sample_bundle_name: sample_trace})
        monkeypatch.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
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

        # store re-uses already registered store
        assert init_store() is STORE 

    def test_persist_bundle(self, monkeypatch:pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory, endpoints: dict[str, dict[str, Any]], bundle_dir, tide_bundle):
        def assert_rows():
            with sqlite3.connect(request_handlers.TIDEAPIStore.ROOT / "bundles.db") as conn:
                rows = conn.execute("SELECT * FROM bundles").fetchall()
            assert len(rows) == 1
            assert rows == [('example.json', tide_bundle)]

        with monkeypatch.context() as m:
            m.setattr(request_handlers, "STORE", None)
            m.setattr(request_handlers, "TRACES", {})
            m.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
            m.setattr(request_handlers.TIDEAPIStore, "ROOT", tmp_path_factory.mktemp("123")) 
            assert request_handlers.STORE is None
            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['POST'],
                function=persist_bundle,
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
            status_code=400, 
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
            persist_bundle('../example.json')
        assert_rows()
                        

        with pytest.raises(AlreadyRegisteredError):
            persist_bundle('example.json')
        assert_rows()
    

class TestAPIHelperEndpoints:

    @pytest.fixture(autouse=True)
    def setup_monkeypatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sample_bundle_name: str,
        sample_trace: Any
    ) -> None:
        monkeypatch.setattr(request_handlers, "TRACES", {sample_bundle_name: sample_trace})

    def test_redirect_to_docs(self, endpoints: dict[str, dict[str, Any]]) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=redirect_to_docs,
            path='/',
        )

        assert isinstance(expected_result, RedirectResponse) 
        assert expected_result.headers['location'] == '/docs'
        assert expected_result.status_code == 307

        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
        client = TestClient(app)
        response = client.get('/', follow_redirects=False)

        assert response.status_code == 307
        assert response.headers['location'] == '/docs'

    def test_local_bundles(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, bundle_dir: Path) -> None:
        with monkeypatch.context() as m:
            m.setattr(request_handlers, "BUNDLE_PATH", bundle_dir)
            (bundle_dir / "invalid.txt").write_text("invalid", encoding="utf-8")

            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['GET'],
                function=local_bundles,
                path='/local/bundles',
            )

            client, _ = endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                expected_result=expected_result,
            )

            assert expected_result == {"result": ["*example.json"]}

            m.setattr(request_handlers, "TRACES", {})
            response = client.get("/local/bundles")

            assert response.status_code == 200
            assert response.json() == {"result": ["example.json"]}

    def test_loaded_traces(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
        endpoint, expected_result = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=loaded_traces,
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
            assert response.json() == {"result": []}

    def test_persisted_bundles(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> None:
        
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
                function=persisted_bundles,
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

    @pytest.mark.parametrize("endpoint", TIDE_INSPECT_ENDPOINTS)
    def test_inspect_endpoints_raises_api_error_on_unknown_trace(self, endpoint: dict[str, Any]) -> None:
        import inspect 
        
        function = endpoint['function']
        parameters = inspect.signature(function).parameters

        assert len(parameters) >= 1
        assert "bundle_name" in parameters
    
        for name, parameter in parameters.items():
            if repr(parameter.annotation) == "<class 'str'>":
                if name == "bundle_name":
                    continue
                ref = UNKNOWN_STR   
            elif repr(parameter.annotation) == "<class 'int'>":
                ref = UNKNOWN_INT   
            else:
                raise RuntimeError("Invalid input signature type for inspection endpoint")
        
        with pytest.raises(APILookupError):
            if len(parameters) == 1:
                function(bundle_name=UNKNOWN_STR)
            else:
                function(bundle_name=UNKNOWN_STR, ref=ref)

    @pytest.mark.parametrize("endpoint", [endpoint for endpoint in TIDE_INSPECT_ENDPOINTS if len(inspect.signature(endpoint['function']).parameters) > 1])
    def test_inspect_endpoints_raises_trace_lookup_error_on_unknown_ref(self, sample_bundle_name: str, endpoint: dict[str, Any]) -> None:
        
        
        function = endpoint['function']
        parameters = inspect.signature(function).parameters
        replace_params = dict()

        for name, parameter in parameters.items():
            if repr(parameter.annotation) == "<class 'str'>":
                if name == "bundle_name":
                    replace_params[f'{parameter.name}'] = sample_bundle_name
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


    def test_load_trace(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory, tide_bundle:str, bundle_dir:Path) -> None:

        def init_context(m: pytest.MonkeyPatch, root):
            m.setattr(request_handlers, "TRACES", {})
            m.setattr(request_handlers.TIDEAPIStore, "ROOT", root)
            m.setattr(request_handlers, "STORE", None)

            return init_store()


        def assert_context():
            TRACES = request_handlers.TRACES

            assert len(TRACES) == 1
            assert len(request_handlers.STORE.bundles()) == 1  

            bundle_name = list(TRACES.keys())[0]
            
            assert bundle_name in TRACES
            assert isinstance(TRACES[bundle_name], Trace)

        def assert_empty_context():
            assert len(request_handlers.TRACES) == 0

        
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
                persist_bundle("invalid.json")

            assert init_store().bundles() == []

            # Test missing bundle
            assert_empty_context()
            with pytest.raises(APILookupError):
                load_trace('unknown.json')
            
            # Test invalid input
            assert_empty_context()
            with pytest.raises(DataValidationError):
                load_trace('path/to/dir.json')

            store.set("example.json", '{"fake_bundle": "lol"}')
            assert len(store.bundles()) == 1

            assert_empty_context()
            with pytest.raises(TypeError):
                load_trace("example.json")
            
            assert_empty_context()
        
        with monkeypatch.context() as m:
            store = init_context(m, tmp_path_factory.mktemp("temp"))
            store.set("example.json", tide_bundle)
            assert len(store.bundles()) == 1
        
            endpoint, expected_result = assert_endpoint_configuration(
                endpoints,
                methods=['POST'],
                function=load_trace,
                path='/register/trace/{bundle_name}',
                bundle_name="example.json",
            )
            bundle_name = list(request_handlers.TRACES.keys())[0]

            # duplicate call returns same bundle_name and does not change structure
            result = load_trace('example.json')
            assert_context()
            duplicate_name = list(result.values())[0]
            assert bundle_name == duplicate_name
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
                load_trace('path/to/dir.json')
            assert_context()
            
            with pytest.raises(APILookupError):
                load_trace('unknown.json')
            assert_context()

        with monkeypatch.context() as m:
            m.setattr(request_handlers, 'BUNDLE_PATH', bundle_dir)
            store = init_context(m, tmp_path_factory.mktemp("auto-reg"))
            assert len(store.bundles()) == 0

            assert list(file.name for file in bundle_dir.iterdir()) == ['example.json']
            
            endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                replace=[('bundle_name', 'example.json')],
                compare_result=False,
            )
            
            assert_context()
            
            with pytest.raises(DataValidationError):
                load_trace('path/to/dir.json')
            assert_context()
            
            with pytest.raises(APILookupError):
                load_trace('unknown.json')
            assert_context()

    def test_get_init_meta(self, endpoints: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch, api_db:pytest.TempPathFactory) -> None:
        def test_endpoint_with_client(client: TestClient, result):
            expected_result = {"result": result} 
            endpoint_tester(
                method=endpoint['methods'][0],
                endpoint=endpoint,
                status_code=200,
                expected_result=expected_result,
                compare_result=True,
                use_client=client,
            )

        monkeypatch.setattr(request_handlers, "STORE", api_db)
        endpoint, _ = assert_endpoint_configuration(
            endpoints,
            methods=['GET'],
            function=get_init_meta,
            path='/meta/init',
            execute=False
        )
        
        app = initialise_fastapi_app(ENDPOINT_HANDLERS=[endpoint])
        client = TestClient(app)
        test_endpoint_with_client(client, {})

        client.app.state.init = {}
        test_endpoint_with_client(client, dict(client.app.state.init))
        
        client.app.state.init = {'succeeded': ['example'], 'failed': []}
        test_endpoint_with_client(client, dict(client.app.state.init))

        client.app.state.init = [213123231]
        test_endpoint_with_client(client, list(client.app.state.init))
        
        
        
        
        
        
