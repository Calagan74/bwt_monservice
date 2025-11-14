"""Constants for the BWT MonService integration."""
from datetime import timedelta

DOMAIN = "bwt_monservice"

# API URLs
BASE_URL = "https://www.bwt-monservice.com"
LOGIN_URL = f"{BASE_URL}/login"
DASHBOARD_URL = f"{BASE_URL}/dashboard"
DEVICE_URL = f"{BASE_URL}/device"
AJAX_URL = f"{BASE_URL}/device/ajaxChart"

# Default values
DEFAULT_SCAN_INTERVAL = 10  # minutes
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 1440

# Timeout settings
REQUEST_TIMEOUT = 30  # seconds

# Device info
MANUFACTURER = "BWT"
