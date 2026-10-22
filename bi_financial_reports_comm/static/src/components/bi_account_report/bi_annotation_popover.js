/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class BiAnnotationPopover extends Component {
    static template = "bi_financial_reports_comm.BiAnnotationPopover";
    static props = {
        reportType: String,
        cellKey: String,
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ note: "", loading: true, saving: false });

        onWillStart(async () => {
            const res = await this.orm.call("bi.report.annotation", "get_note", [
                this.props.reportType,
                this.props.cellKey,
            ]);
            this.state.note = (res && res.note) || "";
            this.state.loading = false;
        });
    }

    async onSave() {
        this.state.saving = true;
        try {
            await this.orm.call("bi.report.annotation", "set_note", [
                this.props.reportType,
                this.props.cellKey,
                this.state.note,
            ]);
            this.notification.add(_t("Anotación guardada"), { type: "success" });
            this.props.close?.();
        } catch (e) {
            this.notification.add(_t("No se pudo guardar la anotación"), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    get _t() {
        return _t;
    }
}
