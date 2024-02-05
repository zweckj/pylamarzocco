"""La Marzocco grinder module."""

from __future__ import annotations

from typing import Any

from .lm_iot_device import LaMarzoccoIoTDevice, LaMarzoccoStatistics
from .client_cloud import LaMarzoccoCloudClient
from .client_local import LaMarzoccoLocalClient


class LaMarzoccoGrinder(LaMarzoccoIoTDevice):
    """Class for La Marzocco grinder"""

    def __init__(
        self,
        model: str,
        serial_number: str,
        name: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        local_client: LaMarzoccoLocalClient | None = None,
    ) -> None:
        """Initializes a new LaMarzoccoGrinder instance."""
        super().__init__(model, serial_number, name, cloud_client, local_client)
        self.bell_opened = False
        self.stand_by_time: int = 5
        self.led_enabled = False

    @classmethod
    async def create(cls, *args, **kwargs) -> LaMarzoccoGrinder:
        """Create a new LaMarzoccoGrinder instance."""
        self = LaMarzoccoGrinder(*args, **kwargs)
        await self.get_config()
        return self

    def parse_config(self, raw_config: dict[str, Any]) -> None:
        """Parse the config object."""
        super().parse_config(raw_config)
        self.turned_on = raw_config["machineMode"] == "StandBy"
        self.led_enabled = raw_config["baristaLed"]
        self.bell_opened = raw_config["bellOpened"]
        self.stand_by_time = raw_config["standByTime"]
        for dose in raw_config["doses"]:
            self.doses[ord(dose["doseIndex"][-1]) - 64] = dose["target"]

    def parse_statistics(
        self, raw_statistics: list[dict[str, Any]]
    ) -> LaMarzoccoStatistics:
        """Parse the statistics object."""
        raise NotImplementedError
