"""GeekMagic Display integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import GeekMagicCoordinator
from .device import GeekMagicDevice
from .panel import async_register_panel
from .store import GeekMagicStore
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

# Schema for integrations configured via UI only (no YAML support)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Platforms for device control entities and image output
PLATFORMS: list[Platform] = [
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the GeekMagic domain.

    This is called once when the integration is first loaded.
    It initializes the global store, WebSocket commands, and panel.

    Args:
        hass: Home Assistant instance
        config: Configuration dictionary

    Returns:
        True if setup successful
    """
    _LOGGER.debug("Setting up GeekMagic domain")

    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})

    # Initialize global store for views
    store = GeekMagicStore(hass)
    await store.async_load()
    hass.data[DOMAIN]["store"] = store

    # Register WebSocket commands
    async_register_websocket_commands(hass)

    # Register custom panel
    await async_register_panel(hass)

    # Register notify service
    async def async_handle_notify(call):
        """Handle the notify service call."""
        device_ids = call.data.get("device_id")
        if not isinstance(device_ids, list):
            device_ids = [device_ids]

        # Get device registry to map device_ids to config entries
        dev_reg = dr.async_get(hass)

        for device_id in device_ids:
            device = dev_reg.async_get(device_id)
            if not device:
                continue

            # Find config entry for this device
            for entry_id in device.config_entries:
                if entry_id in hass.data[DOMAIN]:
                    coordinator = hass.data[DOMAIN][entry_id]
                    if isinstance(coordinator, GeekMagicCoordinator):
                        await coordinator.trigger_notification(call.data)

    hass.services.async_register(DOMAIN, "notify", async_handle_notify)

    _LOGGER.info("GeekMagic domain setup complete")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GeekMagic from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if setup successful
    """
    # Ensure domain is set up
    if DOMAIN not in hass.data:
        await async_setup(hass, {})

    host = entry.data[CONF_HOST]
    _LOGGER.debug("Setting up GeekMagic integration for %s", host)

    session = async_get_clientsession(hass)
    device = GeekMagicDevice(host, session=session)

    # Test connection - raise ConfigEntryNotReady if device is offline
    # This allows HA to automatically retry instead of showing a "Setup Error"
    result = await device.test_connection()
    if not result:
        raise ConfigEntryNotReady(
            f"Could not connect to GeekMagic device at {host}: {result.message}"
        )

    _LOGGER.debug("Successfully connected to GeekMagic device at %s", host)

    # Detect device model (Pro vs Ultra)
    await device.detect_model()

    # One-shot cleanup: prior versions registered the image preview entity
    # under a separate device_info dict that used the host string as its
    # identifier and hardcoded the model as "SmallTV Pro". For Ultra
    # hardware this left a stale, duplicate device entry alongside the
    # real one. Remove any such orphan device on every setup so that users
    # who hit the bug get the duplicate cleaned up automatically.
    _cleanup_duplicate_device(hass, entry, host)

    # Create coordinator
    coordinator = GeekMagicCoordinator(
        hass=hass,
        device=device,
        options=dict(entry.options),
        config_entry=entry,
    )

    # Do first refresh
    _LOGGER.debug("Performing first refresh for %s", host)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("GeekMagic integration successfully set up for %s", host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry

    Returns:
        True if unload successful
    """
    host = entry.data.get(CONF_HOST, "unknown")
    _LOGGER.debug("Unloading GeekMagic integration for %s", host)

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove coordinator
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        del hass.data[DOMAIN][entry.entry_id]
        _LOGGER.debug("GeekMagic integration unloaded for %s", host)

    return unload_ok


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Args:
        hass: Home Assistant instance
        entry: Config entry
    """
    host = entry.data.get(CONF_HOST, "unknown")
    _LOGGER.debug("Options updated for GeekMagic device %s", host)
    coordinator: GeekMagicCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_options(dict(entry.options))
    # Trigger immediate refresh so device displays updated config
    await coordinator.async_request_refresh()


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry being removed
    """
    # Clean up any resources if needed


def _cleanup_duplicate_device(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Remove the stale host-keyed device created by older versions.

    Earlier image.py registered its device with ``identifiers={(DOMAIN,
    host)}`` and ``model="SmallTV Pro"`` — independent of the
    ``(DOMAIN, entry_id)`` identifier used by every other platform.
    After the image entity is moved onto the unified identifier, that
    host-keyed device record becomes an orphan that HA does not garbage
    collect on its own. Detect and remove it.
    """
    dev_reg = dr.async_get(hass)
    stale = dev_reg.async_get_device(identifiers={(DOMAIN, host)})
    if stale is None:
        return
    # Only nuke devices that actually belong to this config entry — never
    # touch a device that some other integration happens to have keyed on
    # the same string.
    if entry.entry_id not in stale.config_entries:
        return
    _LOGGER.info(
        "Removing duplicate GeekMagic device %s (host-keyed identifier '%s')",
        stale.id,
        host,
    )
    dev_reg.async_remove_device(stale.id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to newer schemas.

    Version history:
        1 → 2: ``unique_id`` was the device's IP/host string. We now use
            the device's MAC address so DHCP renumbering no longer
            produces a duplicate config entry. If the device is reachable
            we fetch its MAC and rewrite ``unique_id``; if it isn't, we
            leave the host-based unique_id in place and the migration
            will retry on next HA start.
    """
    _LOGGER.debug("Migrating GeekMagic entry %s from version %s", entry.entry_id, entry.version)

    if entry.version == 1:
        host = entry.data.get(CONF_HOST)
        if not host:
            _LOGGER.error("Cannot migrate entry %s: missing host in entry.data", entry.entry_id)
            return False

        session = async_get_clientsession(hass)
        device = GeekMagicDevice(host, session=session)
        try:
            mac = await device.get_mac()
        except Exception as err:
            _LOGGER.warning(
                "Could not reach %s to read MAC for migration: %s. Will retry on next setup.",
                host,
                err,
            )
            mac = None

        if mac:
            hass.config_entries.async_update_entry(entry, unique_id=mac, version=2)
            _LOGGER.info(
                "Migrated entry %s unique_id host→MAC (%s → %s)",
                entry.entry_id,
                host,
                mac,
            )
        else:
            # No MAC available — keep the host-based unique_id but bump
            # the schema version so we don't try migrating again on every
            # restart. A renumber will still cause a duplicate, but the
            # user gets no worse than they had before.
            hass.config_entries.async_update_entry(entry, version=2)
            _LOGGER.info(
                "Migrated entry %s to v2 with host-based unique_id (device did not expose MAC)",
                entry.entry_id,
            )

    return True
