# -*- coding: utf-8 -*-


def post_init_hook(env):
    env['l10n_hn_reports.904_tax_sync'].sync_all_companies()
