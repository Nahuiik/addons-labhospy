import { patch } from '@web/core/utils/patch';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

import { ControlPanel } from '@web/search/control_panel/control_panel';
import { MailFullscreen } from '@mail/core/common/mail_fullscreen';
import { onWillStart, reactive } from '@odoo/owl';

import { useUdooStore, useUdooLocalStore, waitUntil } from '@omux_state_manager/store';

const DEFAULT_ID = Symbol('default');

export const fullscreenService = {
    start(env) {
        const state = reactive({ enter, exit, id: undefined });
        async function exit(id = state.id) {
            if (!this || id !== state.id) {
                return;
            }
            this.closeOverlay?.();
            state.id = undefined;
            const fullscreenElement =
                document.webkitFullscreenElement || document.fullscreenElement;
            if (fullscreenElement) {
                if (document.exitFullscreen) {
                    await document.exitFullscreen();
                } else if (document.mozCancelFullScreen) {
                    await document.mozCancelFullScreen();
                } else if (document.webkitCancelFullScreen) {
                    await document.webkitCancelFullScreen();
                }
            }
        }
        /**
         * @param component
         * @param {object} [options]
         * @param [options.props]
         * @param {any} [options.id]
         * @param {boolean} [options.keepBrowserHeader] - Optional flag to specify whether to keep
         * the browser's header (address bar, tabs, etc.) visible.
         * @param {string} [options.rootId] - Optional root id to pass to the overlay.
         * @returns {Promise<void>}
         */
        async function enter(
            component,
            { keepBrowserHeader = false, props, rootId, id = DEFAULT_ID } = {}
        ) {
            this.closeOverlay?.();
            state.id = id;
            this.closeOverlay = env.services.overlay.add(
                MailFullscreen,
                { component, props },
                { rootId }
            );
            const el = document.body;
            if (keepBrowserHeader) {
                return;
            }
            try {
                if (el.requestFullscreen) {
                    await el.requestFullscreen();
                } else if (el.mozRequestFullScreen) {
                    await el.mozRequestFullScreen();
                } else if (el.webkitRequestFullscreen) {
                    await el.webkitRequestFullscreen();
                }
            } catch {
                // doing nothing, we're just in non-native fullscreen.
            }
        }
        window.addEventListener("fullscreenchange", () => {
            const isFullscreen = Boolean(
                document.webkitFullscreenElement || document.fullscreenElement
            );
            if (!isFullscreen) {
                exit();
            }
        });
        return state;
    },
};

registry.category('services').add('mail.fullscreen', fullscreenService, { force: true });

patch(ControlPanel.prototype, {
    setup() {
        super.setup();

        this.ui = useService('ui');
        this.ue = useUdooLocalStore();
        this.uo = useUdooStore();
        this.uo.onbOk = false;

        onWillStart(async () => {
            // Initialize actionAdvs if needed
            if (typeof this.ue.actionAdvs != 'object') {
                this.ue.actionAdvs = {};
            }
            this.actUid = this.env.config?.actionId;
            await this.uOnWillStart();
        })
    },

    async uOnWillStart() {
        setTimeout(async () => {
            this.uo.onbOk = await waitUntil(() => document.querySelector('nav>.o_navbar_breadcrumbs'));
        }, 98);
    },

    uInitLayter() { },

    uReloadLayout() {
        this.env.bus.trigger('LYT:RESET');
    },

    uToggleFullScreen() {
        const doc = document;
        const el = doc.documentElement;

        const request = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen || el.msRequestFullscreen;
        const exit = doc.exitFullscreen || doc.webkitExitFullscreen || doc.mozCancelFullScreen || doc.msExitFullscreen;

        const isFullscreen =
            doc.fullscreenElement ||
            doc.webkitFullscreenElement ||
            doc.mozFullScreenElement ||
            doc.msFullscreenElement;

        if (request && exit) {
            if (isFullscreen) {
                exit.call(doc);
            } else {
                request.call(el);
            }
        } else {
            console.warn('Fullscreen API is not supported on this device.');
            // Optional: show toast or fallback behavior
        }
    },
});
