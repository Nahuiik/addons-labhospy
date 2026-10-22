/** @odoo-module **/
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { busService } from "@bus/services/bus_service";

const myService = {
    dependencies: ["bus_service"],

    start(env, { bus_service }) {
        bus_service.addChannel("custom-logout");

        bus_service.subscribe("notification", (payload) => {
              if (payload.type === "custom-logout") {
                this.myEventHandler(payload.payload);
              }

        });

        bus_service.addEventListener("connect", () => {
            console.log("Connected to bus service");
        });

        bus_service.start();
    },

     myEventHandler(event) {
        if (event.user_id === this._getCurrentUserId()) {
            console.log(`Logging out user with ID: ${event.user_id}`);
            window.location.href = "/web/session/logout";
        }
    },

    _getCurrentUserId() {
        return user.userId;
    },
};

registry.category("services").add("myService", myService);