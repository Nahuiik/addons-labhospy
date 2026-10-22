/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { useService, useBus } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";
import { rpcErrorMessage } from "../dashboard/dashboard_utils";
import { CxcPartnerListBanner } from "./cxc_partner_list_banner";

export class CxcPartnerListRenderer extends ListRenderer {
    static template = "gn_customer_due_alerts.CxcPartnerListRenderer";
    static components = {
        ...ListRenderer.components,
        CxcPartnerListBanner,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dashboardState = useState({
            loading: true,
            error: null,
            data: null,
        });
        this.onReloadDashboard = () => this.reloadDashboard();

        onWillStart(async () => {
            await this.reloadDashboard();
        });

        if (this.env.searchModel) {
            useBus(this.env.searchModel, "update", () => {
                this.reloadDashboard();
            });
        }
    }

    get isGroupedView() {
        return this.props.list.isGrouped;
    }

    get allGroupsExpanded() {
        const list = this.props.list;
        return list.isGrouped && list.groups.every((group) => !group.isFolded);
    }

    async reloadDashboard() {
        this.dashboardState.loading = true;
        this.dashboardState.error = null;
        try {
            const domain = this.env.searchModel
                ? this.env.searchModel.domain
                : [];
            this.dashboardState.data = await this.orm.call(
                "gn.customer.due.alert",
                "get_cxc_partner_list_dashboard",
                [domain]
            );
        } catch (error) {
            this.dashboardState.error = rpcErrorMessage(error);
            this.dashboardState.data = null;
        } finally {
            this.dashboardState.loading = false;
        }
    }

    async onToggleAllGroups() {
        const list = this.props.list;
        if (!list.isGrouped) {
            return;
        }
        const expand = list.groups.some((group) => group.isFolded);
        for (const group of list.groups) {
            if (expand && group.isFolded) {
                await group.toggle();
            } else if (!expand && !group.isFolded) {
                group.model._updateConfig(group.config, { isFolded: true }, { reload: false });
            }
        }
    }
}
