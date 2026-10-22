import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { ListController } from '@web/views/list/list_controller';


patch(ListController.prototype, {
    setup() {
        super.setup();

        this.ui = useService('ui');
    },

    get uPureOpenRecord() {
        return true;
    },

    async openRecord(record, { force, newWindow } = { force: false }) {
        const { env, ui, archInfo, actionService } = this;
        const vController = actionService.currentController;

        if (newWindow || env.inDialog || this.uPureOpenRecord) {
            super.openRecord(...arguments); return;
        }
        const hasFormView = vController.views?.some((view) => view.type === 'form');
        if (!hasFormView || archInfo.openAction) {
            super.openRecord(...arguments); return;
        }
        await this._validOpenRecordOm(record, ui, vController);
    },

    async _validOpenRecordOm(record, ui, vController) {
        if (super._validOpenRecordOm) {
            await super._validOpenRecordOm(record, ui, vController);
        }
    },
});
