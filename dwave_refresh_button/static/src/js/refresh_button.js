import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Tiny systray icon that forces a full client reload.
 */
class RefreshSystray extends Component {
    setup() {
        this.action = useService("action");
    }
    onClick() {
        this.action.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}
RefreshSystray.template = "refresh_button.RefreshSystray";

// Register in the systray (sequence decides position; 90 ⇒ just before the user‑menu)
registry.category("systray").add("refresh_systray", {
    Component: RefreshSystray,
    sequence: 90,
});