"""Test utilities"""

from lmcloud import LaMarzoccoCloudClient, LaMarzoccoMachine
from lmcloud.const import LaMarzoccoMachineModel


async def init_machine(
    cloud_client: LaMarzoccoCloudClient,
) -> LaMarzoccoMachine:
    """Get an initialized machine"""
    LaMarzoccoMachine.cloud_client = cloud_client

    machine = await LaMarzoccoMachine.create(
        model=LaMarzoccoMachineModel.GS3_AV,
        serial_number="123456",
        name="MyMachine",
    )
    return machine
