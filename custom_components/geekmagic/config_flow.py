"""Config flow for GeekMagic integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DISPLAY_ROTATION,
    CONF_JPEG_QUALITY,
    CONF_LAYOUT,
    CONF_REFRESH_INTERVAL,
    CONF_SCREEN_CYCLE_INTERVAL,
    CONF_SCREEN_THEME,
    CONF_SCREENS,
    CONF_WIDGETS,
    DEFAULT_DISPLAY_ROTATION,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_SCREEN_CYCLE_INTERVAL,
    DOMAIN,
    LAYOUT_GRID_2X2,
    THEME_WATCHOS,
)
from .device import GeekMagicDevice

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default="GeekMagic Display"): str,
    }
)


class GeekMagicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GeekMagic.

    This flow handles initial device setup only.
    All screen/widget configuration is done through entities (WLED-style).
    """

    # VERSION 2: unique_id switched from host (IP) to MAC address. Existing
    # v1 entries are upgraded in async_migrate_entry.
    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - device connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            _LOGGER.debug("Config flow: attempting to configure device at %s", host)

            # Test connection first — we need to talk to the device to read
            # its MAC, and a clear connection error beats a silent abort.
            session = async_get_clientsession(self.hass)
            device = GeekMagicDevice(host, session=session)
            result = await device.test_connection()

            if not result.success:
                _LOGGER.warning("Config flow: failed to connect to %s: %s", host, result.message)
                errors["base"] = result.error
            else:
                # Prefer the device's MAC address as the unique_id so that
                # DHCP renumbering does not produce a duplicate entry. Fall
                # back to the host string only when the firmware does not
                # expose any usable MAC field — older firmware revisions.
                mac = await device.get_mac()
                unique_id = mac or device.host
                _LOGGER.info(
                    "Config flow: connected to %s, unique_id=%s (%s)",
                    host,
                    unique_id,
                    "mac" if mac else "host fallback",
                )

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Create entry with default options
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, f"GeekMagic ({device.host})"),
                    data=user_input,
                    options=self._get_default_options(),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _get_default_options(self) -> dict[str, Any]:
        """Get default options for a new device."""
        return {
            CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
            CONF_SCREEN_CYCLE_INTERVAL: DEFAULT_SCREEN_CYCLE_INTERVAL,
            CONF_JPEG_QUALITY: DEFAULT_JPEG_QUALITY,
            CONF_DISPLAY_ROTATION: DEFAULT_DISPLAY_ROTATION,
            CONF_SCREENS: [
                {
                    "name": "Screen 1",
                    CONF_LAYOUT: LAYOUT_GRID_2X2,
                    CONF_SCREEN_THEME: THEME_WATCHOS,
                    CONF_WIDGETS: [{"type": "clock", "slot": 0}],
                }
            ],
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GeekMagicOptionsFlow:
        """Get the options flow for this handler."""
        return GeekMagicOptionsFlow()


class GeekMagicOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for GeekMagic.

    Note: Most configuration is done through entities now (WLED-style).
    This options flow is kept minimal for advanced users who want to
    reset to defaults or import/export configurations.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show options menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "reset_defaults":
                return await self.async_step_reset_defaults()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "reset_defaults": "Reset to Default Configuration",
                        }
                    )
                }
            ),
            description_placeholders={
                "tip": "Tip: Configure your display using the device entities "
                "(brightness, screens, widgets, etc.) on the device page."
            },
        )

    async def async_step_reset_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reset to default configuration."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Reset to defaults
                default_options = {
                    CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
                    CONF_SCREEN_CYCLE_INTERVAL: DEFAULT_SCREEN_CYCLE_INTERVAL,
                    CONF_SCREENS: [
                        {
                            "name": "Screen 1",
                            CONF_LAYOUT: LAYOUT_GRID_2X2,
                            CONF_SCREEN_THEME: THEME_WATCHOS,
                            CONF_WIDGETS: [{"type": "clock", "slot": 0}],
                        }
                    ],
                }
                return self.async_create_entry(title="", data=default_options)
            # User cancelled
            return await self.async_step_init()

        return self.async_show_form(
            step_id="reset_defaults",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                }
            ),
            description_placeholders={
                "warning": "This will reset all screens and widgets to defaults. "
                "Your current configuration will be lost."
            },
        )
