"""La Marzocco Cloud API Client."""

from __future__ import annotations

import asyncio
import logging
from http import HTTPMethod
from typing import Any

from authlib.common.errors import AuthlibHTTPError  # type: ignore[import]
from authlib.integrations.base_client.errors import OAuthError  # type: ignore[import]
from authlib.integrations.httpx_client import AsyncOAuth2Client  # type: ignore[import]
from httpx import RequestError

from .const import (
    CUSTOMER_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    GW_AWS_PROXY_BASE_URL,
    GW_MACHINE_BASE_URL,
    TOKEN_URL,
    BoilerType,
    FirmwareType,
    PhysicalKey,
    PrebrewMode,
    SmartStandbyMode,
)
from .exceptions import AuthFail, RequestNotSuccessful
from .models import LaMarzoccoFirmware, LaMarzoccoDeviceInfo

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoCloudClient:
    """La Marzocco Cloud Client."""

    def __init__(self, username: str, password: str):
        self._oauth_client: AsyncOAuth2Client | None = None
        self.username = username
        self.password = password

    async def _connect(self) -> AsyncOAuth2Client:
        """Establish connection by building the OAuth client and requesting the token"""

        client = AsyncOAuth2Client(
            client_id=DEFAULT_CLIENT_ID,
            client_secret=DEFAULT_CLIENT_SECRET,
            token_endpoint=TOKEN_URL,
        )

        try:
            await client.fetch_token(
                url=TOKEN_URL,
                username=self.username,
                password=self.password,
            )
        except OAuthError as exc:
            raise AuthFail(f"Authorization failure: {exc}") from exc
        except AuthlibHTTPError as exc:
            raise RequestNotSuccessful(
                f"Exception during token request: {exc}"
            ) from exc

        return client

    async def _rest_api_call(
        self, url: str, method: HTTPMethod, data: dict[str, Any] | None = None
    ) -> Any:
        """Wrapper for the API call."""

        if self._oauth_client is None:
            self._oauth_client = await self._connect()

        # make sure oauth token is still valid
        if self._oauth_client.token.is_expired():
            await self._oauth_client.refresh_token(TOKEN_URL)

        try:
            response = await self._oauth_client.request(method, url, json=data)
        except RequestError as ecx:
            raise RequestNotSuccessful(
                f"Error during HTTP request. Request to endpoint {url} failed with error: {ecx}"
            ) from ecx

        # ensure status code indicates success
        if response.is_success:
            return response.json()["data"]

        raise RequestNotSuccessful(
            f"Request to endpoint {response.url} failed with status code {response.status_code}"
        )

    async def get_customer_fleet(self) -> dict[str, LaMarzoccoDeviceInfo]:
        """Get basic machine info from the customer endpoint."""

        machine_info: dict[str, LaMarzoccoDeviceInfo] = {}

        data = await self._rest_api_call(url=CUSTOMER_URL, method=HTTPMethod.GET)
        fleet = data.get("fleet", [])
        for machine_data in fleet:
            key = machine_data.get("communicationKey")
            name = machine_data.get("name")

            machine = machine_data.get("machine", {})
            serial_number = machine.get("serialNumber")
            model_name = machine.get("model", {}).get("name")

            machine_info[serial_number] = LaMarzoccoDeviceInfo(
                serial_number=serial_number,
                name=name,
                communication_key=key,
                model=model_name,
            )

        return machine_info

    async def get_config(self, serial_number: str) -> dict[str, Any]:
        """Get configuration from cloud"""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/configuration"
        return await self._rest_api_call(url=url, method=HTTPMethod.GET)

    async def set_power(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Turn power of machine on or off"""

        mode = "BrewingMode" if enabled else "StandBy"

        data = {"status": mode}
        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/status"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def set_steam(
        self,
        serial_number: str,
        enabled: bool,
    ) -> bool:
        """Turn Steamboiler on or off"""

        data = {
            "identifier": BoilerType.STEAM.value,
            "state": enabled,
        }
        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-boiler"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def set_temp(
        self,
        serial_number: str,
        boiler: BoilerType,
        temperature: float,
    ) -> bool:
        """Set boiler temperature (in Celsius)."""

        data = {"identifier": boiler.value, "value": temperature}
        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/target-boiler"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True

        return False

    async def set_prebrew_mode(
        self,
        serial_number: str,
        mode: PrebrewMode,
    ) -> bool:
        """Enable/Disable Pre-Brew or Pre-Infusion (mutually exclusive)."""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-preinfusion"
        data = {"mode": mode.value}
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def configure_pre_brew_infusion_time(
        self,
        serial_number: str,
        on_time: float,
        off_time: float,
        key: PhysicalKey,
    ) -> bool:
        """Set Pre-Brew details. Also used for preinfusion (prebrewOnTime=0, prebrewOnTime=ms)."""

        on_time = round(on_time, 1) * 1000
        off_time = round(off_time, 1) * 1000
        button = f"Dose{key.name}"

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/setting-preinfusion"
        data = {
            "button": button,
            "group": "Group1",
            "holdTimeMs": int(off_time),
            "wetTimeMs": int(on_time),
        }
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def enable_plumbin(
        self,
        serial_number: str,
        enable: bool,
    ) -> bool:
        """Enable or disable plumbin mode"""

        data = {"enable": enable}
        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-plumbin"
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def set_dose(
        self,
        serial_number: str,
        key: PhysicalKey,
        value: int,
    ) -> bool:
        """Set the value for a dose"""

        dose_index = f"Dose{key.name}"

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/dose"
        data = {
            "dose_index": dose_index,
            "dose_type": "PulsesType",
            "group": "Group1",
            "value": value,
        }

        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def set_dose_hot_water(
        self,
        serial_number: str,
        value: int,
    ) -> bool:
        """Set the value for the hot water dose"""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/dose-tea"
        data = {"dose_index": "DoseA", "value": value}
        response = await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    # async def set_schedule(
    #     self,
    #     serial_number: str,
    #     schedule: LaMarzoccoCloudSchedule,
    # ) -> bool:
    #     """Set auto-on/off schedule"""

    #     url = f"{GW_MACHINE_BASE_URL}/{serial_number}/scheduling"
    #     response = await self._rest_api_call(
    #         url=url, method=HTTPMethod.POST, data=dict(schedule)
    #     )
    #     if await self._check_cloud_command_status(serial_number, response):
    #         return True
    #     return False

    async def set_smart_standby(
        self, serial_number: str, enabled: bool, minutes: int, mode: SmartStandbyMode
    ) -> bool:
        """Set the smart standby configuration"""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/smart-standby"
        response = await self._rest_api_call(
            url=url,
            method=HTTPMethod.POST,
            data={
                "enabled": enabled,
                "minutes": minutes,
                "mode": mode.value,
            },
        )
        if await self._check_cloud_command_status(serial_number, response):
            return True
        return False

    async def start_backflush(self, serial_number: str) -> None:
        """Send command to start backflushing"""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/enable-backflush"
        data = {"enable": True}
        await self._rest_api_call(url=url, method=HTTPMethod.POST, data=data)

    async def token_command(self, serial_number: str) -> None:
        """Send token request command to cloud. This is needed when the local API returns 403."""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/token-request"
        response = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        await self._check_cloud_command_status(serial_number, response)

    async def _check_cloud_command_status(
        self,
        serial_number: str,
        command_response: dict[str, Any],
    ) -> bool:
        """Check the status of a cloud command"""

        if command_id := command_response.get("commandId"):
            _LOGGER.debug("Checking status of command %s", command_id)
            url = f"{GW_AWS_PROXY_BASE_URL}/{serial_number}/commands/{command_id}"
            counter = 0
            status = "PENDING"
            while status == "PENDING" and counter < 5:
                await asyncio.sleep(1)  # give a second to settle in
                response = await self._rest_api_call(url=url, method=HTTPMethod.GET)
                if response is None:
                    return False
                status = response.get("status", "PENDING")
                if status == "PENDING":
                    _LOGGER.debug("Command %s still pending", command_id)
                    counter += 1
                    continue
                if status == "COMPLETED":
                    response_payload = response.get("responsePayload")
                    if response_payload is None:
                        return False
                    _LOGGER.debug("Command %s completed", command_id)
                    return response_payload.get("status") == "success"
        _LOGGER.debug("Command %s failed", command_id)
        return False

    async def get_firmware(
        self,
        serial_number: str,
    ) -> dict[FirmwareType, LaMarzoccoFirmware]:
        """Get Firmware details."""

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/firmware/"
        result = await self._rest_api_call(url=url, method=HTTPMethod.GET)
        firmware: dict[FirmwareType, LaMarzoccoFirmware] = {}
        for component in FirmwareType:
            current_version = result.get(f"{component}_firmware", {}).get("version")
            latest_version = result.get(f"{component}_firmware", {}).get(
                "targetVersion"
            )
            firmware[component] = LaMarzoccoFirmware(
                current_version=current_version,
                latest_version=latest_version,
            )
        return firmware

    async def update_firmware(
        self, serial_number: str, component: FirmwareType
    ) -> bool:
        """Update Firmware."""

        _LOGGER.debug("Updating firmware for component %s", component)
        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/firmware/{component.value}/update"
        await self._rest_api_call(url=url, method=HTTPMethod.POST, data={})
        retry_counter = 0
        while retry_counter <= 20:
            firmware = await self.get_firmware(serial_number)

            if (
                firmware[component].current_version
                == firmware[component].latest_version
            ):
                _LOGGER.debug("Firmware update for component %s successful", component)
                return True
            _LOGGER.debug(
                "Firmware update for component %s still in progress", component
            )
            await asyncio.sleep(15)
            retry_counter += 1
        _LOGGER.debug(
            "Firmware update for component %s timed out waiting to finish",
            component,
        )
        return False

    async def get_statistics(self, serial_number: str) -> list[dict[str, Any]]:
        """Get statistics from cloud."""

        _LOGGER.debug("Getting statistics from cloud")

        url = f"{GW_MACHINE_BASE_URL}/{serial_number}/statistics/counters"

        return await self._rest_api_call(url=url, method=HTTPMethod.GET)
