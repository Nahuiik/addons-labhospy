# -*- coding: utf-8 -*-
"""Antes de cargar el registro sin los modelos hn.collective.vacation.* (movidos a gn_hr_vacation)."""

import logging

_logger = logging.getLogger(__name__)

_MODELS = (
    'hn.collective.vacation.wizard',
    'hn.collective.vacation.preview.line',
    'hn.collective.vacation.result.wizard',
    'hn.collective.vacation.result.line',
)


def migrate(cr, version):
    if not version:
        return
    # Vistas y acciones que apuntaban a transient models eliminados
    cr.execute(
        """
        DELETE FROM ir_ui_view v
        USING ir_model_data d
        WHERE d.module = 'l10n_hn_hr_payroll'
          AND d.model = 'ir.ui.view'
          AND d.res_id = v.id
          AND d.name IN (
              'view_hn_collective_vacation_wizard_form',
              'view_hn_collective_vacation_result_wizard_form'
          );
        """
    )
    cr.execute(
        """
        DELETE FROM ir_act_window a
        USING ir_model_data d
        WHERE d.module = 'l10n_hn_hr_payroll'
          AND d.model = 'ir.actions.act_window'
          AND d.res_id = a.id
          AND d.name = 'action_hn_collective_vacation_wizard';
        """
    )
    cr.execute(
        """
        DELETE FROM ir_ui_menu m
        USING ir_model_data d
        WHERE d.module = 'l10n_hn_hr_payroll'
          AND d.model = 'ir.ui.menu'
          AND d.res_id = m.id
          AND d.name = 'menu_gn_vacation_config_collective';
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'l10n_hn_hr_payroll'
          AND name IN (
            'view_hn_collective_vacation_wizard_form',
            'view_hn_collective_vacation_result_wizard_form',
            'action_hn_collective_vacation_wizard',
            'menu_gn_vacation_config_collective'
          );
        """
    )
    # Por si quedaron vistas huérfanas por modelo
    cr.execute(
        "DELETE FROM ir_ui_view WHERE model IN %s",
        (_MODELS,),
    )
    cr.execute(
        "DELETE FROM ir_act_window WHERE res_model IN %s",
        (_MODELS,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_access
        WHERE model_id IN (SELECT id FROM ir_model WHERE model IN %s)
        """,
        (_MODELS,),
    )
    _logger.info(
        "l10n_hn_hr_payroll pre-migrate: eliminados artefactos UI de hn.collective.vacation.*"
    )
