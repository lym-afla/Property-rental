"""Typed response contracts shared by portfolio analytics services."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeriesDefinition:
    key: str
    label: str
    kind: str


@dataclass(frozen=True)
class TimeSeriesPoint:
    date: date
    values: dict[str, object]


@dataclass(frozen=True)
class TimeSeriesResponse:
    metric: str
    grain: str
    currency: str | None
    scale: int
    start: date
    end: date
    series: tuple[SeriesDefinition, ...]
    points: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class CategoryValue:
    key: str
    label: str
    value: object
