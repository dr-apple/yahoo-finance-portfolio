# Finance Portfolio

Home Assistant custom integration for a small Yahoo Finance based portfolio/watchlist.

It creates EUR-normalized price sensors, day/week/month percentage sensors, a master portfolio sensor, and an optional Lovelace card with add/remove controls.

## Features

- Add assets by free search, ISIN, WKN, name, or Yahoo symbol
- Automatic Yahoo search with fallback to direct Yahoo symbols
- Manual WKN mapping for symbols Yahoo does not resolve reliably
- EUR conversion for non-EUR quotes
- Per asset sensors:
  - price in EUR
  - day change %
  - week change %
  - month change %
- Master sensor with all card data:
  - `sensor.finance_portfolio_assets`
- Lovelace card:
  - input field for new assets
  - remove button per asset
  - clickable day/week/month pills
  - settings table for push targets and per-asset alert thresholds
- Configurable push alarms per asset for +1/+5/+10% and -1/-5/-10%
- Global mobile push targets via Home Assistant notify services

## Installation With HACS

1. Add this repository as a custom repository in HACS.
2. Category: `Integration`.
3. Install `Finance Portfolio`.
4. Restart Home Assistant.
5. Go to **Settings > Devices & services > Add integration**.
6. Search for **Finance Portfolio** and add it.

YAML import is also supported. Add this to `configuration.yaml` only if you prefer YAML:

```yaml
finance_portfolio:
```

Then restart Home Assistant once more.

## Lovelace Card

Add this dashboard resource:

```text
/finance_portfolio/finance-portfolio-card.js
```

Resource type:

```text
module
```

Then add this card to a dashboard:

```yaml
type: custom:finance-portfolio-card
entity: sensor.finance_portfolio_assets
```

After updating the card, hard refresh the browser or append a cache buster to the resource URL:

```text
/finance_portfolio/finance-portfolio-card.js?v=1
```

## Push Alarms

Open the Lovelace card settings via the cog button in the card.

1. Select one or more notify services in **Push-Ziele**:

```text
notify.mobile_app_dannys_iphone, notify.mobile_app_ipad
```

2. Set the active plus/minus thresholds per asset in the table:

```text
+1%, +5%, +10%
-1%, -5%, -10%
```

The integration still fires this Home Assistant event for automations:

```text
finance_portfolio_alarm
```

Event data includes:

```text
asset_id, name, symbol, direction, change_pct, threshold, reference, price_eur
```

## Services

### `finance_portfolio.add_asset`

Add or update an asset.

Examples:

```yaml
service: finance_portfolio.add_asset
data:
  query: Meta Platforms
  force: true
```

```yaml
service: finance_portfolio.add_asset
data:
  isin: US30303M1027
  name: Meta
  icon: mdi:facebook
  force: true
```

```yaml
service: finance_portfolio.add_asset
data:
  symbol: NVDA
  name: NVIDIA
  icon: mdi:memory
  force: true
```

Supported fields:

- `query`: free text search, ISIN, WKN, name, or Yahoo symbol
- `isin`: ISIN search value
- `wkn`: WKN search value
- `symbol`: direct Yahoo symbol
- `name`: optional display name
- `icon`: optional MDI icon
- `force`: overwrite existing asset with same ID

### `finance_portfolio.remove_asset`

```yaml
service: finance_portfolio.remove_asset
data:
  asset_id: a1jwvx
```

### `finance_portfolio.refresh`

Refresh all quotes immediately.

```yaml
service: finance_portfolio.refresh
```

### `finance_portfolio.reset_alarm`

Reset high/low alarm reference for an asset.

```yaml
service: finance_portfolio.reset_alarm
data:
  asset_id: a1jwvx
```

### `finance_portfolio.set_alert`

Configure push alarm thresholds for an asset.

```yaml
service: finance_portfolio.set_alert
data:
  asset_id: a1jwvx
  enabled: true
  up_thresholds:
    - 1
    - 5
    - 10
  down_thresholds:
    - 1
    - 5
    - 10
```

## Manual Mappings

Yahoo does not always resolve German WKNs. The integration contains a small manual mapping table in:

```text
custom_components/finance_portfolio/const.py
```

Example:

```python
MANUAL_WKN_SYMBOLS = {
    "A1JWVX": "META",
}
```

Add more mappings there when Yahoo search cannot resolve a WKN or ISIN reliably.

## Entities

For asset ID `a1jwvx`, the integration creates:

```text
sensor.finance_portfolio_a1jwvx_kurs_euro
sensor.finance_portfolio_a1jwvx_tageskursveranderung_prozent
sensor.finance_portfolio_a1jwvx_wochenkursveranderung_prozent
sensor.finance_portfolio_a1jwvx_monatskursveranderung_prozent
```

The master sensor is:

```text
sensor.finance_portfolio_assets
```

It exposes an `assets` attribute used by the custom Lovelace card.

## Repository Layout

```text
.
├── custom_components/
│   └── finance_portfolio/
│       ├── __init__.py
│       ├── config_flow.py
│       ├── const.py
│       ├── manifest.json
│       ├── sensor.py
│       ├── translations/
│       ├── services.yaml
│       └── www/
│           └── finance-portfolio-card.js
├── hacs.json
├── README.md
└── .gitignore
```
