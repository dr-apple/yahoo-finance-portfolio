"""Home Assistant 2026.8 compatibility tests."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.finance_portfolio import (
    FinancePortfolioRuntime,
    PortfolioQuote,
    _scan_interval,
    _serialize_scan_interval,
    _to_float,
    async_migrate_entry,
)
from custom_components.finance_portfolio.const import (
    DOMAIN,
    SERVICE_ADD_ASSET,
    SERVICE_REFRESH,
    SERVICE_REMOVE_ASSET,
    SERVICE_RESET_ALARM,
    SERVICE_SET_ALERT,
    SERVICE_SET_OPTIONS,
)


async def _load_assets(runtime: FinancePortfolioRuntime) -> None:
    runtime.assets = {
        "meta": {
            "name": "Meta",
            "symbol": "META",
            "week_start": 100,
            "month_start": 100,
        }
    }
    runtime.quotes = {
        "meta": PortfolioQuote(
            symbol="META",
            price_eur=110,
            day_pct=1.5,
            currency="EUR",
            source_price=110,
            source_currency="EUR",
            market_state="REGULAR",
            short_name="Meta",
            long_name="Meta Platforms",
        )
    }


def test_non_finite_numbers_are_rejected() -> None:
    """Yahoo NaN and infinity values never become Home Assistant states."""
    assert _to_float("nan") is None
    assert _to_float("inf") is None
    assert _to_float("12.5") == 12.5


def test_scan_interval_is_json_serializable() -> None:
    """YAML time periods are normalized before config entry storage."""
    stored = _serialize_scan_interval(timedelta(minutes=5))

    assert stored == 300
    assert json.dumps({"scan_interval": stored})
    assert _scan_interval(stored) == timedelta(minutes=5)


async def test_migration_repairs_timedelta_config_entry(hass: HomeAssistant) -> None:
    """Version 1 entries no longer retain a timedelta in storage data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Finance Portfolio",
        unique_id=DOMAIN,
        data={"scan_interval": timedelta(minutes=5)},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert entry.data["scan_interval"] == 300
    assert json.dumps(dict(entry.data))


async def test_setup_uses_stable_entity_ids_and_unloads_services(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """The config entry creates stable sensors and cleans up its services."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Finance Portfolio",
        unique_id=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(FinancePortfolioRuntime, "async_load", _load_assets),
        patch.object(FinancePortfolioRuntime, "async_start", new=AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 5
    assert hass.states.get("sensor.finance_portfolio_meta_kurs_euro") is not None

    services = (
        SERVICE_ADD_ASSET,
        SERVICE_REMOVE_ASSET,
        SERVICE_REFRESH,
        SERVICE_RESET_ALARM,
        SERVICE_SET_ALERT,
        SERVICE_SET_OPTIONS,
    )
    assert all(hass.services.has_service(DOMAIN, service) for service in services)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert all(not hass.services.has_service(DOMAIN, service) for service in services)


def test_alert_service_exposes_both_threshold_directions() -> None:
    """Service metadata matches the set_alert service schema."""
    with open("custom_components/finance_portfolio/services.yaml", encoding="utf-8") as file:
        services = yaml.safe_load(file)

    assert "up_thresholds" in services["set_alert"]["fields"]
    assert "down_thresholds" in services["set_alert"]["fields"]
    assert "down_thresholds" not in services["set_options"]["fields"]
    for field in ("up_thresholds", "down_thresholds"):
        options = services["set_alert"]["fields"][field]["selector"]["select"]["options"]
        assert all(isinstance(option["value"], str) for option in options)
