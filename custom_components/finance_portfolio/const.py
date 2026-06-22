"""Constants for Finance Portfolio."""

from __future__ import annotations

from datetime import timedelta
from logging import getLogger

DOMAIN = "finance_portfolio"
PLATFORMS = ["sensor"]

LOGGER = getLogger(__package__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
STORE_VERSION = 1
STORE_KEY = DOMAIN

SERVICE_ADD_ASSET = "add_asset"
SERVICE_REMOVE_ASSET = "remove_asset"
SERVICE_REFRESH = "refresh"
SERVICE_RESET_ALARM = "reset_alarm"
SERVICE_SET_ALERT = "set_alert"
SERVICE_SET_OPTIONS = "set_options"

SIGNAL_ASSET_ADDED = f"{DOMAIN}_asset_added"
SIGNAL_ASSET_REMOVED = f"{DOMAIN}_asset_removed"
EVENT_ALARM = f"{DOMAIN}_alarm"

CONF_NOTIFY_SERVICES = "notify_services"
CONF_DEFAULT_UP_THRESHOLDS = "default_up_thresholds"
CONF_DEFAULT_DOWN_THRESHOLDS = "default_down_thresholds"
CONF_ASSET_ALERTS = "asset_alerts"
CONF_ALERT_ENABLED = "enabled"
CONF_ALERT_UP_THRESHOLDS = "up_thresholds"
CONF_ALERT_DOWN_THRESHOLDS = "down_thresholds"

ALERT_THRESHOLD_OPTIONS = ("1", "5", "10")
DEFAULT_ALERT_THRESHOLDS = ["1"]

QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

GERMAN_EXCHANGE_SUFFIXES = (".DE", ".F", ".SG", ".DU", ".HM", ".MU", ".BE")
MANUAL_WKN_SYMBOLS = {
    "A1JWVX": "META",
    "A14Y6F": "GOOGL",
    "US02079K3059": "GOOGL",
}
SUPPORTED_QUOTE_TYPES = {
    "EQUITY",
    "ETF",
    "MUTUALFUND",
    "CRYPTOCURRENCY",
    "CURRENCY",
    "INDEX",
}
