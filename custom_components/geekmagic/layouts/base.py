"""Base layout class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image
from PIL import ImageDraw as PILImageDraw

from ..const import DISPLAY_HEIGHT, DISPLAY_WIDTH
from ..render_context import RenderContext
from ..widgets.components import Component
from ..widgets.state import WidgetState
from ..widgets.theme import DEFAULT_THEME, Theme

if TYPE_CHECKING:
    from PIL import ImageDraw

    from ..renderer import Renderer
    from ..widgets.base import Widget


def _blend(
    base: tuple[int, int, int],
    over: tuple[int, int, int],
    alpha: float,
) -> tuple[int, int, int]:
    """Blend ``over`` onto ``base`` by ``alpha`` (0..1), returning RGB."""
    a = max(0.0, min(1.0, alpha))
    return (
        int(base[0] + (over[0] - base[0]) * a),
        int(base[1] + (over[1] - base[1]) * a),
        int(base[2] + (over[2] - base[2]) * a),
    )


@dataclass
class Slot:
    """Represents a widget slot in a layout."""

    index: int
    rect: tuple[int, int, int, int]  # x1, y1, x2, y2
    widget: Widget | None = None


class Layout(ABC):
    """Base class for display layouts."""

    def __init__(self, padding: int = 8, gap: int = 8) -> None:
        """Initialize the layout.

        Args:
            padding: Padding around the edges
            gap: Gap between widgets
        """
        self.padding = padding
        self.gap = gap
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.slots: list[Slot] = []
        self.theme: Theme = DEFAULT_THEME  # Default theme, can be overridden
        self._calculate_slots()

    @abstractmethod
    def _calculate_slots(self) -> None:
        """Calculate the slot rectangles. Override in subclasses."""

    def _available_space(self) -> tuple[int, int]:
        """Calculate available width and height after padding.

        Returns:
            Tuple of (available_width, available_height)
        """
        return (
            self.width - 2 * self.padding,
            self.height - 2 * self.padding,
        )

    def _grid_cell_size(self, rows: int, cols: int) -> tuple[int, int]:
        """Calculate cell size for a grid layout.

        Args:
            rows: Number of rows
            cols: Number of columns

        Returns:
            Tuple of (cell_width, cell_height)
        """
        aw, ah = self._available_space()
        return (
            (aw - (cols - 1) * self.gap) // cols,
            (ah - (rows - 1) * self.gap) // rows,
        )

    def _split_dimension(self, total: int, ratio: float) -> tuple[int, int]:
        """Split a dimension by ratio, accounting for gap.

        Args:
            total: Total available dimension (excluding gap)
            ratio: Ratio for first section (0.0-1.0)

        Returns:
            Tuple of (first_size, second_size)
        """
        content = total - self.gap
        first = int(content * ratio)
        second = content - first
        return first, second

    def get_slot_count(self) -> int:
        """Return the number of widget slots."""
        return len(self.slots)

    def get_slot(self, index: int) -> Slot | None:
        """Get a slot by index."""
        if 0 <= index < len(self.slots):
            return self.slots[index]
        return None

    def set_widget(self, index: int, widget: Widget) -> None:
        """Set a widget in a slot.

        Args:
            index: Slot index
            widget: Widget to place
        """
        if 0 <= index < len(self.slots):
            self.slots[index].widget = widget

    def render(
        self,
        renderer: Renderer,
        draw: ImageDraw.ImageDraw,
        widget_states: dict[int, WidgetState] | None = None,
    ) -> None:
        """Render all widgets in the layout with clipping.

        Each widget is rendered to a temporary image first, then pasted
        onto the main canvas with a rounded-corner mask. After paste, a
        thin colored accent rule and a soft top highlight are drawn on
        each card to give the surface a printed-on feel.

        Args:
            renderer: Renderer instance
            draw: ImageDraw instance
            widget_states: Dict mapping slot index to WidgetState for each widget
        """
        # Get the main canvas from the draw object
        canvas = draw._image  # noqa: SLF001
        scale = renderer.scale
        theme = self.theme

        # Repaint the canvas with theme background so the gap between cards
        # uses the theme color (not the default black). This makes themes
        # like ocean/sunset/light/forest read correctly.
        canvas_draw = PILImageDraw.Draw(canvas)
        canvas_draw.rectangle((0, 0, canvas.width, canvas.height), fill=theme.background)

        # Default empty states dict
        if widget_states is None:
            widget_states = {}

        # Corner radius for cell masking (in scaled pixels). The fullscreen
        # layout uses 0 padding/gap and should not get rounded corners.
        scaled_radius = max(0, int(theme.corner_radius * scale))
        if self.padding == 0 and self.gap == 0:
            scaled_radius = 0

        for slot in self.slots:
            widget = slot.widget
            if widget is None:
                continue

            # Calculate slot dimensions in scaled coordinates
            x1, y1, x2, y2 = slot.rect
            slot_width = (x2 - x1) * scale
            slot_height = (y2 - y1) * scale

            # Create temporary image for this widget using theme's surface color
            temp_img = Image.new("RGB", (slot_width, slot_height), theme.surface)
            temp_draw = PILImageDraw.Draw(temp_img)

            # Create render context with local coordinates (0, 0 to width, height)
            # The rect is relative to the temp image, not the main canvas
            local_rect = (0, 0, x2 - x1, y2 - y1)
            ctx = RenderContext(temp_draw, local_rect, renderer, theme=theme)

            # Get widget state for this slot
            state = widget_states.get(slot.index, WidgetState())

            # Call widget render - returns Component tree
            result = widget.render(ctx, state)

            # Render the Component tree
            if isinstance(result, Component):
                result.render(ctx, 0, 0, x2 - x1, y2 - y1)

            # Apply card chrome (highlight + accent bar) before masking so
            # the rounded mask clips the chrome to the card shape.
            self._apply_card_chrome(temp_img, slot.index, scale)

            # Paste the widget image onto the main canvas with a rounded
            # mask so the surface has actual rounded corners.
            paste_x = x1 * scale
            paste_y = y1 * scale
            if scaled_radius > 0:
                mask = Image.new("L", (slot_width, slot_height), 0)
                PILImageDraw.Draw(mask).rounded_rectangle(
                    (0, 0, slot_width - 1, slot_height - 1),
                    radius=scaled_radius,
                    fill=255,
                )
                canvas.paste(temp_img, (paste_x, paste_y), mask)
            else:
                canvas.paste(temp_img, (paste_x, paste_y))

        # Apply theme visual effects after all widgets are rendered
        self._apply_theme_effects(canvas, scale)

    def _apply_card_chrome(self, temp_img: Image.Image, slot_index: int, scale: int) -> None:
        """Draw the per-card surface highlight and accent rule.

        These two pieces of chrome are tiny but make a huge difference at
        a glance: the highlight gives the card a subtle printed-on-glass
        feel, and the accent rule color-codes the slot.

        Args:
            temp_img: The widget's temp image (modified in-place)
            slot_index: Slot index, used to pick an accent color
            scale: Supersampling scale factor
        """
        theme = self.theme
        draw = PILImageDraw.Draw(temp_img)
        w = temp_img.width
        # Inset horizontally by ~corner radius so chrome does not poke
        # past rounded corners after masking. We use a slightly tighter
        # inset than radius to keep the chrome visually balanced.
        inset = max(0, int(theme.corner_radius * scale * 0.55))

        # 1) Soft top highlight: a 1px line just inside the top edge,
        # blended toward white over the surface color. Skipped on light
        # surfaces (where it would be invisible) by setting the theme
        # field to 0.0.
        if theme.surface_highlight > 0.0:
            highlight = _blend(theme.surface, (255, 255, 255), theme.surface_highlight)
            line_y = max(0, int(scale * 0.5))  # 1 scaled-px line near the top
            draw.line(
                [(inset, line_y), (w - 1 - inset, line_y)],
                fill=highlight,
                width=max(1, scale // 2),
            )

        # 2) Accent rule: a thin horizontal stripe at the top, colored
        # by accent_colors[slot_index]. Inset to clear the rounded
        # corners.
        if theme.accent_bar_height > 0:
            bar_h = max(1, theme.accent_bar_height * scale)
            accent = theme.get_accent_color(slot_index)
            # Draw the bar slightly below the very edge so the surface
            # highlight sits between it and the cell rim.
            bar_y0 = max(1, int(scale * 0.5)) + max(1, scale // 2)
            draw.rectangle(
                (inset, bar_y0, w - 1 - inset, bar_y0 + bar_h - 1),
                fill=accent,
            )

    def _apply_theme_effects(self, canvas: Image.Image, scale: int) -> None:
        """Apply theme-specific visual effects to the rendered canvas.

        Args:
            canvas: The rendered canvas image
            scale: Supersampling scale factor
        """
        if self.theme.scanlines:
            self._apply_scanlines(canvas, scale)

    def _apply_scanlines(self, canvas: Image.Image, scale: int) -> None:
        """Apply retro scanline effect to the canvas.

        Creates horizontal lines that darken every Nth row for a CRT-like effect.

        Args:
            canvas: The canvas image to modify (in-place)
            scale: Supersampling scale factor
        """
        # Scanlines every 3 scaled pixels (6 pixels at 2x scale)
        line_spacing = 3 * scale
        darkness_factor = 0.7

        # Use PIL pixel access for in-place modification
        pixels = canvas.load()
        if pixels is None:
            return

        for y in range(0, canvas.height, line_spacing):
            for x in range(canvas.width):
                pixel = pixels[x, y]
                if isinstance(pixel, tuple) and len(pixel) >= 3:
                    r, g, b = pixel[0], pixel[1], pixel[2]
                    pixels[x, y] = (
                        int(r * darkness_factor),
                        int(g * darkness_factor),
                        int(b * darkness_factor),
                    )

    def get_all_entities(self) -> list[str]:
        """Get all entity IDs from all widgets."""
        entities = []
        for slot in self.slots:
            if slot.widget is not None:
                entities.extend(slot.widget.get_entities())
        return entities
