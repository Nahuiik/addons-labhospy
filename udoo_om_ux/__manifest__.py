# -*- coding: utf-8 -*-
# Copyright 2025 Sveltware Solutions

{
    'name': 'Omux Backend. eCommerce',
    'category': 'Themes/Backend',
    'summary': 'Modern Odoo Backend, pairs with the eCommerce website theme (suite offer, sold separately), theme editor, bookmark manager, menu builder, dual sidebar, hybrid start menu, dark mode, quick pop-up, quick create, recent items, fullscreen forms, RTL support, language switcher, mobile responsive layout, flexible chatter, sticky headers, group toggles, full-width sheet, enhanced list & kanban views, required input markers, batch create, app menu sorting, right-click menu, user wise menu sorting, WCAG 2.2-ready, enterprise color theme, RTL CSS, multi-language ready.',
    'version': '2.1.9',
    'license': 'Other proprietary',
    'author': 'Sveltware Solutions',
    'website': 'https://www.linkedin.com/in/sveltware',
    'live_test_url': 'https://o19-omux.sveltware.com',
    'support': 'odoo@sveltware.com',
    'sequence': 777,
    'images': [
        'static/description/banner.png',
        'static/description/theme_screenshot.png',
    ],
    'cloc_exclude': ['**/*.js'],
    'uninstall_hook': 'uninstall_hook',
    'depends': [
        'base_sparse_field',
        'auth_signup',
        'omux_shared_lib',
        'omux_config_base',
        'omux_state_manager',
        'omux_web_refresher',
        'omux_list_indicator',
        'omux_list_density',
        'omux_border_radius',
        'omux_input_style',
    ],
    'excludes': [
        'web_enterprise',
    ],
    'data': [
        'data/asset_data.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/webclient_templates.xml',
        'views/res_company.xml',
        'views/res_users.xml',
        'views/ir_module.xml',
        'views/ir_ui_menu.xml',
    ],
    'assets': {
        'web._assets_primary_variables': {
            (
                'prepend',
                'udoo_om_ux/static/src/scss/style_variables.scss',
            ),
            (
                'before',
                'web/static/src/scss/primary_variables.scss',
                'udoo_om_ux/static/src/scss/primary_variables.scss',
            ),
            (
                'before',
                'web/static/src/**/*.variables.scss',
                'udoo_om_ux/static/src/**/*.variables.scss',
            ),
        },
        'web._assets_secondary_variables': [
            (
                'before',
                'web/static/src/scss/secondary_variables.scss',
                'udoo_om_ux/static/src/scss/secondary_variables.scss',
            ),
        ],
        'web._assets_backend_helpers': [
            (
                'before',
                'web/static/src/scss/bootstrap_overridden.scss',
                'udoo_om_ux/static/src/scss/bs_backend_overridden.scss',
            ),
        ],
        'web.assets_backend': [
            'omux_shared_lib/static/lib/object_hash.js',
            (
                'after',
                'web/static/src/session.js',
                'udoo_om_ux/static/src/omux.js',
            ),
            (
                'before',
                'base/static/src/css/modules.css',
                'udoo_om_ux/static/src/core/**/*',
            ),
            (
                'replace',
                'web/static/src/webclient/navbar/navbar.scss',
                'udoo_om_ux/static/src/webclient/navbar/navbar.scss',
            ),
            (
                'after',
                'web/static/src/scss/fontawesome_overridden.scss',
                'udoo_om_ux/static/src/scss/overridden_icons.scss',
            ),
            (
                'before',
                'mail/static/src/views/fields/**/*',
                'udoo_om_ux/static/src/patch/chatter/form_compiler.js',
            ),
            (
                'before',
                'mail/static/src/views/fields/**/*',
                'udoo_om_ux/static/src/patch/chatter/form_renderer.js',
            ),
            (
                'before',
                'mail/static/src/views/fields/**/*',
                'udoo_om_ux/static/src/patch/chatter/form_renderer.scss',
            ),
            (
                'before',
                'web/static/src/webclient/**/*',
                'udoo_om_ux/static/src/search/**/*.xml',
            ),
            (
                'after',
                'web/static/src/core/utils/ui.js',
                'udoo_om_ux/static/src/patch/_ui.js',
            ),
            'udoo_om_ux/static/src/views/**/*',
            'udoo_om_ux/static/src/search/**/*.scss',
            'udoo_om_ux/static/src/search/**/*.js',
            'udoo_om_ux/static/src/webclient/**/*',
            'udoo_om_ux/static/src/patch/button_box.js',
            (
                'remove',
                'udoo_om_ux/static/src/**/*.dark.scss',
            ),  # Don't include dark theme
            (
                'after',
                'udoo_om_ux/static/src/webclient/**/*',
                'udoo_om_ux/static/src/scss/style_backend.scss',
            ),
        ],
        'web.dark_mode_variables': [
            (
                'before',
                'udoo_om_ux/static/src/scss/primary_variables.scss',
                'udoo_om_ux/static/src/scss/primary_variables_dark.scss',
            ),
            (
                'before',
                'udoo_om_ux/static/src/**/*.variables.scss',
                'udoo_om_ux/static/src/**/*.variables.dark.scss',
            ),
            (
                'before',
                'udoo_om_ux/static/src/scss/secondary_variables.scss',
                'udoo_om_ux/static/src/scss/secondary_variables_dark.scss',
            ),
        ],
        'web.assets_web_dark': [
            ('include', 'web.dark_mode_variables'),
            (
                'after',
                'udoo_om_ux/static/src/scss/style_variables.scss',
                'udoo_om_ux/static/src/scss/omux/dark.scss',
            ),
            (
                'before',
                'udoo_om_ux/static/src/scss/bs_backend_overridden.scss',
                'udoo_om_ux/static/src/scss/bs_backend_overridden_dark.scss',
            ),
            (
                'after',
                'web/static/lib/bootstrap/scss/_functions.scss',
                'udoo_om_ux/static/src/scss/bs_functions_overridden_dark.scss',
            ),
            'udoo_om_ux/static/src/**/*.dark.scss',
        ],
        'web.assets_backend_lazy_dark': [
            ('include', 'web.dark_mode_variables'),
            (
                'before',
                'udoo_om_ux/static/src/scss/bs_backend_overridden.scss',
                'udoo_om_ux/static/src/scss/bs_backend_overridden_dark.scss',
            ),
            (
                'after',
                'web/static/lib/bootstrap/scss/_functions.scss',
                'udoo_om_ux/static/src/scss/bs_functions_overridden_dark.scss',
            ),
        ],
        'web.assets_web': [
            (
                'after',
                'udoo_om_ux/static/src/scss/style_variables.scss',
                'udoo_om_ux/static/src/scss/omux/light.scss',
            ),
        ],
        'web.assets_frontend': [
            (
                'before',
                'web/static/lib/bootstrap/scss/_variables.scss',
                'udoo_om_ux/static/src/scss/bs_frontend_variables.scss',
            ),
            (
                'replace',
                'web/static/src/webclient/navbar/navbar.scss',
                'udoo_om_ux/static/src/webclient/navbar/navbar.scss',
            ),
            'udoo_om_ux/static/src/scss/style_login_page.scss',
        ],
        'omux.conf': [
            'udoo_om_ux/static/src/conf/*.js',
            'udoo_om_ux/static/src/conf/*.xml',
            'udoo_om_ux/static/src/conf/*.scss',
        ],
    },
    'price': 299,
    'currency': 'USD',
}
