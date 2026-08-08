"""Config flow for Finance Portfolio."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import DOMAIN


def _serializable_import(import_config: dict[str, Any]) -> dict[str, Any]:
    """Normalize YAML values before saving them in a config entry."""
    data = dict(import_config)
    interval = data.get(CONF_SCAN_INTERVAL)
    if hasattr(interval, "total_seconds"):
        data[CONF_SCAN_INTERVAL] = interval.total_seconds()
    return data


class FinancePortfolioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Finance Portfolio setup."""

    VERSION = 2

    async def async_step_import(self, import_config: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Import YAML configuration."""
        import_config = _serializable_import(import_config)
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=import_config)
        return self.async_create_entry(title="Finance Portfolio", data=import_config)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Create the integration from the UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Finance Portfolio", data={})
