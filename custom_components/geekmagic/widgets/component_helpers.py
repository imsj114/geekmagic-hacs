"""Convenience component factories for common widget patterns.

Each gauge / value helper here is now a thin shim over ``DataCard`` —
the layout policy lives in one place, and these factories just choose
the right indicator (``Bar`` / ``VerticalBar`` / ``Ring`` / ``Arc``) and
the right ``icon_role``.

Example:

    return BarGauge(percent=75, value="75%", label="CPU", color=THEME_PRIMARY)

is equivalent to:

    return DataCard(
        caption="CPU",
        hero="75%",
        hero_color=THEME_PRIMARY,
        indicator=Bar(percent=75, color=THEME_PRIMARY),
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .components import (
    THEME_TEXT_PRIMARY,
    THEME_TEXT_SECONDARY,
    Arc,
    Bar,
    Component,
    Ring,
    VerticalBar,
)
from .data_card import DataCard, pick_card_mode

if TYPE_CHECKING:
    from ..render_context import RenderContext

Color = tuple[int, int, int]

BarGaugeMode = Literal["auto", "compact", "stacked", "vertical"]


@dataclass
class BarGauge(Component):
    """Adaptive bar gauge — DataCard with a ``Bar`` (or ``VerticalBar``)
    indicator. Mode is resolved by ``pick_card_mode``: tall+narrow
    cells get a ``VerticalBar``, square-ish roomy cells get the
    Modular-Large stacked look, everything else gets the compact
    horizontal bar.
    """

    percent: float
    value: str
    label: str
    color: Color
    icon: str | None = None
    background: Color | None = None  # None = theme tinted track
    padding: int = 6
    mode: BarGaugeMode = "auto"

    def measure(self, ctx: RenderContext, max_width: int, max_height: int) -> tuple[int, int]:
        return (max_width, max_height)

    def render(self, ctx: RenderContext, x: int, y: int, width: int, height: int) -> None:
        # Pick the indicator first so DataCard's auto-mode can promote
        # tall+narrow cells to vertical (which needs a VerticalBar).
        if self.mode == "vertical" or (
            self.mode == "auto"
            and pick_card_mode(width, height) == "compact"
            and height > width * 1.8
        ):
            indicator: Component = VerticalBar(
                percent=self.percent, color=self.color, background=self.background
            )
        else:
            indicator = Bar(percent=self.percent, color=self.color, background=self.background)
        DataCard(
            caption=self.label,
            icon=self.icon,
            icon_color=self.color,
            icon_role="feature",
            hero=self.value,
            hero_color=self.color,  # Activity-bar style: hero matches the bar tint
            indicator=indicator,
        ).render(ctx, x, y, width, height)


@dataclass
class RingGauge(Component):
    """Adaptive ring gauge — DataCard with a ``Ring`` indicator (mode="ring")."""

    percent: float
    value: str
    label: str
    color: Color
    background: Color | None = None  # None = theme tinted track

    def measure(self, ctx: RenderContext, max_width: int, max_height: int) -> tuple[int, int]:
        return (max_width, max_height)

    def render(self, ctx: RenderContext, x: int, y: int, width: int, height: int) -> None:
        DataCard(
            caption=self.label,
            hero=self.value,
            hero_color=self.color,
            indicator=Ring(percent=self.percent, color=self.color, background=self.background),
        ).render(ctx, x, y, width, height)


@dataclass
class ArcGauge(Component):
    """Adaptive arc gauge — DataCard with an ``Arc`` indicator (mode="ring")."""

    percent: float
    value: str
    label: str
    color: Color
    background: Color | None = None  # None = theme tinted track

    def measure(self, ctx: RenderContext, max_width: int, max_height: int) -> tuple[int, int]:
        return (max_width, max_height)

    def render(self, ctx: RenderContext, x: int, y: int, width: int, height: int) -> None:
        DataCard(
            caption=self.label,
            hero=self.value,
            hero_color=self.color,
            indicator=Arc(percent=self.percent, color=self.color, background=self.background),
        ).render(ctx, x, y, width, height)


def IconValue(
    icon: str,
    value: str,
    label: str,
    color: Color,
    value_color: Color = THEME_TEXT_PRIMARY,
    label_color: Color = THEME_TEXT_SECONDARY,
    icon_size: int | None = None,
) -> Component:
    """Icon with value and label — backed by ``DataCard``."""
    return DataCard(
        caption=label or None,
        icon=icon,
        icon_color=color,
        icon_role="feature",
        hero=value,
        hero_color=value_color,
    )


def CenteredValue(
    value: str,
    label: str | None = None,
    value_color: Color = THEME_TEXT_PRIMARY,
    label_color: Color = THEME_TEXT_SECONDARY,
    value_font: str = "large",
    label_font: str = "small",
) -> Component:
    """Centered value with optional label — backed by ``DataCard``."""
    return DataCard(
        caption=label,
        hero=value,
        hero_color=value_color,
    )


__all__ = [
    "ArcGauge",
    "BarGauge",
    "CenteredValue",
    "IconValue",
    "RingGauge",
]
