import pytest
from tideapi_core import request_handlers
from tideapi.exceptions import InvalidAPIStoreConfigurationError

@pytest.mark.parametrize(
    'backend, store_class',
    [('sqlite3', 'TIDEAPIStore'), ('postgresql', 'TIDEPSQLStore')]
)
def test_init_store_selects_backend(monkeypatch: pytest.MonkeyPatch, backend: str, store_class: str) -> None:
    store = object()
    calls = []

    def create_store():
        calls.append(store)
        return store

    monkeypatch.setattr(request_handlers, 'STORE', None)
    monkeypatch.setattr(request_handlers, 'STORE_BACKEND', backend)
    monkeypatch.setattr(request_handlers, store_class, create_store)

    assert request_handlers.init_store() is store
    assert request_handlers.init_store() is store
    assert calls == [store]

def test_init_store_denies_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(request_handlers, 'STORE', None)
    monkeypatch.setattr(request_handlers, 'STORE_BACKEND', 'invalid')

    with pytest.raises(InvalidAPIStoreConfigurationError):
        request_handlers.init_store()

    assert request_handlers.STORE is None
