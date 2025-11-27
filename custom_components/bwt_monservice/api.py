"""API client for BWT MyService with persistent session."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    AJAX_URL,
    DASHBOARD_URL,
    DEVICE_URL,
    LOGIN_URL,
)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""


class ConnectionError(Exception):
    """Exception raised for connection errors."""


class DataNotFoundError(Exception):
    """Exception raised when data is not found."""


class BWTApiClient:
    """API client for BWT MyService with persistent session."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client with a persistent session.

        Args:
            session: Persistent aiohttp.ClientSession with cookie jar
        """
        self._session = session
        self._receipt_line_key: str | None = None
        self._is_authenticated: bool = False
        self._username: str | None = None
        self._password: str | None = None

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with BWT MyService and store credentials.

        Args:
            username: User email
            password: User password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        _LOGGER.debug("Authenticating user: %s", username)

        # Store credentials for potential re-authentication
        self._username = username
        self._password = password

        try:
            # First, visit the login page to get any necessary cookies/tokens
            try:
                _LOGGER.debug("Fetching login page: %s", LOGIN_URL)
                async with self._session.get(LOGIN_URL) as response:
                    _LOGGER.debug("Login page status: %s", response.status)
            except Exception as err:
                _LOGGER.debug("Error fetching login page (continuing anyway): %s", err)

            # Prepare login data
            data = {
                "_username": username,
                "_password": password,
            }

            _LOGGER.debug("Posting login credentials to: %s", LOGIN_URL)

            # Perform login
            async with self._session.post(LOGIN_URL, data=data, allow_redirects=True) as response:
                final_url = str(response.url)
                status = response.status
                _LOGGER.debug("Login response status: %s, final URL: %s", status, final_url)

                if status != 200:
                    _LOGGER.error("Login failed with status %s", status)
                    raise AuthenticationError(f"Login failed with status {status}")

                # Get response text for debugging
                text = await response.text()
                _LOGGER.debug("Response text length: %d characters", len(text))

                # Check if we were redirected to dashboard (successful login)
                if "dashboard" in final_url:
                    self._is_authenticated = True
                    _LOGGER.info("Authentication successful (redirected to dashboard)")
                    return True

                # Check response content for error messages
                text_lower = text.lower()
                if "identifiants invalides" in text_lower or "invalid credentials" in text_lower:
                    _LOGGER.error("Invalid credentials detected in response")
                    raise AuthenticationError("Invalid credentials")

                # Check if login form is still present (failed login)
                if "_username" in text or "_password" in text:
                    _LOGGER.error("Login form still present - authentication failed")
                    raise AuthenticationError("Authentication failed - login form still present")

                # If we reach here, assume success (might be logged in but not redirected)
                _LOGGER.warning("Login completed but not redirected to dashboard - assuming success")
                self._is_authenticated = True
                return True

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error during authentication: %s", err)
            raise ConnectionError(f"Connection error during authentication: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout during authentication")
            raise ConnectionError("Timeout during authentication") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during authentication: %s", err)
            raise ConnectionError(f"Unexpected error: {err}") from err

    async def _ensure_authenticated(self) -> None:
        """Ensure session is authenticated, re-authenticate if needed.

        Raises:
            AuthenticationError: If re-authentication fails
        """
        if not self._is_authenticated:
            if not self._username or not self._password:
                raise AuthenticationError("No credentials stored for re-authentication")

            _LOGGER.warning("Session expired, re-authenticating...")
            await self.authenticate(self._username, self._password)

    async def get_receipt_line_key(self) -> str:
        """Get receipt line key from dashboard (cached after first call).

        Returns:
            Receipt line key

        Raises:
            AuthenticationError: If not authenticated
            DataNotFoundError: If receipt line key not found
            ConnectionError: If connection fails
        """
        # Return cached value if available
        if self._receipt_line_key:
            _LOGGER.debug("Using cached receiptLineKey: %s", self._receipt_line_key)
            return self._receipt_line_key

        await self._ensure_authenticated()

        try:
            _LOGGER.debug("Fetching dashboard to extract receipt line key")

            async with self._session.get(DASHBOARD_URL) as response:
                # Handle authentication failures
                if response.status in (401, 403):
                    _LOGGER.warning("Dashboard returned %s, session expired - re-authenticating", response.status)
                    self._is_authenticated = False
                    await self._ensure_authenticated()
                    # Retry after re-authentication
                    async with self._session.get(DASHBOARD_URL) as retry_response:
                        if retry_response.status != 200:
                            raise ConnectionError(f"Failed to fetch dashboard after re-auth: {retry_response.status}")
                        html = await retry_response.text()
                elif response.status == 500:
                    _LOGGER.warning("Dashboard returned 500 (server overload)")
                    raise ConnectionError("Server overload (500)")
                elif response.status != 200:
                    raise ConnectionError(f"Failed to fetch dashboard: {response.status}")
                else:
                    html = await response.text()

                soup = BeautifulSoup(html, "lxml")

                # Find link with href containing receiptLineKey
                device_link = soup.find("a", href=lambda x: x and "receiptLineKey=" in x)

                if not device_link:
                    raise DataNotFoundError("No device found in dashboard")

                # Extract receiptLineKey from href
                href = device_link.get("href")
                if "receiptLineKey=" in href:
                    key = href.split("receiptLineKey=")[1].split("&")[0]
                    # Cache the key for future use
                    self._receipt_line_key = key
                    _LOGGER.info("Receipt line key extracted and cached: %s", key)
                    return key

                raise DataNotFoundError("Receipt line key not found in link")

        except (AuthenticationError, DataNotFoundError, ConnectionError):
            raise
        except aiohttp.ClientError as err:
            raise ConnectionError(f"Connection error fetching dashboard: {err}") from err
        except asyncio.TimeoutError as err:
            raise ConnectionError("Timeout fetching dashboard") from err

    async def get_device_data(self) -> dict[str, Any]:
        """Fetch all device data using persistent session.

        Returns:
            Dictionary containing device data

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        await self._ensure_authenticated()

        # Ensure we have the receipt line key
        if not self._receipt_line_key:
            await self.get_receipt_line_key()

        try:
            # Fetch AJAX data (real-time data: consumption, regenerations, alarms)
            ajax_data = await self._fetch_ajax_data()

            # Fetch HTML data (configuration: hardness, pressure, holiday mode, serial, etc.)
            html_data = await self._fetch_html_data()

            # Merge both data sources (HTML data won't overwrite AJAX data)
            html_data.update(ajax_data)

            return html_data

        except aiohttp.ClientError as err:
            # Check if it's an authentication error
            if "401" in str(err) or "403" in str(err):
                _LOGGER.warning("Session expired during data fetch, re-authenticating...")
                self._is_authenticated = False
                await self._ensure_authenticated()

                # Retry after re-authentication
                return await self._fetch_ajax_data()

            raise ConnectionError(f"Error fetching device data: {err}") from err

    async def _fetch_ajax_data(self) -> dict[str, Any]:
        """Fetch JSON data from AJAX endpoint.

        Returns:
            Dictionary containing AJAX data

        Raises:
            ConnectionError: If request fails
            DataNotFoundError: If data structure is invalid
        """
        url = f"{AJAX_URL}?receiptLineKey={self._receipt_line_key}"

        try:
            _LOGGER.debug("Fetching AJAX data (POST): %s", url)

            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{DEVICE_URL}?receiptLineKey={self._receipt_line_key}",
            }

            async with self._session.post(url, headers=headers) as response:
                _LOGGER.debug("AJAX response status: %s", response.status)

                # Handle authentication failures
                if response.status in (401, 403):
                    _LOGGER.warning("AJAX endpoint returned %s - session expired", response.status)
                    raise aiohttp.ClientError(f"Session expired: {response.status}")

                if response.status == 500:
                    _LOGGER.warning("AJAX endpoint returned 500 (server overload)")
                    raise ConnectionError("Server overload (500)")

                if response.status != 200:
                    _LOGGER.error("Failed to fetch AJAX data: status %s", response.status)
                    raise ConnectionError(f"Failed to fetch AJAX data: {response.status}")

                json_data = await response.json()
                _LOGGER.debug("JSON response keys: %s", list(json_data.keys()) if isinstance(json_data, dict) else type(json_data))

                if "dataset" not in json_data:
                    raise DataNotFoundError("Invalid JSON structure: missing 'dataset'")

                dataset = json_data["dataset"]
                data = {}

                # Dataset can be a list or dict, handle both
                if isinstance(dataset, list):
                    # If dataset is a list, take the first element
                    if not dataset:
                        raise DataNotFoundError("Dataset list is empty")
                    dataset = dataset[0]
                    _LOGGER.debug("Dataset is a list, using first element")

                if not isinstance(dataset, dict):
                    _LOGGER.error("Dataset is not a dict after processing: %s", type(dataset))
                    raise DataNotFoundError(f"Invalid dataset type: {type(dataset)}")

                _LOGGER.debug("Dataset keys: %s", list(dataset.keys()))

                # Extract connectivity info
                data["connectable"] = dataset.get("connectable", False)
                data["connected"] = dataset.get("connected", False)
                data["online"] = dataset.get("online", False)

                # Extract last seen datetime
                last_seen = dataset.get("lastSeenDateTime")
                if last_seen:
                    try:
                        # Parse ISO format datetime
                        dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        data["last_seen"] = dt.isoformat()
                    except ValueError:
                        _LOGGER.debug("Failed to parse last_seen datetime: %s", last_seen)
                        data["last_seen"] = last_seen

                # Extract device history data (only first line = today)
                history = dataset.get("deviceDataHistory", {})
                codes = history.get("codes", [])
                lines = history.get("lines", [])

                if lines and len(lines) > 0:
                    # Cherche la ligne correspondant à la date du jour (YYYY-MM-DD)
                    today_str = datetime.now(timezone.utc).date().isoformat()
                    today_data = None

                    for line in lines:
                        if not line:
                            continue
                        first_col = str(line[0])
                        if first_col.startswith(today_str):
                            today_data = line
                            break

                    # Si pas de ligne pour aujourd'hui : définir des valeurs par défaut (zéros)
                    if today_data is None:
                        _LOGGER.debug("No history line for today (%s), setting default zeros", today_str)
                        data["data_date"] = today_str
                        data["regen_count"] = 0
                        data["power_outage"] = 0
                        data["water_use"] = 0
                        data["salt_alarm"] = 0
                    else:
                        # Map codes to values from today's line
                        for i, code in enumerate(codes):
                            if i < len(today_data):
                                value = today_data[i]

                                if code == "date":
                                    data["data_date"] = value
                                elif code == "regenCount":
                                    data["regen_count"] = value
                                elif code == "powerOutage":
                                    data["power_outage"] = value
                                elif code == "waterUse":
                                    data["water_use"] = value
                                elif code == "saltAlarm":
                                    data["salt_alarm"] = value

                _LOGGER.debug("AJAX data extracted: %s", data)
                return data

        except (ConnectionError, DataNotFoundError):
            raise
        except aiohttp.ClientError as err:
            raise ConnectionError(f"Connection error fetching AJAX data: {err}") from err
        except asyncio.TimeoutError as err:
            raise ConnectionError("Timeout fetching AJAX data") from err

    async def _fetch_html_data(self) -> dict[str, Any]:
        """Fetch device basic info from HTML page.

        Extracts only device name, serial number, and service date.
        Configuration parameters (hardness, pressure, etc.) are no longer
        available due to website changes.

        Returns:
            Dictionary containing device name, serial number, and service date

        Raises:
            ConnectionError: If request fails
            DataNotFoundError: If data structure is invalid
        """
        url = f"{DEVICE_URL}?receiptLineKey={self._receipt_line_key}"

        try:
            _LOGGER.debug("Fetching HTML data: %s", url)

            async with self._session.get(url) as response:
                _LOGGER.debug("HTML response status: %s", response.status)

                # Handle authentication failures
                if response.status in (401, 403):
                    _LOGGER.warning("HTML endpoint returned %s - session expired", response.status)
                    raise aiohttp.ClientError(f"Session expired: {response.status}")

                if response.status == 500:
                    _LOGGER.warning("HTML endpoint returned 500 (server overload)")
                    raise ConnectionError("Server overload (500)")

                if response.status != 200:
                    _LOGGER.error("Failed to fetch HTML data: status %s", response.status)
                    raise ConnectionError(f"Failed to fetch HTML data: {response.status}")

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                data = {}

                # Extract device name
                device_name_elem = soup.find("h1", class_="page-title")
                if device_name_elem:
                    data["device_name"] = device_name_elem.get_text(strip=True)

                # Extract serial number and service date from informations div
                info_div = soup.find("div", class_="informations")
                if info_div:
                    spans = info_div.find_all("span")
                    for span in spans:
                        text = span.get_text(strip=True)
                        if "N° série" in text:
                            # Extract serial: "N° série : 08K8-FJKL" -> "08K8-FJKL"
                            data["serial_number"] = text.split(":")[-1].strip()
                        elif "Mise en service le" in text:
                            # Extract date: "Mise en service le 04-06-2024" -> "04-06-2024"
                            date_str = text.split("le")[-1].strip()
                            # Convert DD-MM-YYYY to YYYY-MM-DD for date.fromisoformat()
                            try:
                                day, month, year = date_str.split("-")
                                data["service_date"] = f"{year}-{month}-{day}"
                            except ValueError:
                                _LOGGER.debug("Failed to parse service_date: %s", date_str)
                                data["service_date"] = date_str

                _LOGGER.debug("HTML data extracted: %s", data)
                return data

        except (ConnectionError, DataNotFoundError):
            raise
        except aiohttp.ClientError as err:
            raise ConnectionError(f"Connection error fetching HTML data: {err}") from err
        except asyncio.TimeoutError as err:
            raise ConnectionError("Timeout fetching HTML data") from err

    async def close(self) -> None:
        """Close the session properly.

        Note: In persistent session mode, this should only be called
        when the integration is unloaded, not after each polling.
        """
        if self._session and not self._session.closed:
            _LOGGER.info("Closing BWT MyService session")
            await self._session.close()
            # Allow 250ms for aiohttp to complete SSL shutdown and connection cleanup
            # Recommended by aiohttp docs to prevent "Unclosed client session" warnings
            await asyncio.sleep(0.25)
