import { patch } from '@web/core/utils/patch';
import { router } from '@web/core/browser/router';
import { useService } from '@web/core/utils/hooks';
import { onWillStart, onWillUnmount } from '@odoo/owl';
import { KanbanController } from '@web/views/kanban/kanban_controller';
import { FormViewDialog } from '@web/views/view_dialogs/form_view_dialog';

import { useUdooLocalStore } from '@omux_state_manager/store';


patch(KanbanController.prototype, {
    setup() {
        super.setup();

        this.ui = useService('ui');
        this.ue = useUdooLocalStore();

        onWillStart(async () => {
            const { ui, props } = this;
            if (props.context.ux_props?.dropin_kanban) {
                ui.dropinUid = `${props.resModel}`;
                ui.dropinMode = props.context.ux_props.dropin_kanban;
            }
        });

        onWillUnmount(() => {
            if (this.ui.dropinMode) {
                delete this.ui.dropinMode;
                delete this.ui.dropinUid;
            }
        });
    },

    async openRecord(record, { newWindow } = {}) {
        const { actionService, env, ui, ue } = this;
        const actUid = env.config?.actionId;
        if (actUid && ue.actionAdvs['DIM_' + actUid]) {
            ui.dropinMode = true;
        } else if (newWindow || env.isSmall || env.inDialog || (!ui.dropinMode && !ui.shiftKey)) {
            this.open2stRecord(...arguments);
            return;
        }
        const controller = actionService.currentController;
        const hasFormView = controller.views?.some((view) => view.type === 'form');

        if (!hasFormView) {
            super.openRecord(...arguments);
            return;
        }
        if (ui.shiftKey) {
            ui.dropinMode = ui.dropinMode ? false : true;
        }
        if (ui.dropinMode) {
            record.model.dialog.add(FormViewDialog, this.composeDropinProps(record));
        } else {
            this.open2stRecord(...arguments);
        }
    },

    composeDropinProps(record) {
        const formSpec = this.env.config.views.find(v => v[1] === 'form');
        const sheetName = record._textValues.display_name || record._textValues.name;
        return {
            title: sheetName || router.current.actionStack[router.current.actionStack.length - 1].displayName,
            viewId: formSpec ? formSpec[0] : false,
            resModel: record.resModel,
            resId: record.resId,
            context: {},
            onRecordSaved: async () => {
                await this.model.load();
            },
        }
    },

    async open2stRecord(record, { newWindow } = {}) {
        super.openRecord(...arguments);
    }
});