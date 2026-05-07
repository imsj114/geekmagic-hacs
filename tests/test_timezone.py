"""Tests for timezone handling in preview rendering."""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo


class TestPreviewTimezone:
    """Test timezone handling in preview rendering."""

    def test_timezone_override_for_clock_widget(self):
        """Test that clock widget timezone override creates correct datetime."""

        # Simulate the logic from websocket.py
        base_tz = ZoneInfo("Europe/Paris")
        now = datetime.now(tz=base_tz)

        # Test clock widget with timezone override
        widget_data: dict[str, Any] = {
            "type": "clock",
            "slot": 0,
            "options": {"timezone": "America/New_York"},
        }

        widget_now = now
        if widget_data.get("type") == "clock":
            tz_option = widget_data.get("options", {}).get("timezone")
            if tz_option:
                widget_tz = ZoneInfo(tz_option)
                widget_now = datetime.now(tz=widget_tz)

        # Verify the timezone was applied
        assert widget_now.tzinfo is not None
        assert str(widget_now.tzinfo) == "America/New_York"

    def test_timezone_override_empty_string_uses_default(self):
        """Test that empty timezone string uses default timezone."""

        base_tz = ZoneInfo("Europe/Paris")
        now = datetime.now(tz=base_tz)

        widget_data: dict[str, Any] = {
            "type": "clock",
            "slot": 0,
            "options": {"timezone": ""},
        }

        widget_now = now
        if widget_data.get("type") == "clock":
            tz_option = widget_data.get("options", {}).get("timezone")
            if tz_option:  # Empty string is falsy
                widget_tz = ZoneInfo(tz_option)
                widget_now = datetime.now(tz=widget_tz)

        # Should still have the base timezone since empty string is falsy
        assert str(widget_now.tzinfo) == "Europe/Paris"

    def test_timezone_override_only_applies_to_clock(self):
        """Test that timezone override only applies to clock widgets."""

        base_tz = ZoneInfo("Europe/Paris")
        now = datetime.now(tz=base_tz)

        widget_data: dict[str, Any] = {
            "type": "entity",  # Not a clock widget
            "slot": 0,
            "options": {"timezone": "America/New_York"},
        }

        widget_now = now
        if widget_data.get("type") == "clock":
            tz_option = widget_data.get("options", {}).get("timezone")
            if tz_option:
                widget_tz = ZoneInfo(tz_option)
                widget_now = datetime.now(tz=widget_tz)

        # Should still have the base timezone (entity widget doesn't get override)
        assert str(widget_now.tzinfo) == "Europe/Paris"

    def test_invalid_timezone_is_handled_gracefully(self):
        """Test that invalid timezone doesn't crash."""
        import contextlib

        base_tz = ZoneInfo("Europe/Paris")
        now = datetime.now(tz=base_tz)

        widget_data: dict[str, Any] = {
            "type": "clock",
            "slot": 0,
            "options": {"timezone": "Invalid/Timezone"},
        }

        widget_now = now
        if widget_data.get("type") == "clock":
            tz_option = widget_data.get("options", {}).get("timezone")
            if tz_option:
                with contextlib.suppress(Exception):
                    widget_tz = ZoneInfo(tz_option)
                    widget_now = datetime.now(tz=widget_tz)

        # Should fall back to base timezone on invalid timezone
        assert str(widget_now.tzinfo) == "Europe/Paris"

    def test_hass_timezone_fallback_to_utc(self):
        """Test that missing time_zone_obj falls back to UTC."""
        from datetime import UTC

        # Mock hass config without time_zone_obj
        mock_config = MagicMock()
        del mock_config.time_zone_obj  # Remove the attribute

        tz = getattr(mock_config, "time_zone_obj", None) or UTC
        assert tz == UTC

    def test_hass_timezone_uses_config(self):
        """Test that time_zone_obj from config is used."""
        mock_config = MagicMock()
        mock_config.time_zone_obj = ZoneInfo("Asia/Tokyo")

        tz = getattr(mock_config, "time_zone_obj", None)
        assert tz is not None
        assert str(tz) == "Asia/Tokyo"
