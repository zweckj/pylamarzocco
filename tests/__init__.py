"""Test utilities"""

from lmcloud import LaMarzoccoCloudClient, LaMarzoccoMachine, LaMarzoccoGrinder
from lmcloud.client_bluetooth import LaMarzoccoBluetoothClient
from lmcloud.client_local import LaMarzoccoLocalClient
from lmcloud.const import MachineModel, GrinderModel

MACHINE_SERIAL = "GS01234"
GRINDER_SERIAL = "G00000000000"


async def init_machine(
    cloud_client: LaMarzoccoCloudClient | None = None,
    bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    local_client: LaMarzoccoLocalClient | None = None,
) -> LaMarzoccoMachine:
    """Get an initialized machine"""

    machine = await LaMarzoccoMachine.create(
        model=MachineModel.GS3_AV,
        serial_number=MACHINE_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
        local_client=local_client,
        bluetooth_client=bluetooth_client,
    )
    return machine


async def init_grinder(
    cloud_client: LaMarzoccoCloudClient,
) -> LaMarzoccoGrinder:
    """Get an initialized machine"""

    grinder = await LaMarzoccoGrinder.create(
        model=GrinderModel.PICO,
        serial_number=GRINDER_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
    )
    return grinder
