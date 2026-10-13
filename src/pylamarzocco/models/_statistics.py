"""Models for statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, override

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from pylamarzocco.const import DoseIndex, DoseMode, WidgetType

from ._general import (
    BaseWidgetOutput,
    Thing,
    Widget,
    filter_valid_widgets,
    from_epoch_ms,
    prepare_widgets,
)


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
    @override
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        prepare_widgets(d, "selectedWidgets")

        # Filter widget code lists using helper
        d["selectedWidgetCodes"] = filter_valid_widgets(
            d.get("selectedWidgetCodes", []), "selectedWidgetCodes"
        )
        d["allWidgetCodes"] = filter_valid_widgets(
            d.get("allWidgetCodes", []), "allWidgetCodes"
        )
        
        return d

    @classmethod
    @override
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
            deserialize=from_epoch_ms,
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
            deserialize=from_epoch_ms,
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
