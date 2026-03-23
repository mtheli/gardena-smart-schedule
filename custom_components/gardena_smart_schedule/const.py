"""Constants for the Gardena Smart Schedule integration."""

from datetime import timedelta

DOMAIN = "gardena_smart_schedule"

AUTH_TOKEN_URL = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token"
SCHEDULE_API_BASE_URL = "https://smart.gardena.com"
GARDENA_API_BASE_URL = "https://api.smart.gardena.dev/v2"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_LOCATION_ID = "location_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 1440
TOKEN_REFRESH_BUFFER_SECONDS = 300
REQUEST_TIMEOUT = 10
