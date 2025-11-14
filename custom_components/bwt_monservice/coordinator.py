"""Data update coordinator for BWT MyService."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BWTApiClient, AuthenticationError, ConnectionError as BWTConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BWTDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching BWT data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: BWTApiClient,
        update_interval: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api_client: BWT API client
            update_interval: Update interval in minutes
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval),
        )
        self.api_client = api_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from BWT API using persistent session.

        Returns:
            Dictionary containing device data

        Raises:
            UpdateFailed: If update fails
        """
        try:
            _LOGGER.debug("Starting data update (using persistent session)")
            data = await self.api_client.get_device_data()
            _LOGGER.debug("Data update successful")
            return data

        except AuthenticationError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err

        except BWTConnectionError as err:
            _LOGGER.error("Connection error: %s", err)
            raise UpdateFailed(f"Connection error: {err}") from err

        except Exception as err:
            _LOGGER.error("Unexpected error updating data: %s", err)
            raise UpdateFailed(f"Error updating data: {err}") from err
