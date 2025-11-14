"""The BWT MyService integration."""
from __future__ import annotations

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import BWTApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, REQUEST_TIMEOUT
from .coordinator import BWTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BWT MyService from a config entry with persistent session."""
    hass.data.setdefault(DOMAIN, {})

    # Get credentials and config
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Get scan interval from options (or use default)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    _LOGGER.info(
        "Setting up BWT MyService with polling interval: %d minutes",
        scan_interval,
    )

    # Create persistent aiohttp session with cookie jar
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    session = aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(ssl=False),
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )

    # Create API client with persistent session
    api_client = BWTApiClient(session)

    try:
        # Perform initial authentication
        _LOGGER.debug("Performing initial authentication...")
        if not await api_client.authenticate(username, password):
            await session.close()
            raise ConfigEntryAuthFailed("Authentication failed")

        # Fetch and cache receiptLineKey
        _LOGGER.debug("Retrieving and caching receiptLineKey...")
        await api_client.get_receipt_line_key()

    except Exception as err:
        await session.close()
        _LOGGER.error("Setup failed: %s", err)
        if "Authentication" in str(err):
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        raise ConfigEntryNotReady(f"Failed to setup BWT MyService: {err}") from err

    # Create coordinator
    coordinator = BWTDataUpdateCoordinator(
        hass,
        api_client,
        scan_interval,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and api_client in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("BWT MyService setup completed successfully")
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and close persistent session."""
    _LOGGER.info("Unloading BWT MyService integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Get data and close session properly
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api_client = data["api_client"]

        # Close the persistent session
        await api_client.close()

        _LOGGER.info("BWT MyService unloaded successfully")

    return unload_ok
