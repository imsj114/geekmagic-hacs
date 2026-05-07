"""Theme-role color sentinels shared by widgets and render contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .theme import Theme

Color = tuple[int, int, int]

# Theme-role sentinels, resolved to the active theme's colors at render time.
# Negative-channel tuples are safe sentinels because legitimate RGB values are
# constrained to 0..255.
THEME_TEXT_PRIMARY: Color = (-1, -1, -1)
THEME_TEXT_SECONDARY: Color = (-2, -2, -2)
THEME_PRIMARY: Color = (-3, -3, -3)
THEME_SECONDARY: Color = (-4, -4, -4)
THEME_SUCCESS: Color = (-5, -5, -5)
THEME_WARNING: Color = (-6, -6, -6)
THEME_ERROR: Color = (-7, -7, -7)
THEME_INFO: Color = (-8, -8, -8)
THEME_MUTED: Color = (-9, -9, -9)
THEME_TEXT_TERTIARY: Color = (-10, -10, -10)


THEME_COLOR_SENTINELS: dict[Color, str] = {
    THEME_TEXT_PRIMARY: "text_primary",
    THEME_TEXT_SECONDARY: "text_secondary",
    THEME_TEXT_TERTIARY: "text_tertiary",
    THEME_PRIMARY: "primary",
    THEME_SECONDARY: "secondary",
    THEME_SUCCESS: "success",
    THEME_WARNING: "warning",
    THEME_ERROR: "error",
    THEME_INFO: "info",
    THEME_MUTED: "muted",
}


def resolve_theme_color(color: Color, theme: Theme) -> Color:
    """Resolve a theme-role sentinel to a concrete RGB color."""
    if color[0] >= 0:
        return color
    attr = THEME_COLOR_SENTINELS.get(color)
    if attr is None:
        return color
    return getattr(theme, attr)


__all__ = [
    "THEME_COLOR_SENTINELS",
    "THEME_ERROR",
    "THEME_INFO",
    "THEME_MUTED",
    "THEME_PRIMARY",
    "THEME_SECONDARY",
    "THEME_SUCCESS",
    "THEME_TEXT_PRIMARY",
    "THEME_TEXT_SECONDARY",
    "THEME_TEXT_TERTIARY",
    "THEME_WARNING",
    "Color",
    "resolve_theme_color",
]
