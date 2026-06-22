class FinancePortfolioCard extends HTMLElement {
  constructor() {
    super();
    this._rendered = false;
    this._settingsOpen = false;
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
            <button class="fp-tool" title="Einstellungen">
              <ha-icon icon="mdi:cog-outline"></ha-icon>
            </button>
          </div>
          <div class="fp-list"></div>
          <div class="fp-settings" hidden></div>
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
          grid-template-columns: minmax(0, 1fr) 42px 42px;
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
        .fp-tool {
          width: 42px;
          height: 40px;
          border: 0;
          border-radius: 20px;
          color: var(--primary-text-color);
          background: rgba(255,255,255,0.08);
          cursor: pointer;
          display: grid;
          place-items: center;
        }
        .fp-tool ha-icon {
          width: 20px;
        }
        .fp-list {
          display: grid;
          gap: 8px;
        }
        .fp-row {
          display: grid;
          grid-template-areas: "icon name day week month remove" "icon price day week month remove";
          grid-template-columns: 54px minmax(30px, 1fr) 64px 64px 64px 34px;
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
          min-width: 64px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 3px;
          padding: 0 5px;
          border-radius: 999px;
          color: white;
          font-size: 11px;
          font-weight: 700;
          line-height: 1;
          white-space: nowrap;
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
        .fp-settings {
          display: grid;
          gap: 10px;
          padding-top: 4px;
        }
        .fp-settings[hidden] {
          display: none;
        }
        .fp-settings-head {
          display: grid;
          grid-template-columns: 132px minmax(0, 1fr);
          gap: 8px;
          align-items: center;
        }
        .fp-settings-label {
          font-size: 12px;
          font-weight: 700;
          color: var(--primary-text-color);
        }
        .fp-notify-select {
          width: 100%;
          min-height: 38px;
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          padding: 5px 8px;
          color: var(--primary-text-color);
          background: var(--card-background-color);
          font: inherit;
          font-size: 12px;
          box-sizing: border-box;
        }
        .fp-alert-scroll {
          overflow-x: auto;
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 12px;
        }
        .fp-alert-table {
          width: 100%;
          min-width: 430px;
          border-collapse: collapse;
          font-size: 12px;
        }
        .fp-alert-table th,
        .fp-alert-table td {
          padding: 8px 6px;
          border-bottom: 1px solid rgba(255,255,255,0.07);
          text-align: center;
          white-space: nowrap;
        }
        .fp-alert-table th:first-child,
        .fp-alert-table td:first-child {
          text-align: left;
          min-width: 120px;
          max-width: 170px;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .fp-alert-table tr:last-child td {
          border-bottom: 0;
        }
        .fp-alert-table input {
          width: 18px;
          height: 18px;
          accent-color: rgba(25,135,84,0.95);
        }
        @media (max-width: 420px) {
          .fp-row {
            grid-template-columns: 46px minmax(20px, 1fr) 56px 56px 56px 28px;
            column-gap: 2px;
            padding: 8px 5px;
          }
          .fp-icon {
            width: 42px;
            height: 42px;
          }
          .fp-pill {
            min-width: 56px;
            font-size: 10px;
            padding: 0 3px;
            gap: 2px;
          }
          .fp-remove {
            width: 28px;
            height: 28px;
          }
          .fp-settings-head {
            grid-template-columns: 1fr;
          }
        }
      </style>
    `;
    this._rendered = true;
    this.querySelector(".fp-button")?.addEventListener("click", () => this.addAsset());
    this.querySelector(".fp-tool")?.addEventListener("click", () => this.toggleSettings());
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
    this.updateSettings(state, assets);
  }

  updateSettings(state, assets) {
    const settings = this.querySelector(".fp-settings");
    if (!settings) return;
    settings.hidden = !this._settingsOpen;
    if (!this._settingsOpen) return;

    const selectedServices = state?.attributes?.notify_services || [];
    const notifyServices = this.notifyServiceOptions();
    settings.innerHTML = `
      <div class="fp-settings-head">
        <div class="fp-settings-label">Push-Ziele</div>
        <select class="fp-notify-select" multiple size="${Math.min(Math.max(notifyServices.length, 2), 4)}">
          ${notifyServices.map((service) => `
            <option value="${this.escape(service)}" ${selectedServices.includes(service) ? "selected" : ""}>
              ${this.escape(service)}
            </option>
          `).join("")}
        </select>
      </div>
      <div class="fp-alert-scroll">
        <table class="fp-alert-table">
          <thead>
            <tr>
              <th>Aktie/ETF</th>
              <th>-10%</th>
              <th>-5%</th>
              <th>-1%</th>
              <th>1%</th>
              <th>5%</th>
              <th>10%</th>
            </tr>
          </thead>
          <tbody>
            ${assets.map((asset) => this.alertRow(asset)).join("")}
          </tbody>
        </table>
      </div>
    `;
    settings.querySelector(".fp-notify-select")?.addEventListener("change", (event) => {
      this.saveNotifyServices([...event.currentTarget.selectedOptions].map((option) => option.value));
    });
    settings.querySelectorAll("[data-alert-asset]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => this.saveAssetAlert(checkbox.dataset.alertAsset));
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
    return `<div class="fp-pill ${cssClass}" style="background:${color}" data-more-info="${entityId}"><span>${icon}</span><span>${safe.toFixed(1)}%</span></div>`;
  }

  alertRow(asset) {
    const label = this.escape(asset.name || asset.symbol || asset.asset_id);
    return `
      <tr>
        <td title="${label}">${label}</td>
        ${this.alertCell(asset, "down", 10)}
        ${this.alertCell(asset, "down", 5)}
        ${this.alertCell(asset, "down", 1)}
        ${this.alertCell(asset, "up", 1)}
        ${this.alertCell(asset, "up", 5)}
        ${this.alertCell(asset, "up", 10)}
      </tr>
    `;
  }

  alertCell(asset, direction, threshold) {
    const values = asset.alert?.[`${direction}_thresholds`] || [];
    const checked = asset.alert?.enabled !== false && values.map(Number).includes(threshold);
    return `
      <td>
        <input
          type="checkbox"
          data-alert-asset="${this.escape(asset.asset_id)}"
          data-alert-direction="${direction}"
          data-alert-threshold="${threshold}"
          ${checked ? "checked" : ""}
        />
      </td>
    `;
  }

  notifyServiceOptions() {
    const notifyServices = Object.keys(this._hass.services?.notify || {})
      .filter((service) => !["persistent_notification", "send_message"].includes(service))
      .map((service) => `notify.${service}`)
      .sort();
    const selected = this._hass.states[this.config.entity]?.attributes?.notify_services || [];
    return [...new Set([...selected, ...notifyServices])];
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

  toggleSettings() {
    this._settingsOpen = !this._settingsOpen;
    this.updateList();
  }

  async saveNotifyServices(notifyServices) {
    await this._hass.callService("finance_portfolio", "set_options", {
      notify_services: notifyServices,
    });
  }

  async saveAssetAlert(assetId) {
    const checkboxes = [...this.querySelectorAll(`[data-alert-asset="${assetId}"]`)];
    const upThresholds = [];
    const downThresholds = [];
    checkboxes.forEach((checkbox) => {
      if (!checkbox.checked) return;
      const threshold = Number(checkbox.dataset.alertThreshold);
      if (checkbox.dataset.alertDirection === "up") {
        upThresholds.push(threshold);
      } else {
        downThresholds.push(threshold);
      }
    });
    await this._hass.callService("finance_portfolio", "set_alert", {
      asset_id: assetId,
      enabled: upThresholds.length > 0 || downThresholds.length > 0,
      up_thresholds: upThresholds,
      down_thresholds: downThresholds,
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
