"""Init the devices module.

Currently not in use
"""

from ._grinder import LaMarzoccoGrinder
from ._machine import LaMarzoccoMachine
from ._thing import LaMarzoccoThing

__all__ = [
    "LaMarzoccoGrinder",
    "LaMarzoccoMachine",
    "LaMarzoccoThing",
]
