"""Sensors for Finance Portfolio."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import FinancePortfolioRuntime
from .const import DOMAIN, SIGNAL_ASSET_ADDED


async def async_setup_entry(
    hass: HomeAssistant,
    _entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up portfolio sensors from a config entry."""
    runtime: FinancePortfolioRuntime = hass.data[DOMAIN]["runtime"]
    _async_add_portfolio_entities(hass, runtime, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    _config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up portfolio sensors."""
    runtime: FinancePortfolioRuntime = hass.data[DOMAIN]["runtime"]
    _async_add_portfolio_entities(hass, runtime, async_add_entities)


def _async_add_portfolio_entities(
    hass: HomeAssistant,
    runtime: FinancePortfolioRuntime,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add portfolio entities and subscribe to later asset additions."""
    entities: list[SensorEntity] = [PortfolioAssetsSensor(runtime)]
    for asset_id in runtime.assets:
        entities.extend(_asset_entities(runtime, asset_id))
    async_add_entities(entities)

    @callback
    def add_asset_entities(asset_id: str) -> None:
        async_add_entities(_asset_entities(runtime, asset_id))

    hass.data.setdefault(f"{DOMAIN}_unsubs", []).append(
        async_dispatcher_connect(hass, SIGNAL_ASSET_ADDED, add_asset_entities)
    )


def _asset_entities(runtime: FinancePortfolioRuntime, asset_id: str) -> list[SensorEntity]:
    return [
        PortfolioMetricSensor(runtime, asset_id, "price"),
        PortfolioMetricSensor(runtime, asset_id, "day"),
        PortfolioMetricSensor(runtime, asset_id, "week"),
        PortfolioMetricSensor(runtime, asset_id, "month"),
    ]


class PortfolioAssetsSensor(SensorEntity):
    """Master portfolio list sensor."""

    _attr_name = "Finance Portfolio Assets"
    _attr_unique_id = "finance_portfolio_assets"
    _attr_icon = "mdi:briefcase-variant"

    def __init__(self, runtime: FinancePortfolioRuntime) -> None:
        self.runtime = runtime
        self._unsub = None

    @property
    def native_value(self) -> StateType:
        return len(self.runtime.assets)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"assets": self.runtime.asset_summary()}

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(
            self.hass, f"{DOMAIN}_updated", self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()


class PortfolioMetricSensor(SensorEntity):
    """Per-asset metric sensor."""

    def __init__(self, runtime: FinancePortfolioRuntime, asset_id: str, metric: str) -> None:
        self.runtime = runtime
        self.asset_id = asset_id
        self.metric = metric
        self._unsub = None
        self._attr_unique_id = f"finance_portfolio_{asset_id}_{metric}"
        if metric != "price":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self.entity_id = self._entity_id()

    def _entity_id(self) -> str:
        suffix = {
            "price": "kurs_euro",
            "day": "tageskursveranderung_prozent",
            "week": "wochenkursveranderung_prozent",
            "month": "monatskursveranderung_prozent",
        }[self.metric]
        return f"sensor.finance_portfolio_{self.asset_id}_{suffix}"

    @property
    def name(self) -> str:
        asset = self.runtime.assets.get(self.asset_id, {})
        name = asset.get("name", self.asset_id)
        label = {
            "price": "Kurs Euro",
            "day": "Tageskursveranderung Prozent",
            "week": "Wochenkursveranderung Prozent",
            "month": "Monatskursveranderung Prozent",
        }[self.metric]
        return f"{name} {label}"

    @property
    def icon(self) -> str | None:
        asset = self.runtime.assets.get(self.asset_id, {})
        return asset.get("icon")

    @property
    def native_unit_of_measurement(self) -> str | None:
        return "EUR" if self.metric == "price" else PERCENTAGE

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return SensorDeviceClass.MONETARY if self.metric == "price" else None

    @property
    def native_value(self) -> StateType:
        quote = self.runtime.quotes.get(self.asset_id)
        asset = self.runtime.assets.get(self.asset_id, {})
        price = quote.price_eur if quote else None
        if self.metric == "price":
            return price
        if self.metric == "day":
            return quote.day_pct if quote else None
        start_key = "week_start" if self.metric == "week" else "month_start"
        start = asset.get(start_key)
        if price is None or not start:
            return None
        start = float(start)
        if start <= 0:
            return None
        return round(((price - start) / start) * 100, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        asset = self.runtime.assets.get(self.asset_id, {})
        quote = self.runtime.quotes.get(self.asset_id)
        return {
            "asset_id": self.asset_id,
            "wkn": asset.get("wkn"),
            "isin": asset.get("isin"),
            "query": asset.get("query"),
            "symbol": asset.get("symbol"),
            "source_currency": quote.source_currency if quote else None,
            "market_state": quote.market_state if quote else None,
            "peak_ref": asset.get("peak_ref"),
            "trough_ref": asset.get("trough_ref"),
            "last_alarm": asset.get("last_alarm"),
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = async_dispatcher_connect(
            self.hass, f"{DOMAIN}_updated", self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
