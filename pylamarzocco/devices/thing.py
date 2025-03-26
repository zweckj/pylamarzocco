"""Base class for all La Marzocco IoT devices."""

from pylamarzocco.models import Thing

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoThing:
    """Base class for all La Marzocco devices"""

    cloud_client: LaMarzoccoCloudClient | None

    def __init__(
        self,
        serial_number: str,
        name: str,
        cloud_client: LaMarzoccoCloudClient | None = None,
        bluetooth_client: LaMarzoccoBluetoothClient | None = None,
    ) -> None:
        """Initializes a new LaMarzoccoMachine instance"""

    async def get_statistics(self) -> None:
        """Update the statistics"""

        raw_statistics = await self.cloud_client.get_statistics(self.serial_number)
        self.parse_statistics(raw_statistics)

    async def get_firmware(self) -> None:
        """Update the firmware"""

        self.firmware = await self.cloud_client.get_firmware(self.serial_number)

    @abstractmethod
    async def update_firmware(self) -> None:
        """Update firmware"""

    async def _bluetooth_command_with_cloud_fallback(
        self,
        command: str,
        **kwargs,
    ) -> bool:
        """Send a command to the machine via Bluetooth, falling back to cloud if necessary."""

        # First, try with bluetooth
        if self._bluetooth_client is not None:
            func = getattr(self._bluetooth_client, command)
            try:
                _LOGGER.debug(
                    "Sending command %s over bluetooth with params %s",
                    command,
                    str(kwargs),
                )
                await func(**kwargs)
            except (BleakError, BluetoothConnectionFailed) as exc:
                msg = "Could not send command to bluetooth device, even though initalized."

                if self._cloud_client is None:
                    _LOGGER.error(
                        "%s Cloud client not initialized, cannot fallback. Full error %s",
                        msg,
                        exc,
                    )
                    return False

                _LOGGER.warning("%s Falling back to cloud", msg)
                _LOGGER.debug("Full error: %s", exc)
            else:
                return True

        # no bluetooth or failed, try with cloud
        if self._cloud_client is not None:
            _LOGGER.debug(
                "Sending command %s over cloud with params %s",
                command,
                str(kwargs),
            )
            func = getattr(self._cloud_client, command)
            kwargs["serial_number"] = self.serial_number
            if await func(**kwargs):
                return True
        return False

    def __str__(self) -> str:
        config = dict(vars(self.config).items())
        return str(config)
