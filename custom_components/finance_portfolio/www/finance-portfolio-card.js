class FinancePortfolioCard extends HTMLElement {
  constructor() {
    super();
    this._rendered = false;
  }

  setConfig(config) {
    this.config = {
      entity: "sensor.finance_portfolio_assets",
      title: "Finanzen",
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) this.render();
    this.updateList();
  }

  render() {
    if (!this._hass) return;
    this.innerHTML = `
      <ha-card>
        <div class="fp-wrap">
          <div class="fp-add">
            <input class="fp-input" placeholder="Name, ISIN, WKN oder Yahoo Symbol" />
            <button class="fp-button" title="Hinzufuegen">+</button>
          </div>
          <div class="fp-list"></div>
        </div>
      </ha-card>
      <style>
        .fp-wrap {
          display: grid;
          gap: 10px;
          padding: 10px;
        }
        .fp-add {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 42px;
          gap: 8px;
        }
        .fp-input {
          min-width: 0;
          height: 40px;
          border: 1px solid var(--divider-color);
          border-radius: 20px;
          padding: 0 14px;
          color: var(--primary-text-color);
          background: var(--card-background-color);
          font: inherit;
          outline: none;
        }
        .fp-button {
          width: 42px;
          height: 40px;
          border: 0;
          border-radius: 20px;
          color: white;
          background: rgba(25,135,84,0.95);
          font-size: 24px;
          cursor: pointer;
        }
        .fp-list {
          display: grid;
          gap: 8px;
        }
        .fp-row {
          display: grid;
          grid-template-areas: "icon name day week month remove" "icon price day week month remove";
          grid-template-columns: 54px minmax(30px, 1fr) 65px 65px 65px 34px;
          grid-template-rows: min-content min-content;
          column-gap: 3px;
          align-items: center;
          padding: 8px 7px;
          border-radius: 24px;
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.07);
        }
        .fp-icon {
          grid-area: icon;
          width: 48px;
          height: 48px;
          border-radius: 50%;
          display: grid;
          place-items: center;
          background: rgba(255,255,255,0.06);
          color: white;
        }
        .fp-name {
          grid-area: name;
          align-self: end;
          font-size: 12px;
          font-weight: 700;
          line-height: 1.1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .fp-price {
          grid-area: price;
          align-self: start;
          font-size: 12px;
          color: rgba(255,255,255,0.78);
          line-height: 1.1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .fp-pill {
          height: 32px;
          min-width: 65px;
          display: grid;
          place-items: center;
          padding: 0 6px;
          border-radius: 999px;
          color: white;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          box-sizing: border-box;
        }
        .fp-day { grid-area: day; }
        .fp-week { grid-area: week; }
        .fp-month { grid-area: month; }
        .fp-remove {
          grid-area: remove;
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          border: 0;
          border-radius: 50%;
          color: rgba(255,255,255,0.82);
          background: rgba(220,53,69,0.18);
          cursor: pointer;
          padding: 0;
        }
        .fp-remove ha-icon {
          width: 18px;
          color: currentColor;
        }
        .fp-remove:hover {
          color: white;
          background: rgba(220,53,69,0.75);
        }
        @media (max-width: 420px) {
          .fp-row {
            grid-template-columns: 48px minmax(20px, 1fr) 54px 54px 54px 30px;
          }
          .fp-pill {
            min-width: 54px;
            font-size: 10px;
          }
          .fp-remove {
            width: 28px;
            height: 28px;
          }
        }
      </style>
    `;
    this._rendered = true;
    this.querySelector(".fp-button")?.addEventListener("click", () => this.addAsset());
    this.querySelector(".fp-input")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") this.addAsset();
    });
  }

  updateList() {
    if (!this._hass || !this._rendered) return;
    const state = this._hass.states[this.config.entity];
    const assets = state?.attributes?.assets || [];
    const list = this.querySelector(".fp-list");
    if (!list) return;
    list.innerHTML = assets.map((asset) => this.assetHtml(asset)).join("");
    list.querySelectorAll("[data-more-info]").forEach((element) => {
      element.addEventListener("click", () => this.moreInfo(element.dataset.moreInfo));
    });
    list.querySelectorAll("[data-remove-asset]").forEach((element) => {
      element.addEventListener("click", (event) => {
        event.stopPropagation();
        this.removeAsset(element.dataset.removeAsset, element.dataset.removeName);
      });
    });
  }

  assetHtml(asset) {
    const price = this.formatPrice(asset.price_eur);
    return `
      <div class="fp-row" data-more-info="${asset.price_entity}">
        <ha-icon class="fp-icon" icon="${asset.icon || "mdi:finance"}"></ha-icon>
        <div class="fp-name">${this.escape(asset.name || asset.symbol || asset.asset_id)}</div>
        <div class="fp-price">${price}</div>
        ${this.pill("fp-day", asset.day_pct, asset.day_entity)}
        ${this.pill("fp-week", asset.week_pct, asset.week_entity)}
        ${this.pill("fp-month", asset.month_pct, asset.month_entity)}
        <button
          class="fp-remove"
          title="Entfernen"
          data-remove-asset="${this.escape(asset.asset_id)}"
          data-remove-name="${this.escape(asset.name || asset.symbol || asset.asset_id)}"
        >
          <ha-icon icon="mdi:trash-can-outline"></ha-icon>
        </button>
      </div>
    `;
  }

  pill(cssClass, value, entityId) {
    const numeric = Number(value);
    const safe = Number.isFinite(numeric) ? numeric : 0;
    const icon = safe > 0 ? "↗" : safe < 0 ? "↘" : "→";
    const color = safe > 0
      ? "rgba(25,135,84,0.95)"
      : safe < 0
        ? "rgba(220,53,69,0.95)"
        : "rgba(13,110,253,0.95)";
    return `<div class="fp-pill ${cssClass}" style="background:${color}" data-more-info="${entityId}">${icon} ${safe.toFixed(2)} %</div>`;
  }

  formatPrice(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "- EUR";
    return `${numeric.toFixed(2)} EUR`;
  }

  async addAsset() {
    const input = this.querySelector(".fp-input");
    const raw = input?.value?.trim();
    if (!raw) return;
    const data = { query: raw };
    input.disabled = true;
    try {
      await this._hass.callService("finance_portfolio", "add_asset", data);
      input.value = "";
    } finally {
      input.disabled = false;
    }
  }

  async removeAsset(assetId, name) {
    if (!assetId) return;
    const label = name || assetId;
    if (!confirm(`${label} entfernen?`)) return;
    await this._hass.callService("finance_portfolio", "remove_asset", {
      asset_id: assetId,
    });
  }

  moreInfo(entityId) {
    if (!entityId) return;
    const event = new Event("hass-more-info", { bubbles: true, composed: true });
    event.detail = { entityId };
    this.dispatchEvent(event);
  }

  escape(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("finance-portfolio-card", FinancePortfolioCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "finance-portfolio-card",
  name: "Finance Portfolio Card",
  description: "Dynamische Wertpapierliste mit freier Suche",
});
