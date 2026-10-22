import { Component, onWillStart, useState } from '@odoo/owl';
import { Dropdown } from '@web/core/dropdown/dropdown';
import { DropdownItem } from '@web/core/dropdown/dropdown_item';
import { loadLanguages, _t } from '@web/core/l10n/translation';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';

export class LanguDropdown extends Component {
    static components = { Dropdown, DropdownItem };
    static props = [];
    static template = 'wux.LanguDropdown';

    setup() {
        this.user = user;

        this.action = useService('action');
        this.orm = useService('orm');
        this.ui = useService('ui');

        this.state = useState({});

        onWillStart(async () => {
            this.state.langs = await loadLanguages(this.orm);
        })
    }

    switchLang(ev) {
        const lang = ev.target.getAttribute('val');
        if (lang === user.context.lang) return;

        this.action.doAction('udoo_om_ux.action_switch_lang', {
            additionalContext: { clang: lang }
        });
    }
}
