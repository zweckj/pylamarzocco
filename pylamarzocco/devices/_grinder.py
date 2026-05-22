"""Module for La Marzocco grinders (Pico, Swan).

Read-only support: dashboard/settings/statistics fetched via the cloud client
are parsed into grinder widget models. No setter commands are exposed yet
because the cloud API command names for grinders have not been confirmed.
"""

from __future__ import annotations

import logging

from ._thing import LaMarzoccoThing

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoGrinder(LaMarzoccoThing):
    """Class for a La Marzocco grinder (read-only)."""
