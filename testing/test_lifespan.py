import pytest
import tideapi_core.request_handlers as request_handlers

from pathlib import Path
from fastapi.testclient import TestClient
from tideapi.persistence import TIDEAPIStore
from tideapi_core.lifespan import lifespan
from tideapi.helpers.fastapi import initialise_fastapi_app 

class TestLifespan:

    # TEST HELPERS
    @staticmethod
    def expect_init_state_result(registered: list[str]=None, failed: list[str]=None):
        '''Produce expected result from '''
        failed = [] if failed is None else failed
        registered = [] if registered is None else registered
        if not isinstance(registered, list) or not isinstance(failed, list):
            raise TypeError("Expected `registered` and `failed` inputs to both be lists") 
        
        return {
            'traces': {
                'registered': registered,
                'failed': failed
            }
        }

    def init_lifespan(self, monkeypatch: pytest.MonkeyPatch, dir: Path, include_dir:bool=False):
        monkeypatch.setattr(request_handlers, 'BUNDLE_DIR', dir)
        monkeypatch.setattr(request_handlers, 'INCLUDE_BUNDLE_DIR_AT_INIT', include_dir)

        app = initialise_fastapi_app(lifespan=lifespan)
        client = TestClient(app)
        return client

    # TESTS
    def test_lifespan_init(
        self, 
        bundle_dir: Path,
        monkeypatch: pytest.MonkeyPatch, 
        tide_bundle: str,
        tmp_path_factory: pytest.TempPathFactory,
    ):  
        
        # TEST EMPTY STORE AND PATH
        tmp_dir = lambda: tmp_path_factory.mktemp('tmp')
        with monkeypatch.context() as m:
            m.setattr(request_handlers, 'TRACES', {})
            m.setattr(request_handlers, 'STORE', TIDEAPIStore(tmp_dir() / 'bundles.db'))
            assert not request_handlers.STORE.bundles() 
            with self.init_lifespan(m, tmp_dir(), include_dir=True) as client:
                assert client.app.state.init == self.expect_init_state_result([], [])

        # TEST VALID BUNDLE FROM STORE ONLY
        with monkeypatch.context() as m:
            m.setattr(request_handlers, 'TRACES', {})
            m.setattr(request_handlers, 'STORE', TIDEAPIStore(tmp_dir() / 'bundles.db'))            

            dir_to_ignore = tmp_dir() 
            (dir_to_ignore /'path_example.json').write_text('{}')
            
            store = request_handlers.STORE
            assert not store.bundles()
            store.set('example.json', tide_bundle)
            
            with self.init_lifespan(m, dir_to_ignore, include_dir=False) as client:
                assert client.app.state.init == self.expect_init_state_result(['example.json'], [])
            

        # TEST ALREADY REGISTERED PLUS INVALID FROM STORE AND DIR
        with monkeypatch.context() as m:
            m.setattr(request_handlers, 'TRACES', {'example.json': tide_bundle})
            m.setattr(request_handlers, 'STORE', TIDEAPIStore(tmp_dir() / 'bundles.db'))
            request_handlers.STORE.set('store_invalid.json', '1234')
            dir = tmp_dir()
            valid_path = (dir / 'example.json')
            valid_path.write_text(tide_bundle)
            invalid_path = (dir / 'path_invalid.json')
            invalid_path.write_text('{}')
            
            with self.init_lifespan(m, dir, include_dir=True) as client:
                assert client.app.state.init == self.expect_init_state_result(['*example.json'], ['store_invalid.json', 'path_invalid.json'])
            invalid_path.unlink()


