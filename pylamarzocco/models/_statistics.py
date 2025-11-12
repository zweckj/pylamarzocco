"""Models for statistics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import DoseIndex, DoseMode, WidgetType

from ._general import BaseWidgetOutput, Thing, Widget

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ThingStatistics(Thing):
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

    widgets: dict[WidgetType, BaseWidgetOutput] = field(default_factory=dict)

    @classmethod
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        # Filter out widgets with unknown codes and log warnings
        widgets = d.get("selectedWidgets", [])
        valid_widgets = []
        
        for widget in widgets:
            code = widget.get("code")
            try:
                # Check if the code is a valid WidgetType
                WidgetType(code)
                widget["output"]["widget_type"] = code
                valid_widgets.append(widget)
            except (ValueError, KeyError):
                _LOGGER.warning(
                    "Unknown widget code '%s' in statistics encountered and will be discarded",
                    code,
                )
        
        d["selectedWidgets"] = valid_widgets
        
        # Filter widget code lists
        selected_codes = d.get("selectedWidgetCodes", [])
        valid_selected_codes = []
        for code in selected_codes:
            try:
                WidgetType(code)
                valid_selected_codes.append(code)
            except ValueError:
                _LOGGER.warning(
                    "Unknown selected widget code '%s' encountered and will be discarded",
                    code,
                )
        d["selectedWidgetCodes"] = valid_selected_codes
        
        all_codes = d.get("allWidgetCodes", [])
        valid_all_codes = []
        for code in all_codes:
            try:
                WidgetType(code)
                valid_all_codes.append(code)
            except ValueError:
                _LOGGER.warning(
                    "Unknown widget code '%s' in allWidgetCodes encountered and will be discarded",
                    code,
                )
        d["allWidgetCodes"] = valid_all_codes
        
        return d

    @classmethod
    def __post_deserialize__(cls, obj: ThingStatistics) -> ThingStatistics:
        # move the firmware to a dict with type as key
        obj.widgets = {widget.code: widget.output for widget in obj.selected_widgets}
        return obj


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


@dataclass(kw_only=True)
class CoffeeAndFlushCounter(BaseWidgetOutput):
    """Coffee counter statistics."""

    widget_type = WidgetType.COFFEE_AND_FLUSH_COUNTER
    total_coffee: int = field(
        metadata=field_options(alias="totalCoffee"),
    )
    total_flush: int = field(
        metadata=field_options(alias="totalFlush"),
    )
