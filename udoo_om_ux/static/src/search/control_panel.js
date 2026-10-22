import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { useState } from '@odoo/owl';
import { utils } from '@web/core/ui/ui_service';

import { CheckBox } from '@web/core/checkbox/checkbox';
import { Breadcrumbs } from '@web/search/breadcrumbs/breadcrumbs';
import { ControlPanel } from '@web/search/control_panel/control_panel';

import { useUdooStore, useUdooLocalStore } from '@omux_state_manager/store';


patch(Breadcrumbs.prototype, {

    setup() {
        super.setup();

        this.ue = useUdooLocalStore();
        this.uo = useUdooStore();
    }
});

patch(ControlPanel.prototype, {

    setup() {
        super.setup();

        if (this.env.services['mail.store']) {
            this.store = useState(useService('mail.store'));
        }

        this.store.uQuickRepeat = false;
    },

    async uOnWillStart() {
        await super.uOnWillStart();

        if (this.ui.dropinMode || (this.actUid && this.ue.actionAdvs['DIM_' + this.actUid])) {
            this.state.dropinMode = true;
        }
    },

    uInitLayter() {
        this.hasAttachmentPreview = document.querySelectorAll('div.o_attachment_preview').length > 0;
        this.hasChatter = document.querySelectorAll('.o-mail-ChatterContainer, .o_FormRenderer_chatterContainer').length > 0;
        this.hasList = document.querySelectorAll('.o_list_table').length > 0;
    },

    uSwitchAside(dir) {
        if (dir == 'b') {
            if (utils.getPureSize() > 4) {
                odoo.sett_uisize = 4;
                this.ui.size = odoo.sett_uisize;
                this.ue.sett_uisize = odoo.sett_uisize;
                document.body.classList.add('uup');
            } else {
                delete odoo.sett_uisize;
                delete this.ue.sett_uisize;
            }
        } else if (dir == 'r') {
            if (utils.getPureSize() > 4) {
                delete odoo.sett_uisize;
                delete this.ue.sett_uisize;
            }
        }
        this.env.bus.trigger('ACT:REPAINT');
    },

    uSwitchDropin() {
        this.state.dropinMode = !this.state.dropinMode;
        this.ui.dropinMode = this.state.dropinMode;

        if (this.ui.dropinMode) {
            this.ue.actionAdvs['DIM_' + this.actUid] = 1;
        } else {
            delete this.ue.actionAdvs['DIM_' + this.actUid];
        }
    },

    uBookmarkThis() {
        this.env.bus.trigger('UDOO:BMK');
    },

    uBackTrick() {
        const backBtn = document.querySelector('.breadcrumb-item.o_back_button');
        if (backBtn) {
            backBtn.click();
        } else {
            this.actionService.restore();
        }
    },

    uQuickRepeatCheck(checked) {
        this.store.uQuickRepeat = checked;
    },
});

ControlPanel.components = {
    ...ControlPanel.components,
    CheckBox,
}