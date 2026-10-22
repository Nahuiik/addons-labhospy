/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { download } from "@web/core/network/download";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";

const CONTEXT_KEYS = [
    "to_date",
    "warehouse",
    "warehouse_id",
    "location",
    "allowed_company_ids",
    "lang",
    "tz",
];

export class StockAtDateListController extends ListController {
    static template = "gn_labhospy.StockAtDateListView";
    static components = { ...ListController.components };

    setup() {
        super.setup();
        this.exportState = useState({ busy: false });
        this.notification = useService("notification");
    }

    _stockAtDateContext() {
        const source = this.model.root.context || {};
        const context = {};
        for (const key of CONTEXT_KEYS) {
            if (source[key] !== undefined && source[key] !== null && source[key] !== false) {
                context[key] = source[key];
            }
        }
        return context;
    }

    async onExportStockAtDate() {
        if (this.exportState.busy) {
            return;
        }
        this.exportState.busy = true;
        try {
            const root = this.model.root;
            let ids;
            if (root.selection?.length && !root.isDomainSelected) {
                ids = root.selection.map((record) => record.resId);
            } else {
                ids = await this.orm.search(root.resModel, root.domain, {
                    context: root.context,
                    order: "is_favorite desc, default_code, name, id",
                });
            }
            if (!ids.length) {
                this.notification.add(_t("No hay productos para exportar con el filtro actual."), {
                    type: "warning",
                });
                return;
            }
            await download({
                url: "/gn_labhospy/stock_at_date_xlsx",
                data: {
                    ids: JSON.stringify(ids),
                    context: JSON.stringify(this._stockAtDateContext()),
                },
            });
        } catch (error) {
            this.notification.add(_t("No se pudo generar el Excel del inventario."), {
                type: "danger",
            });
            console.error(error);
        } finally {
            this.exportState.busy = false;
        }
    }
}

const stockReportListView = registry.category("views").get("stock_report_list_view");
registry.category("views").add(
    "stock_report_list_view",
    {
        ...stockReportListView,
        Controller: StockAtDateListController,
    },
    { force: true }
);
