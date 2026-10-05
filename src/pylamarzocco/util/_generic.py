"""General utility functions."""

from aiohttp import ClientResponse

def is_success(response: ClientResponse) -> bool:
    """Check if response is successful."""
    return 200 <= response.status < 300