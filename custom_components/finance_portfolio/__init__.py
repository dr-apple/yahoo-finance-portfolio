"""Finance Portfolio integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_ALARM,
    GERMAN_EXCHANGE_SUFFIXES,
    LOGGER,
    MANUAL_WKN_SYMBOLS,
    QUOTE_URL,
    SEARCH_URL,
    SERVICE_ADD_ASSET,
    SERVICE_REFRESH,
    SERVICE_REMOVE_ASSET,
    SERVICE_RESET_ALARM,
    SIGNAL_ASSET_ADDED,
    STORE_KEY,
    STORE_VERSION,
    SUPPORTED_QUOTE_TYPES,
)

REQUEST_TIMEOUT = 20
MAX_LINE_SIZE = 8190 * 5
INITIAL_URL = "https://finance.yahoo.com/quote/NQ%3DF/"
CONSENT_HOST = "consent.yahoo.com"
GET_CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"
INITIAL_REQUEST_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0",
}
USER_AGENTS_FOR_XHR = [
    "Mozilla/5.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
]
XHR_REQUEST_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "accept-encoding": "gzip,deflate,br,zstd",
    "accept-language": "en-US,en;q=0.9",
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ADD_ASSET_SCHEMA = vol.Schema(
    {
        vol.Optional("wkn"): cv.string,
        vol.Optional("isin"): cv.string,
        vol.Optional("query"): cv.string,
        vol.Optional("symbol"): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ICON): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    }
)

REMOVE_ASSET_SCHEMA = vol.Schema({vol.Required("asset_id"): cv.string})
RESET_ALARM_SCHEMA = vol.Schema({vol.Required("asset_id"): cv.string})


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "asset"


def _now_iso() -> str:
    return dt_util.utcnow().isoformat()


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class PortfolioQuote:
    """Current quote values normalized to EUR."""

    symbol: str
    price_eur: float | None
    day_pct: float | None
    currency: str | None
    source_price: float | None
    source_currency: str | None
    market_state: str | None
    short_name: str | None
    long_name: str | None
    error: str | None = None


class FinancePortfolioRuntime:
    """Runtime state and Yahoo access for the portfolio."""

    def __init__(self, hass: HomeAssistant, scan_interval) -> None:
        self.hass = hass
        self.scan_interval = scan_interval
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.assets: dict[str, dict[str, Any]] = {}
        self.quotes: dict[str, PortfolioQuote] = {}
        self._cookies: SimpleCookie[str] | None = None
        self._crumb: str | None = None
        self._preferred_user_agent: str | None = None
        self._unsub_interval = None
        self._refresh_lock = asyncio.Lock()

    async def async_load(self) -> None:
        data = await self.store.async_load()
        self.assets = dict((data or {}).get("assets", {}))

    async def async_save(self) -> None:
        await self.store.async_save({"assets": self.assets})

    async def async_start(self) -> None:
        await self.async_refresh()
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_interval_refresh, self.scan_interval
        )

    async def async_stop(self) -> None:
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None

    async def _async_interval_refresh(self, _now) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        async with self._refresh_lock:
            await self._async_fetch_quotes()
            changed = self._update_period_refs_and_alarm_state()
            if changed:
                await self.async_save()
            async_dispatcher_send(self.hass, f"{DOMAIN}_updated")

    async def async_add_asset(
        self,
        *,
        wkn: str | None = None,
        isin: str | None = None,
        query: str | None = None,
        symbol: str | None = None,
        name: str | None = None,
        icon: str | None = None,
        force: bool = False,
    ) -> str:
        search_text = (query or isin or wkn or "").strip()
        if not search_text and not symbol:
            raise ValueError("query, isin, wkn oder symbol muss gesetzt sein")

        manual_symbol = MANUAL_WKN_SYMBOLS.get(search_text.upper()) if search_text else None
        if manual_symbol and not symbol:
            symbol = manual_symbol

        try:
            found = await self._async_resolve_asset(search_text=search_text, symbol=symbol)
        except ValueError:
            if symbol or not search_text:
                raise
            LOGGER.info(
                "No Yahoo search result for %s, retrying the input as Yahoo symbol",
                search_text,
            )
            found = await self._async_resolve_asset(search_text=None, symbol=search_text)
        yahoo_symbol = found["symbol"].upper()
        asset_id = _slugify(wkn or isin or query or yahoo_symbol)

        if asset_id in self.assets and not force:
            raise ValueError(f"{asset_id} ist bereits vorhanden")

        self.assets[asset_id] = {
            "asset_id": asset_id,
            "wkn": (wkn or "").upper(),
            "isin": (isin or "").upper(),
            "query": query or "",
            "symbol": yahoo_symbol,
            "name": name or found.get("name") or yahoo_symbol,
            "icon": icon or _default_icon(found.get("quote_type")),
            "quote_type": found.get("quote_type"),
            "exchange": found.get("exchange"),
            "created_at": _now_iso(),
            "week_start": None,
            "week_key": None,
            "month_start": None,
            "month_key": None,
            "peak_ref": None,
            "trough_ref": None,
            "last_alarm": None,
            "last_alarm_price": None,
        }
        await self.async_save()
        await self.async_refresh()
        async_dispatcher_send(self.hass, SIGNAL_ASSET_ADDED, asset_id)
        return asset_id

    async def async_remove_asset(self, asset_id: str) -> None:
        asset_id = _slugify(asset_id)
        if asset_id not in self.assets:
            raise ValueError(f"{asset_id} wurde nicht gefunden")
        self.assets.pop(asset_id)
        self.quotes.pop(asset_id, None)
        await self.async_save()
        async_dispatcher_send(self.hass, f"{DOMAIN}_updated")

    async def async_reset_alarm(self, asset_id: str) -> None:
        asset_id = _slugify(asset_id)
        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError(f"{asset_id} wurde nicht gefunden")
        quote = self.quotes.get(asset_id)
        price = quote.price_eur if quote else None
        asset["peak_ref"] = price
        asset["trough_ref"] = price
        asset["last_alarm"] = None
        asset["last_alarm_price"] = None
        await self.async_save()
        async_dispatcher_send(self.hass, f"{DOMAIN}_updated")

    async def _async_resolve_asset(
        self, *, search_text: str | None, symbol: str | None
    ) -> dict[str, Any]:
        if symbol:
            data = await self._async_quote_symbols([symbol.upper()])
            item = data.get(symbol.upper())
            if not item:
                raise ValueError(
                    f"Keine Yahoo-Finance-Referenz fuer Symbol {symbol.upper()} gefunden"
                )
            return {
                "symbol": symbol.upper(),
                "name": item.get("shortName") or item.get("longName") or symbol.upper(),
                "quote_type": item.get("quoteType"),
                "exchange": item.get("exchange"),
            }

        session = async_get_clientsession(self.hass)
        await self._async_ensure_yahoo_auth()
        async with session.get(
            SEARCH_URL,
            params={
                "q": search_text,
                "quotesCount": 12,
                "newsCount": 0,
                "enableFuzzyQuery": "true",
            },
            headers=self._yahoo_headers(),
            cookies=self._cookies,
            timeout=20,
            max_line_size=MAX_LINE_SIZE,
            max_field_size=MAX_LINE_SIZE,
        ) as response:
            response.raise_for_status()
            payload = await response.json()

        quotes = payload.get("quotes") or []
        candidates = []
        for item in quotes:
            quote_type = item.get("quoteType")
            yahoo_symbol = item.get("symbol")
            if not yahoo_symbol or quote_type not in SUPPORTED_QUOTE_TYPES:
                continue
            candidates.append(item)

        if not candidates:
            raise ValueError(f"Keine Yahoo-Finance-Referenz fuer {search_text} gefunden")

        def score(item: dict[str, Any]) -> tuple[int, int, str]:
            yahoo_symbol = str(item.get("symbol", "")).upper()
            exchange = str(item.get("exchange", "")).upper()
            eur_hint = 1 if yahoo_symbol.endswith(GERMAN_EXCHANGE_SUFFIXES) else 0
            german_hint = 1 if exchange in {"GER", "FRA", "STU", "DUS", "MUN", "HAN"} else 0
            return (eur_hint, german_hint, yahoo_symbol)

        best = sorted(candidates, key=score, reverse=True)[0]
        return {
            "symbol": best["symbol"],
            "name": best.get("shortname") or best.get("longname") or best["symbol"],
            "quote_type": best.get("quoteType"),
            "exchange": best.get("exchange"),
        }

    async def _async_fetch_quotes(self) -> None:
        symbols = [asset["symbol"] for asset in self.assets.values()]
        if not symbols:
            self.quotes = {}
            return

        quote_data = await self._async_quote_symbols(symbols)
        conversion_symbols = set()
        for item in quote_data.values():
            currency = item.get("currency") or item.get("financialCurrency")
            if currency and currency != "EUR":
                conversion_symbols.add(f"{currency}EUR=X")

        conversion_data = await self._async_quote_symbols(sorted(conversion_symbols)) if conversion_symbols else {}

        new_quotes: dict[str, PortfolioQuote] = {}
        for asset_id, asset in self.assets.items():
            symbol = asset["symbol"]
            item = quote_data.get(symbol)
            if not item:
                new_quotes[asset_id] = PortfolioQuote(
                    symbol=symbol,
                    price_eur=None,
                    day_pct=None,
                    currency="EUR",
                    source_price=None,
                    source_currency=None,
                    market_state=None,
                    short_name=None,
                    long_name=None,
                    error="no_data",
                )
                continue

            source_price = _to_float(item.get("regularMarketPrice"))
            previous_close = _to_float(item.get("regularMarketPreviousClose"))
            source_currency = item.get("currency") or item.get("financialCurrency") or "EUR"
            factor = 1.0
            if source_currency != "EUR":
                conversion = conversion_data.get(f"{source_currency}EUR=X") or {}
                factor = _to_float(conversion.get("regularMarketPrice")) or 1.0

            price_eur = source_price * factor if source_price is not None else None
            previous_eur = previous_close * factor if previous_close is not None else None
            day_pct = None
            if price_eur is not None and previous_eur and previous_eur > 0:
                day_pct = round(((price_eur - previous_eur) / previous_eur) * 100, 2)

            new_quotes[asset_id] = PortfolioQuote(
                symbol=symbol,
                price_eur=round(price_eur, 4) if price_eur is not None else None,
                day_pct=day_pct,
                currency="EUR",
                source_price=source_price,
                source_currency=source_currency,
                market_state=item.get("marketState"),
                short_name=item.get("shortName"),
                long_name=item.get("longName"),
            )

        self.quotes = new_quotes

    async def _async_quote_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        payload = await self._async_fetch_quote_payload(symbols)
        finance = payload.get("finance") or {}
        error = finance.get("error")
        if error and error.get("code") == "Unauthorized":
            self._reset_yahoo_auth()
            payload = await self._async_fetch_quote_payload(symbols)
        result = payload.get("quoteResponse", {}).get("result", [])
        return {str(item.get("symbol")).upper(): item for item in result if item.get("symbol")}

    async def _async_fetch_quote_payload(self, symbols: list[str]) -> dict[str, Any]:
        await self._async_ensure_yahoo_auth()
        session = async_get_clientsession(self.hass)
        params = {"symbols": ",".join(symbols)}
        if self._crumb:
            params["crumb"] = self._crumb
        async with session.get(
            QUOTE_URL,
            params=params,
            headers=self._yahoo_headers(),
            cookies=self._cookies,
            timeout=20,
            max_line_size=MAX_LINE_SIZE,
            max_field_size=MAX_LINE_SIZE,
        ) as response:
            if response.status == HTTPStatus.UNAUTHORIZED:
                return await response.json()
            response.raise_for_status()
            return await response.json()

    def _reset_yahoo_auth(self) -> None:
        self._cookies = None
        self._crumb = None
        self._preferred_user_agent = None

    def _yahoo_headers(self) -> dict[str, str]:
        user_agent = self._preferred_user_agent or USER_AGENTS_FOR_XHR[0]
        return {**XHR_REQUEST_HEADERS, "user-agent": user_agent}

    async def _async_ensure_yahoo_auth(self) -> None:
        if self._crumb and self._cookies:
            return
        if not await self._async_initial_navigation(INITIAL_URL):
            return
        await self._async_get_crumb()

    async def _async_initial_navigation(self, url: str) -> bool:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                url,
                headers=INITIAL_REQUEST_HEADERS,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                max_line_size=MAX_LINE_SIZE,
                max_field_size=MAX_LINE_SIZE,
            ) as response:
                if response.status != HTTPStatus.OK:
                    LOGGER.warning(
                        "Yahoo initial navigation failed: status=%s reason=%s",
                        response.status,
                        response.reason,
                    )
                    return False
                if response.cookies:
                    self._cookies = response.cookies
                if response.url.host.lower() != CONSENT_HOST:
                    return True
                content = await response.text()
                return await self._async_process_yahoo_consent(content, response.url)
        except (TimeoutError, aiohttp.ClientError) as err:
            LOGGER.warning("Yahoo initial navigation failed: %s", err)
            return False

    async def _async_process_yahoo_consent(self, content: str, post_url) -> bool:
        session = async_get_clientsession(self.hass)
        pattern = r'<input.*?type="hidden".*?name="(.*?)".*?value="(.*?)".*?>'
        form_data = {"reject": "reject", **dict(re.findall(pattern, content))}
        try:
            async with session.post(
                post_url,
                data=form_data,
                headers=INITIAL_REQUEST_HEADERS,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                max_line_size=MAX_LINE_SIZE,
                max_field_size=MAX_LINE_SIZE,
            ) as response:
                if response.status != HTTPStatus.OK:
                    LOGGER.warning(
                        "Yahoo consent post failed: status=%s reason=%s",
                        response.status,
                        response.reason,
                    )
                    return False
                if response.cookies:
                    self._cookies = response.cookies
                return True
        except (TimeoutError, aiohttp.ClientError) as err:
            LOGGER.warning("Yahoo consent post failed: %s", err)
            return False

    async def _async_get_crumb(self) -> None:
        session = async_get_clientsession(self.hass)
        for user_agent in USER_AGENTS_FOR_XHR:
            headers = {**XHR_REQUEST_HEADERS, "user-agent": user_agent}
            try:
                async with session.get(
                    GET_CRUMB_URL,
                    headers=headers,
                    cookies=self._cookies,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    max_line_size=MAX_LINE_SIZE,
                    max_field_size=MAX_LINE_SIZE,
                ) as response:
                    if response.status == HTTPStatus.OK:
                        crumb = await response.text()
                        if crumb:
                            self._crumb = crumb
                            self._preferred_user_agent = user_agent
                            return
                    if response.status != 429:
                        LOGGER.warning(
                            "Yahoo crumb request failed: status=%s reason=%s",
                            response.status,
                            response.reason,
                        )
                        return
            except (TimeoutError, aiohttp.ClientError) as err:
                LOGGER.warning("Yahoo crumb request failed: %s", err)
                return

    def _update_period_refs_and_alarm_state(self) -> bool:
        changed = False
        now = dt_util.now()
        week_key = f"{now.isocalendar().year}-{now.isocalendar().week:02d}"
        month_key = f"{now.year}-{now.month:02d}"

        for asset_id, asset in self.assets.items():
            quote = self.quotes.get(asset_id)
            price = quote.price_eur if quote else None
            if price is None or price <= 0:
                continue

            if asset.get("week_key") != week_key or not asset.get("week_start"):
                asset["week_key"] = week_key
                asset["week_start"] = price
                changed = True
            if asset.get("month_key") != month_key or not asset.get("month_start"):
                asset["month_key"] = month_key
                asset["month_start"] = price
                changed = True
            if not asset.get("peak_ref") or not asset.get("trough_ref"):
                asset["peak_ref"] = price
                asset["trough_ref"] = price
                changed = True
                continue

            peak = float(asset["peak_ref"])
            trough = float(asset["trough_ref"])
            cooldown_ok = True
            last_alarm = asset.get("last_alarm")
            if last_alarm:
                last_dt = dt_util.parse_datetime(last_alarm)
                if last_dt is not None:
                    cooldown_ok = (now - last_dt).total_seconds() >= 15 * 60

            up_pct = ((price - trough) / trough) * 100 if trough > 0 else 0
            down_pct = ((price - peak) / peak) * 100 if peak > 0 else 0
            direction = None
            change_pct = None
            reference = None
            if price >= trough * 1.01 and cooldown_ok:
                direction = "up"
                change_pct = round(up_pct, 2)
                reference = trough
            elif price <= peak * 0.99 and cooldown_ok:
                direction = "down"
                change_pct = round(down_pct, 2)
                reference = peak

            if direction:
                asset["peak_ref"] = price
                asset["trough_ref"] = price
                asset["last_alarm"] = now.isoformat()
                asset["last_alarm_price"] = price
                self.hass.bus.async_fire(
                    EVENT_ALARM,
                    {
                        "asset_id": asset_id,
                        "name": asset.get("name"),
                        "symbol": asset.get("symbol"),
                        "direction": direction,
                        "change_pct": change_pct,
                        "reference": reference,
                        "price_eur": price,
                    },
                )
                changed = True
            else:
                if price > peak:
                    asset["peak_ref"] = price
                    changed = True
                if price < trough:
                    asset["trough_ref"] = price
                    changed = True

        return changed

    def asset_summary(self) -> list[dict[str, Any]]:
        result = []
        for asset_id, asset in sorted(self.assets.items(), key=lambda x: x[1].get("name", x[0])):
            quote = self.quotes.get(asset_id)
            price = quote.price_eur if quote else None
            week_start = _to_float(asset.get("week_start"))
            month_start = _to_float(asset.get("month_start"))
            result.append(
                {
                    "asset_id": asset_id,
                    "name": asset.get("name"),
                    "wkn": asset.get("wkn"),
                    "isin": asset.get("isin"),
                    "query": asset.get("query"),
                    "symbol": asset.get("symbol"),
                    "icon": asset.get("icon"),
                    "price_entity": f"sensor.finance_portfolio_{asset_id}_kurs_euro",
                    "day_entity": f"sensor.finance_portfolio_{asset_id}_tageskursveranderung_prozent",
                    "week_entity": f"sensor.finance_portfolio_{asset_id}_wochenkursveranderung_prozent",
                    "month_entity": f"sensor.finance_portfolio_{asset_id}_monatskursveranderung_prozent",
                    "price_eur": price,
                    "day_pct": quote.day_pct if quote else None,
                    "week_pct": round(((price - week_start) / week_start) * 100, 2) if price and week_start else None,
                    "month_pct": round(((price - month_start) / month_start) * 100, 2) if price and month_start else None,
                    "peak_ref": asset.get("peak_ref"),
                    "trough_ref": asset.get("trough_ref"),
                    "last_alarm": asset.get("last_alarm"),
                    "market_state": quote.market_state if quote else None,
                    "source_currency": quote.source_currency if quote else None,
                }
            )
        return result


def _default_icon(quote_type: str | None) -> str:
    if quote_type == "CRYPTOCURRENCY":
        return "mdi:currency-btc"
    if quote_type in {"ETF", "MUTUALFUND"}:
        return "mdi:earth"
    if quote_type == "CURRENCY":
        return "mdi:cash-sync"
    return "mdi:finance"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Finance Portfolio from YAML."""
    static_path = Path(__file__).parent / "www"
    if static_path.exists():
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/finance_portfolio",
                    str(static_path),
                    cache_headers=True,
                )
            ]
        )

    conf = config.get(DOMAIN, {})
    if conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=dict(conf),
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up Finance Portfolio from a config entry."""
    conf = dict(entry.data)
    runtime = FinancePortfolioRuntime(
        hass, conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    await runtime.async_load()
    hass.data.setdefault(DOMAIN, {})["runtime"] = runtime

    async def handle_add(call: ServiceCall) -> None:
        current_runtime = hass.data[DOMAIN]["runtime"]
        try:
            asset_id = await current_runtime.async_add_asset(**call.data)
            await _notify(
                hass,
                "Finance Portfolio",
                f"Wertpapier {asset_id} wurde hinzugefuegt.",
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unable to add portfolio asset")
            await _notify(hass, "Finance Portfolio Fehler", str(err))

    async def handle_remove(call: ServiceCall) -> None:
        current_runtime = hass.data[DOMAIN]["runtime"]
        try:
            await current_runtime.async_remove_asset(call.data["asset_id"])
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unable to remove portfolio asset")
            await _notify(hass, "Finance Portfolio Fehler", str(err))

    async def handle_refresh(_call: ServiceCall) -> None:
        await hass.data[DOMAIN]["runtime"].async_refresh()

    async def handle_reset_alarm(call: ServiceCall) -> None:
        current_runtime = hass.data[DOMAIN]["runtime"]
        try:
            await current_runtime.async_reset_alarm(call.data["asset_id"])
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unable to reset portfolio alarm")
            await _notify(hass, "Finance Portfolio Fehler", str(err))

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_ASSET):
        hass.services.async_register(DOMAIN, SERVICE_ADD_ASSET, handle_add, schema=ADD_ASSET_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REMOVE_ASSET, handle_remove, schema=REMOVE_ASSET_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)
        hass.services.async_register(DOMAIN, SERVICE_RESET_ALARM, handle_reset_alarm, schema=RESET_ALARM_SCHEMA)

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await runtime.async_start()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload Finance Portfolio."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    runtime: FinancePortfolioRuntime | None = hass.data.get(DOMAIN, {}).get("runtime")
    if unload_ok and runtime:
        await runtime.async_stop()
        hass.data[DOMAIN].pop("runtime", None)
    return unload_ok


async def _notify(hass: HomeAssistant, title: str, message: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message},
        blocking=False,
    )
