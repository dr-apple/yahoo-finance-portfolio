"""Config flow for Finance Portfolio."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    ALERT_THRESHOLD_OPTIONS,
    CONF_ALERT_DOWN_THRESHOLDS,
    CONF_ALERT_ENABLED,
    CONF_ALERT_UP_THRESHOLDS,
    CONF_ASSET_ALERTS,
    CONF_DEFAULT_DOWN_THRESHOLDS,
    CONF_DEFAULT_UP_THRESHOLDS,
    CONF_NOTIFY_SERVICES,
    DEFAULT_ALERT_THRESHOLDS,
    DOMAIN,
)


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

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return FinancePortfolioOptionsFlow(config_entry)


class FinancePortfolioOptionsFlow(config_entries.OptionsFlow):
    """Handle Finance Portfolio options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._asset_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["global_options", "asset_alert"],
        )

    async def async_step_global_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure global notification options."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            options[CONF_NOTIFY_SERVICES] = user_input[CONF_NOTIFY_SERVICES]
            options[CONF_DEFAULT_UP_THRESHOLDS] = user_input[
                CONF_DEFAULT_UP_THRESHOLDS
            ]
            options[CONF_DEFAULT_DOWN_THRESHOLDS] = user_input[
                CONF_DEFAULT_DOWN_THRESHOLDS
            ]
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICES,
                    default=options.get(CONF_NOTIFY_SERVICES, ""),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_DEFAULT_UP_THRESHOLDS,
                    default=options.get(
                        CONF_DEFAULT_UP_THRESHOLDS, DEFAULT_ALERT_THRESHOLDS
                    ),
                ): _threshold_selector(),
                vol.Optional(
                    CONF_DEFAULT_DOWN_THRESHOLDS,
                    default=options.get(
                        CONF_DEFAULT_DOWN_THRESHOLDS, DEFAULT_ALERT_THRESHOLDS
                    ),
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(step_id="global_options", data_schema=schema)

    async def async_step_asset_alert(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select an asset for alert options."""
        runtime = self.hass.data.get(DOMAIN, {}).get("runtime")
        assets = getattr(runtime, "assets", {})
        if not assets:
            return self.async_abort(reason="no_assets")

        if user_input is not None:
            self._asset_id = user_input["asset_id"]
            return await self.async_step_asset_alert_edit()

        options = [
            selector.SelectOptionDict(
                value=asset_id,
                label=f"{asset.get('name') or asset.get('symbol') or asset_id} ({asset_id})",
            )
            for asset_id, asset in sorted(
                assets.items(), key=lambda item: item[1].get("name", item[0])
            )
        ]
        schema = vol.Schema(
            {
                vol.Required("asset_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options)
                )
            }
        )
        return self.async_show_form(step_id="asset_alert", data_schema=schema)

    async def async_step_asset_alert_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure alert options for one asset."""
        if not self._asset_id:
            return await self.async_step_asset_alert()

        options = dict(self.config_entry.options)
        asset_alerts = dict(options.get(CONF_ASSET_ALERTS, {}))
        current = dict(asset_alerts.get(self._asset_id, {}))

        if user_input is not None:
            asset_alerts[self._asset_id] = {
                CONF_ALERT_ENABLED: user_input[CONF_ALERT_ENABLED],
                CONF_ALERT_UP_THRESHOLDS: user_input[CONF_ALERT_UP_THRESHOLDS],
                CONF_ALERT_DOWN_THRESHOLDS: user_input[
                    CONF_ALERT_DOWN_THRESHOLDS
                ],
            }
            options[CONF_ASSET_ALERTS] = asset_alerts
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ALERT_ENABLED,
                    default=current.get(CONF_ALERT_ENABLED, True),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_ALERT_UP_THRESHOLDS,
                    default=current.get(
                        CONF_ALERT_UP_THRESHOLDS,
                        options.get(
                            CONF_DEFAULT_UP_THRESHOLDS, DEFAULT_ALERT_THRESHOLDS
                        ),
                    ),
                ): _threshold_selector(),
                vol.Optional(
                    CONF_ALERT_DOWN_THRESHOLDS,
                    default=current.get(
                        CONF_ALERT_DOWN_THRESHOLDS,
                        options.get(
                            CONF_DEFAULT_DOWN_THRESHOLDS, DEFAULT_ALERT_THRESHOLDS
                        ),
                    ),
                ): _threshold_selector(),
            }
        )
        return self.async_show_form(step_id="asset_alert_edit", data_schema=schema)


def _threshold_selector() -> selector.SelectSelector:
    """Return the shared threshold selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=value, label=f"{value} %")
                for value in ALERT_THRESHOLD_OPTIONS
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )
