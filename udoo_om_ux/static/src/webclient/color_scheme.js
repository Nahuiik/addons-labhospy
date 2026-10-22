import { registry } from '@web/core/registry';
import { browser } from '@web/core/browser/browser';
import { cookie } from '@web/core/browser/cookie';
import { user } from '@web/core/user';

const systemColorScheme = () =>
    browser.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light';

const currentColorScheme = () => cookie.get('color_scheme');

export const blockingWebClient = Promise.withResolvers();

export const colorSchemeService = {
    async start() {
        const userScheme = user.settings.color_scheme;
        const preferred = ['light', 'dark'].includes(userScheme) ? userScheme : systemColorScheme();
        const current = currentColorScheme();

        if (preferred !== current) {
            cookie.set('color_scheme', preferred);
            if (current || preferred === 'dark') {
                this.reload();
                await blockingWebClient.promise;
            }
        }

        return {
            get systemColorScheme() { return systemColorScheme(); },
            get currentColorScheme() { return currentColorScheme(); },
            get userColorScheme() { return user.settings.color_scheme; },
        };
    },

    reload() {
        browser.location.reload();
    },
};

registry.category('services').add('color_scheme', colorSchemeService);