from tideapi.handlers import register_bundle
from tideapi_core import request_handlers
from threading import Thread, Barrier, Event
import pytest

class TestFunctionLocks:
    @pytest.fixture(autouse=True)
    def setup_monkeypatch(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bundle_dir: Path): 
        monkeypatch.setattr(request_handlers.TIDEAPIStore, 'ROOT', tmp_path)
        monkeypatch.setattr(request_handlers, 'BUNDLE_PATH', bundle_dir)

    def test_register_bundle(self):
            barrier = Barrier(2)
            def worker():
                barrier.wait()
                register_bundle('example.json')
                print('proceeding')
            a = Thread(target=worker)
            b = Thread(target=worker)
            a.start()
            b.start()
            a.join()
            with pytest.raises(AlreadyRegisteredError):
                 b.join()

