"""Config flow for Finance Portfolio."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class FinancePortfolioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Finance Portfolio setup."""

    VERSION = 1

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Import YAML configuration."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(updates=import_config)
        return self.async_create_entry(title="Finance Portfolio", data=import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the integration from the UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Finance Portfolio", data={})
