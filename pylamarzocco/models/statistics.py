"""Models for statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import WidgetType, DoseIndex, DoseMode
from pylamarzocco.models.general import Device, Widget, BaseWidgetOutput


@dataclass(kw_only=True)
class Statistics(Device):
    """Statistics model."""

    firmwares: str | None = field(
        default=None,
    )
    selected_widget_codes: list[WidgetType] = field(
        metadata=field_options(
            alias="selectedWidgetCodes",
        ),
        default_factory=list,
    )
    all_widget_codes: list[WidgetType] = field(
        metadata=field_options(
            alias="allWidgetCodes",
        ),
        default_factory=list,
    )
    selected_widgets: list[Widget] = field(
        metadata=field_options(
            alias="selectedWidgets",
        ),
        default_factory=list,
    )

    @classmethod
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        # move code to widget_type for mashumaro annotated serialization
        widgets = d["selectedWidgets"]
        for widget in widgets:
            widget["output"]["widget_type"] = widget["code"]
        d["selectedWidgets"] = widgets
        return d


@dataclass(kw_only=True)
class CoffeeAndFlushTrend(BaseWidgetOutput):
    """Coffee and flush trend model."""

    widget_type = WidgetType.COFFEE_AND_FLUSH_TREND
    days: int
    timezone: str
    coffees: list[CoffeeHistoryEvent]


@dataclass(kw_only=True)
class CoffeeHistoryEvent(DataClassJSONMixin):
    """Coffee that has been made in the past."""

    timestamp: datetime = field(
        metadata=field_options(
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
        )
    )
    value: int


@dataclass(kw_only=True)
class LastCoffeeList(BaseWidgetOutput):
    """Last coffees statistics."""

    widget_type = WidgetType.LAST_COFFEE
    last_coffees: list[LastCoffee] = field(
        metadata=field_options(alias="lastCoffees"),
        default_factory=list,
    )


@dataclass(kw_only=True)
class LastCoffee(DataClassJSONMixin):
    """One of the last coffees."""

    time: datetime = field(
        metadata=field_options(
            deserialize=lambda ts: datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
        )
    )
    extraction_seconds: float = field(
        metadata=field_options(alias="extractionSeconds"),
    )
    dose_mode: DoseMode = field(
        metadata=field_options(alias="doseMode"),
    )
    dose_index: DoseIndex = field(
        metadata=field_options(alias="doseIndex"),
    )
    dose_value_numerator: str | None = field(
        metadata=field_options(alias="doseValueNumerator"),
        default=None,
    )
