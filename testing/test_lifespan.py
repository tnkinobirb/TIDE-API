import pytest
import tideapi_core.request_handlers as request_handlers

from pathlib import Path
from fastapi.testclient import TestClient
from tideapi.exceptions import DataValidationError
from tideapi.persistence import TIDEAPIStore
from tideapi.fastapi import initialise_fastapi_app, lifespan

class TestLifespan:

    # TEST HELPERS
    @staticmethod
    def expect_init_state_result(registered: list[str] | None=None, failed: list[str] | None=None) -> dict[str, dict[str, list[str]]]:
        '''Format expected result from registered and failed lists'''
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

    def init_lifespan(self, monkeypatch: pytest.MonkeyPatch, bundle_dir: Path, include_dir:bool=False) -> TestClient:
        monkeypatch.setattr(request_handlers, 'BUNDLE_DIR', bundle_dir)
        monkeypatch.setattr(request_handlers, 'INCLUDE_BUNDLE_DIR_WHEN_LOADING', include_dir)

        app = initialise_fastapi_app(lifespan=lifespan)
        client = TestClient(app)
        return client

    # TESTS
    def test_lifespan_init(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tide_bundle: str,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:

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

            tmp_path = tmp_dir()
            valid_path = (tmp_path / 'example.json')
            valid_path.write_text(tide_bundle)
            invalid_path = (tmp_path / 'path_invalid.json')
            invalid_path.write_text('{}')

            with self.init_lifespan(m, tmp_path, include_dir=True) as client:
                assert client.app.state.init == self.expect_init_state_result(['*example.json'], ['store_invalid.json', 'path_invalid.json'])

        # TEST ROLLBACK OF LOCAL BUNDLES PERSISTED BEFORE FAILURE
        with monkeypatch.context() as m:
            m.setattr(request_handlers, 'TRACES', {})

            store = TIDEAPIStore(tmp_dir() / 'bundles.db')
            m.setattr(request_handlers, 'STORE', store)

            local_dir = tmp_dir()
            (local_dir / 'pass.json').write_text(tide_bundle)
            (local_dir / 'fail.json').write_text(tide_bundle)

            m.setattr(request_handlers, 'BUNDLE_DIR', local_dir)
            m.setattr(request_handlers, 'INCLUDE_BUNDLE_DIR_WHEN_LOADING', True)

            original_load = request_handlers.load_trace
            loaded = []

            def fail_on_second(bundle_name: str) -> dict[str, str]:
                if loaded:
                    assert store.exists(loaded[0])
                    assert loaded[0] in request_handlers.TRACES
                    raise DataValidationError("Simulated failure")

                result = original_load(bundle_name)
                loaded.append(bundle_name)
                return result

            m.setattr(request_handlers, 'load_trace', fail_on_second)

            with pytest.raises(DataValidationError):
                request_handlers.initialise_traces_from_bundles(ignore_invalid=False)

            assert len(loaded) == 1
            assert not request_handlers.TRACES
            assert not store.bundles()
