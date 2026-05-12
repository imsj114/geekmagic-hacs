"""Image platform for GeekMagic display preview."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODEL_PRO, MODEL_ULTRA

if TYPE_CHECKING:
    from .coordinator import GeekMagicCoordinator

_LOGGER = logging.getLogger(__name__)


def _model_name(model: str) -> str:
    """Map the internal model token to a human-readable device name."""
    if model == MODEL_PRO:
        return "SmallTV Pro"
    if model == MODEL_ULTRA:
        return "SmallTV Ultra"
    return "SmallTV"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GeekMagic image from a config entry."""
    coordinator: GeekMagicCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Setting up GeekMagic image for %s", entry.data.get(CONF_HOST))
    async_add_entities([GeekMagicPreviewImage(hass, coordinator, entry)])


class GeekMagicPreviewImage(ImageEntity):
    """Image entity showing the GeekMagic display preview.

    Updates only when config changes (preview_just_updated=True), not on
    periodic coordinator refreshes. This prevents constant re-renders while
    still showing updated previews after configuration changes.
    """

    _attr_has_entity_name = True
    _attr_name = "Display Preview"
    _attr_content_type = "image/png"
    # Disable state polling - we update via coordinator listener only on config changes
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: GeekMagicCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(hass)
        self.coordinator = coordinator
        self._entry = entry

        # Entity attributes — anchor the unique_id and device identifier
        # to the config entry so the image entity ends up on the SAME
        # device record as the rest of the platforms (number, sensor,
        # etc.). Previously this used CONF_HOST + a hardcoded "SmallTV Pro"
        # model, which created a duplicate device in the registry whenever
        # the actual hardware was an Ultra.
        self._attr_unique_id = f"{entry.entry_id}_preview"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GeekMagic",
            model=_model_name(coordinator.device.model),
        )

        # Set initial timestamp
        if coordinator.last_image is not None:
            self._attr_image_last_updated = dt_util.utcnow()

        _LOGGER.debug(
            "Initialized GeekMagic image %s",
            self._attr_unique_id,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        # Listen to coordinator updates, but only act on config changes
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Only updates state when preview_just_updated is True (config changed).
        Periodic refreshes do NOT trigger state updates, preventing re-renders.
        """
        if self.coordinator.preview_just_updated and self.coordinator.last_image is not None:
            self._attr_image_last_updated = dt_util.utcnow()
            self._cached_image = None
            self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return the current display preview image."""
        image = self.coordinator.last_image
        if image is not None:
            return image

        _LOGGER.debug(
            "Image %s: No image available yet",
            self._attr_unique_id,
        )
        return None

    @property
    def available(self) -> bool:
        """Return True if an image has been generated."""
        return self.coordinator.last_image is not None
