/** @odoo-module **/

import { registry } from "@web/core/registry";

export const dueAlertBusService = {
    dependencies: ["bus_service", "orm"],
    start(env, { bus_service, orm }) {
        const listeners = new Set();

        const notify = (payload) => {
            for (const fn of listeners) {
                fn(payload);
            }
        };

        bus_service.subscribe("gn_due_alert_notification", (payload) => {
            notify(payload);
        });

        const loadInitial = async () => {
            try {
                const payload = await orm.call(
                    "gn.due.alert.engine",
                    "get_initial_payload",
                    []
                );
                notify(payload);
            } catch {
                // usuario sin permiso o modulo no listo
            }
        };

        bus_service.start();
        loadInitial();

        return {
            subscribe(fn) {
                listeners.add(fn);
                return () => listeners.delete(fn);
            },
            reload: loadInitial,
        };
    },
};

registry.category("services").add("gn_due_alert_bus", dueAlertBusService);
