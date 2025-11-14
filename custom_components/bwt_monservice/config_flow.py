"""Config flow for BWT MyService integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import AuthenticationError, BWTApiClient, ConnectionError as BWTConnectionError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Args:
        hass: Home Assistant instance
        data: User input data

    Returns:
        Dict containing title only (receipt_line_key will be fetched during setup)

    Raises:
        AuthenticationError: If authentication fails
        BWTConnectionError: If connection fails
    """
    _LOGGER.debug("Validating user input for BWT MyService")

    # Create temporary session for validation
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    session = aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(ssl=False),
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )

    api_client = BWTApiClient(session)

    try:
        # Test authentication
        _LOGGER.debug("Testing authentication")
        if not await api_client.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD]):
            raise AuthenticationError("Authentication failed")
        _LOGGER.debug("Authentication successful")

        # Get receipt line key to verify we can access the device
        _LOGGER.debug("Fetching receipt line key")
        receipt_line_key = await api_client.get_receipt_line_key()
        _LOGGER.debug("Receipt line key verified: %s", receipt_line_key)

        # Return minimal data - actual setup will happen in __init__.py
        return {
            "title": "BWT MyService",
            "receipt_line_key": receipt_line_key,  # Use for unique_id only
        }

    except Exception as err:
        _LOGGER.error("Error validating input: %s", err, exc_info=True)
        raise
    finally:
        # Always close the temporary session
        await session.close()


class BWTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BWT MyService."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Create unique ID based on receipt_line_key
                await self.async_set_unique_id(info["receipt_line_key"])
                self._abort_if_unique_id_configured()

                # Store only credentials (receipt_line_key will be fetched during setup)
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }

                # Create entry
                return self.async_create_entry(
                    title=info["title"],
                    data=data,
                )

            except AuthenticationError as err:
                _LOGGER.error("Authentication error: %s", err)
                errors["base"] = "invalid_auth"
            except BWTConnectionError as err:
                _LOGGER.error("Connection error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config flow: %s", err)
                errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BWTOptionsFlowHandler:
        """Get the options flow for this handler."""
        return BWTOptionsFlowHandler()


class BWTOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for BWT MyService."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current scan interval or use default
        # Access options via config_entry which is set by the framework
        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): vol.All(
                    cv.positive_int,
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
