"""Helpers for the pylamarzocco package."""

from aiohttp import ClientResponse
from .const import StompMessageType


def is_success(response: ClientResponse) -> bool:
    """Check if response is successful."""
    return 200 <= response.status < 300


def encode_stomp_ws_message(
    msg_type: StompMessageType, headers: dict[str, str], body: str | None = None
) -> str:
    """Encode STOMP WebSocket message."""
    fragments: list[str] = []
    fragments.append(str(msg_type))
    for key, value in headers.items():
        fragments.append(f"{key}:{value}")
    msg = "\n".join(fragments)
    msg += "\n\n"
    if body:
        msg += body
    msg += "\x00"
    return msg


def decode_stomp_ws_message(
    msg: str,
) -> tuple[StompMessageType, dict[str, str], str | None]:
    """Decode STOMP WebSocket message."""
    header, data = msg.split("\n\n", 1)
    headers: dict[str, str] = {}
    metadata = header.split("\n")
    msg_type = StompMessageType(metadata[0])
    for header in metadata[1:]:
        key, value = header.split(":", 1)
        headers[key] = value
    if data.endswith("\x00"):
        data = data[:-1]
    return msg_type, headers, data
