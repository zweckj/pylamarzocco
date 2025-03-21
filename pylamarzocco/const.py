"""Constants for La Marzocco Cloud."""

from enum import StrEnum

# Base URL for La Marzocco Cloud

BASE_URL = "lion.lamarzocco.io"
CUSTOMER_APP_URL = f"https://{BASE_URL}/api/customer-app"


class MachineState(StrEnum):
    """Machine states."""

    BREWING_MODE = "BrewingMode"
    STANDBY = "StandBy"

class PreExtractionMode(StrEnum):
    """Pre-extraction modes."""

    PREINFUSION = "PreInfusion"
    PREBREWING = "PreBrewing"
    DISABLED = "Disabled"