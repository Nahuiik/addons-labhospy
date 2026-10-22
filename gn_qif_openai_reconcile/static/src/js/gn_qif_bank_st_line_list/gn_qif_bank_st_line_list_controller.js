/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";

/**
 * ListController para líneas de extracto tras import QIF/IA: banner con resumen y atajos
 * a candidatos CE `account.reconcile.model` sin depender del widget Enterprise.
 */
export class GnQifBankStLineListController extends ListController {
    static template = "gn_qif_openai_reconcile.GnQifBankStLineListView";

    setup() {
        super.setup();
        this.notificationService = useService("notification");
    }

    get gnQifImportMessage() {
        return this.props.context?.gn_qif_import_message || "";
    }

    get gnQifRecoToolbarVisible() {
        const c = this.props.context || {};
        return Boolean(
            c.gn_qif_reco_tools_enabled ||
                c.default_journal_id ||
                c.search_default_journal_id ||
                this.gnQifImportMessage
        );
    }

    gnQifSelectedLineIds() {
        return this.model.root.selection.map((r) => r.resId);
    }

    async onGnQifOpenRecoCandidates() {
        const ids = this.gnQifSelectedLineIds();
        if (!ids.length) {
            this.notificationService.add(_t("Selecciona una o más líneas de extracto."), {
                type: "warning",
            });
            return;
        }
        const action = await this.orm.call(
            "account.bank.statement.line",
            "gn_qif_action_reconcile_model_candidates",
            [ids]
        );
        if (action) {
            return this.actionService.doAction(action);
        }
        return undefined;
    }

    async onGnQifOpenTemplateWizard() {
        const ids = this.gnQifSelectedLineIds();
        if (!ids.length) {
            this.notificationService.add(
                _t("Selecciona al menos una línea para usar su diario."),
                {
                    type: "warning",
                }
            );
            return;
        }
        const action = await this.orm.call(
            "account.bank.statement.line",
            "gn_qif_action_open_template_wizard",
            [ids]
        );
        if (action) {
            return this.actionService.doAction(action);
        }
        return undefined;
    }
}
