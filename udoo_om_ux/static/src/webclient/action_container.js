import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { useBus } from '@web/core/utils/hooks';
import { ActionContainer } from '@web/webclient/actions/action_container';

patch(ActionContainer.prototype, {
    setup() {
        super.setup();

        useBus(this.env.bus, 'ACT:REPAINT', async (args) => {
            await this.render(true);
            setTimeout(() => window.dispatchEvent(new Event('resize')));
        });
    }
});