/** @odoo-module */

import { patch } from '@web/core/utils/patch';
import { useState } from '@odoo/owl';

import { ListController } from '@web/views/list/list_controller';


patch(ListController.prototype, {
    setup() {
        super.setup();

        this.lvState = useState({
            isInlineEdit: this.editable,
            forceInlineEdit: false,
        })
    },

    forceInlineEdit() {
        if (this.bkEditable === undefined) {
            this.bkEditable = this.editable;
        }

        // Toggling
        this.lvState.forceInlineEdit = !this.lvState.forceInlineEdit;

        if (this.lvState.forceInlineEdit) {
            this.editable = 'top';
        } else {
            this.editable = this.bkEditable;
            delete this.bkEditable;
        }

        // Render
        this.render();
    }
});