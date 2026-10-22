/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { router } from "@web/core/browser/router";

export class DebugSwitch extends Component {
    static template = "ts_debug_switch.debugswitch";

    setup(){
        this.isDebug = Boolean(odoo.debug);
        this.orm = useService("orm");

        // Checks for user access
        onWillStart(async () => {
            this.has_debug_access = await this.orm.call(
                "res.users", "has_group", 
                [user.userId], {group_ext_id: 'ts_debug_switch.group_debug_switch_access'})
                .then(function (has_debug_access){
                    return has_debug_access;
                });  
            });   
    }

    switchDebugMode(){
        // checks current debug mode and updates accordingly
        const isDebug = Boolean(odoo.debug);
        const isAssets = odoo.debug.includes("assets");
        const isTests = odoo.debug.includes("tests");

        const oppositeDebug = (isDebug || isAssets || isTests) ? 0 : 1;
        router.pushState({ debug: oppositeDebug }, { reload: true });
    }
}

export const systrayDebug = {
    Component:DebugSwitch,
};

registry.category("systray").add("ts_debug_switch.debugswitch", systrayDebug, { sequence: 2 });
