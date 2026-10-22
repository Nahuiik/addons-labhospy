import { _t } from '@web/core/l10n/translation';
import { registry } from '@web/core/registry';

import { ConfLoader } from '../webclient/webclient';
import { LanguDropdown } from './indicat/langu';

const userMenuRegistry = registry.category('user_menuitems');

function customizeItem(env) {
    return {
        type: 'item',
        id: 'customize',
        description: _t('Appearance'),
        callback: () => {
            if (env.isSmall) {
                document.querySelector('.o_burger_menu .o_sidebar_close')?.click();
            }
            env.services.ui.omux_conf_ctab = 'usr';
            env.services.dialog.add(ConfLoader, {});
        },
        sequence: 41,
    };
}

function languItem(env) {
    return {
        type: 'component',
        contentComponent: LanguDropdown,
        sequence: 42,
    };
}

function separator42() {
    return {
        type: 'separator',
        sequence: 43,
    };
}

userMenuRegistry
    .add('appea', customizeItem)
    .add('langu', languItem)
    .add('sep42', separator42)