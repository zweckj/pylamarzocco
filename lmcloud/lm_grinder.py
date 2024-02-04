"""La Marzocco grinder module."""

from typing import Any

from .const import LaMarzoccoGrinderModel
from .lm_iot_device import LaMarzoccoIoTDevice, LaMarzoccoStatistics


class LaMarzoccoGrinder(LaMarzoccoIoTDevice):
    """Class for La Marzocco grinder"""

    model: LaMarzoccoGrinderModel
    bell_opened: bool
    stand_by_time: int
    led_enabled: bool

    def parse_config(self, raw_config: dict[str, Any]) -> None:
        """Parse the config object."""
        raise NotImplementedError

    def parse_statistics(
        self, raw_statistics: list[dict[str, Any]]
    ) -> LaMarzoccoStatistics:
        """Parse the statistics object."""
        raise NotImplementedError
