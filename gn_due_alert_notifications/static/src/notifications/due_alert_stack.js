/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { DueAlertCard } from "./due_alert_card";

export class DueAlertStack extends Component {
    static template = "gn_due_alert_notifications.DueAlertStack";
    static components = { DueAlertCard };
    static props = {};

    setup() {
        this.dueAlertBus = useService("gn_due_alert_bus");
        this.state = useState({
            cards: [],
            pendingCount: 0,
            maxVisible: 5,
            soundEnabled: false,
        });
        this._unsubscribe = null;
        onMounted(() => {
            this._unsubscribe = this.dueAlertBus.subscribe((payload) => {
                this._applyPayload(payload);
            });
        });
        onWillUnmount(() => {
            if (this._unsubscribe) {
                this._unsubscribe();
            }
        });
    }

    _applyPayload(payload) {
        if (!payload) {
            return;
        }
        this.state.cards = payload.cards || [];
        this.state.pendingCount = payload.pending_count || 0;
        this.state.maxVisible = payload.max_visible || 5;
        if (payload.sound_enabled && this.state.cards.length) {
            this._playSound();
        }
    }

    _playSound() {
        try {
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            gain.gain.value = 0.05;
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        } catch {
            // sin soporte de audio
        }
    }

    onCardClosed(cardId) {
        this.state.cards = this.state.cards.filter((c) => c.id !== cardId);
    }

    async onRefresh() {
        await this.dueAlertBus.reload();
    }
}

registry.category("main_components").add(
    "GnDueAlertStack",
    { Component: DueAlertStack }
);
