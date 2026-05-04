"""Tests for the chart/candlestick label-value header logic.

The four-way mode decision (inline / stacked / value_only / label_only)
is pure data — driven by text widths and container size — so it's easy
to pin down without a real renderer.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.geekmagic.widgets._header import (
    header_height_for,
    header_mode,
)


def _ctx_with_text_widths(label_w: int, value_w: int, text_h: int = 10) -> MagicMock:
    """Build a mock RenderContext that returns deterministic text widths.

    The header logic measures both the label and the value with their own
    fonts — we route via the font name to return the right width.
    """
    ctx = MagicMock()
    label_font = MagicMock(name="font:small")
    value_font = MagicMock(name="font:regular")

    def get_font(name: str, bold: bool = False, adjust: int = 0) -> MagicMock:
        if name == "small":
            return label_font
        if name == "regular":
            return value_font
        return MagicMock(name=f"font:{name}")

    def get_text_size(text: str, font: MagicMock) -> tuple[int, int]:
        if font is label_font:
            return (label_w, text_h)
        if font is value_font:
            return (value_w, text_h)
        return (0, text_h)

    ctx.get_font.side_effect = get_font
    ctx.get_text_size.side_effect = get_text_size
    return ctx


class TestHeaderMode:
    def test_empty_when_neither_present(self) -> None:
        ctx = _ctx_with_text_widths(0, 0)
        assert header_mode(ctx, label=None, value="", inner_w=200, height=120) == "empty"

    def test_label_only_when_no_value(self) -> None:
        ctx = _ctx_with_text_widths(40, 0)
        assert header_mode(ctx, label="Temp", value="", inner_w=200, height=120) == "label_only"

    def test_value_only_when_no_label(self) -> None:
        ctx = _ctx_with_text_widths(0, 30)
        assert header_mode(ctx, label=None, value="23.5°C", inner_w=200, height=120) == "value_only"

    def test_inline_when_both_fit(self) -> None:
        # 40 + 30 + 4 gap = 74 ≤ 200 → inline.
        ctx = _ctx_with_text_widths(40, 30)
        assert header_mode(ctx, label="Temp", value="23.5°C", inner_w=200, height=120) == "inline"

    def test_stacked_when_doesnt_fit_inline_but_tall_enough(self) -> None:
        # 80 + 50 + 4 = 134 > 100 → not inline. Height 120, stacked needs
        # 10+10+4 = 24 ≤ 32% of 120 = 38, and 120 ≥ 90 → stacked.
        ctx = _ctx_with_text_widths(80, 50)
        assert header_mode(ctx, label="Temp", value="23.5°C", inner_w=100, height=120) == "stacked"

    def test_value_only_when_too_short_to_stack(self) -> None:
        # Doesn't fit inline (80+50+4 > 100), and height 60 < 90 → drop label.
        ctx = _ctx_with_text_widths(80, 50)
        assert (
            header_mode(ctx, label="Temp", value="23.5°C", inner_w=100, height=60) == "value_only"
        )

    def test_value_only_when_stacked_too_tall(self) -> None:
        # Doesn't fit inline; tall text means stacked > 32% of height.
        ctx = _ctx_with_text_widths(80, 50, text_h=40)
        # 40+40+4 = 84 vs 32% of 200 = 64 → not stacked.
        assert header_mode(ctx, label="T", value="V", inner_w=100, height=200) == "value_only"


class TestHeaderHeightFor:
    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            ("stacked", 28),  # 10+10+8
            ("inline", 36),  # max(0.18*200=36, 14)
            ("value_only", 36),
            ("label_only", 36),
            ("empty", 16),  # 0.08*200
        ],
    )
    def test_modes(self, mode: str, expected: int) -> None:
        assert (
            header_height_for(mode, label_h=10, value_h=10, height=200)  # type: ignore[arg-type]
            == expected
        )

    def test_inline_floor_uses_max_text_height(self) -> None:
        # When the percentage-based minimum is smaller than the actual
        # text, the floor wins.
        h = header_height_for("inline", label_h=20, value_h=15, height=80)
        assert h >= 24  # max(text_h) + 4

    def test_stacked_height_uses_label_plus_value(self) -> None:
        h = header_height_for("stacked", label_h=12, value_h=20, height=200)
        assert h == 12 + 20 + 8
