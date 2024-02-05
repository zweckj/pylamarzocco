"""Test utilities"""

from lmcloud import LaMarzoccoCloudClient, LaMarzoccoMachine, LaMarzoccoGrinder
from lmcloud.const import LaMarzoccoMachineModel, LaMarzoccoGrinderModel

MACHINE_SERIAL = "GS01234"
GRINDER_SERIAL = "G00000000000"


async def init_machine(
    cloud_client: LaMarzoccoCloudClient,
) -> LaMarzoccoMachine:
    """Get an initialized machine"""

    machine = await LaMarzoccoMachine.create(
        model=LaMarzoccoMachineModel.GS3_AV,
        serial_number=MACHINE_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
    )
    return machine


async def init_grinder(
    cloud_client: LaMarzoccoCloudClient,
) -> LaMarzoccoGrinder:
    """Get an initialized machine"""

    grinder = await LaMarzoccoGrinder.create(
        model=LaMarzoccoGrinderModel.PICO,
        serial_number=GRINDER_SERIAL,
        name="MyMachine",
        cloud_client=cloud_client,
    )
    return grinder
