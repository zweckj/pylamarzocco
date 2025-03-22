"""Testing models serialization and deserialization."""

from syrupy import SnapshotAssertion
from pylamarzocco.models.config import DeviceConfig

from .conftest import load_fixture

async def test_device_config(snapshot: SnapshotAssertion) -> None:
    """Test the config model serialization."""

    fixture = load_fixture("machine", "config_micra.json")
    device = DeviceConfig.from_dict(fixture)
    assert device.to_dict() == snapshot