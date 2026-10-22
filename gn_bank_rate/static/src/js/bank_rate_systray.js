/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

const systrayRegistry = registry.category("systray");

export class BankRateSystray extends Component {
    setup() {
        this.rpc = this.env.services.rpc || this.env.services.ajax;
        this.state = useState({
            time: "--:--",
            rate: null,
            currencySymbol: "$",
        });

        this._updateTime();
        this._fetchRate();

        this.clockInterval = setInterval(() => this._updateTime(), 60 * 1000);
        this.rateInterval = setInterval(() => this._fetchRate(), 5 * 60 * 1000);

        onWillUnmount(() => {
            clearInterval(this.clockInterval);
            clearInterval(this.rateInterval);
        });
    }

    async _fetchRate() {
        try {
            let data;
            if (typeof this.rpc === "function") {
                data = await this.rpc("/gn_bank_rate/info", {});
            } else if (this.rpc && typeof this.rpc.rpc === "function") {
                data = await this.rpc.rpc("/gn_bank_rate/info", {});
            } else {
                const response = await fetch("/gn_bank_rate/info", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: 1, jsonrpc: "2.0", method: "call", params: {} }),
                    credentials: "same-origin",
                });
                const payload = await response.json();
                data = payload.result;
            }
            if (data) {
                this.state.currencySymbol = data.currency_symbol || this.state.currencySymbol;
                if (typeof data.rate === "number") {
                    this.state.rate = data.rate;
                } else if (data.rate) {
                    const parsed = Number(data.rate);
                    this.state.rate = Number.isFinite(parsed) ? parsed : this.state.rate;
                }
                if (data.time) {
                    this._updateTime(data.time);
                }
            }
        } catch (err) {
            // silent
        }
    }

    _updateTime(isoString) {
        let now = isoString ? new Date(isoString) : new Date();
        if (Number.isNaN(now?.getTime())) {
            now = new Date();
        }
        this.state.time = now.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    get rateDisplay() {
        if (this.state.rate === null || this.state.rate === undefined) {
            return "--";
        }
        try {
            return new Intl.NumberFormat(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 4,
            }).format(Number(this.state.rate));
        } catch (err) {
            return String(this.state.rate);
        }
    }
}

BankRateSystray.template = "gn_bank_rate.BankRateSystray";
BankRateSystray.props = {};

systrayRegistry.add("gn_bank_rate.BankRateSystray", { Component: BankRateSystray }, { sequence: 1 });
