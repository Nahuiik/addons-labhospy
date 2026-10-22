# -*- coding: utf-8 -*-
"""Actualiza client actions con el tag legacy del dashboard semanal."""


def migrate(cr, version):
    # odoo-pr-allow-sql: migración — retag de client action legacy del dashboard semanal
    cr.execute(
        """
        UPDATE ir_act_client
           SET tag = 'gn_banks_balance_weekly_dashboard'
         WHERE tag = 'gn_banks_weekly_balance_dashboard'
        """
    )
