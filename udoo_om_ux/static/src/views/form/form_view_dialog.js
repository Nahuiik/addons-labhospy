/** @odoo-module **/

import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { Chatter } from '@mail/chatter/web_portal/chatter';


patch(FormViewDialog.prototype, {
    setup() {
        this.dropinCls = '';
        super.setup();
        this.ui = useService('ui');
    }
});

FormViewDialog.components = { ...FormViewDialog.components, Chatter }
