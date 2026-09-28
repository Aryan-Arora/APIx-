import pytest

from apix.adapters.cleartrip import ClearTripAdapter
from apix.adapters.easemytrip import EaseMyTripAdapter
from apix.adapters.indigo import IndiGoAdapter
from apix.adapters.ixigo import IxigoAdapter


@pytest.mark.parametrize("adapter_cls,expected_name,expected_type", [
    (IxigoAdapter, "ixigo", "ota"),
    (EaseMyTripAdapter, "easemytrip", "ota"),
    (ClearTripAdapter, "cleartrip", "ota"),
    (IndiGoAdapter, "indigo", "airline"),
])
def test_stub_adapter_identity(adapter_cls, expected_name, expected_type):
    a = adapter_cls()
    assert a.name == expected_name
    assert a.source_type == expected_type


@pytest.mark.parametrize("adapter_cls", [IxigoAdapter, EaseMyTripAdapter, ClearTripAdapter, IndiGoAdapter])
def test_stub_adapter_raises_not_implemented(adapter_cls):
    a = adapter_cls()
    with pytest.raises(NotImplementedError):
        a.fetch({"route_id": "BOM-DEL", "origin": "BOM", "dest": "DEL"}, None)
