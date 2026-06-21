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

SIGNAL_ASSET_ADDED = f"{DOMAIN}_asset_added"
EVENT_ALARM = f"{DOMAIN}_alarm"

QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

GERMAN_EXCHANGE_SUFFIXES = (".DE", ".F", ".SG", ".DU", ".HM", ".MU", ".BE")
MANUAL_WKN_SYMBOLS = {
    "A1JWVX": "META",
}
SUPPORTED_QUOTE_TYPES = {
    "EQUITY",
    "ETF",
    "MUTUALFUND",
    "CRYPTOCURRENCY",
    "CURRENCY",
    "INDEX",
}
