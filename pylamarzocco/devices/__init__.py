"""Init the devices module."""

from ._machine import LaMarzoccoMachine
from ._thing import LaMarzoccoThing

__all__ = [
    "LaMarzoccoMachine",
    "LaMarzoccoThing",
]
