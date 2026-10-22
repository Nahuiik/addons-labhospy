# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik

_XMLID_NAMES = (
    "warning_type_missing_docs",
    "warning_type_license_expiry",
    "warning_type_contract_expiry",
    "warning_type_loan_no_dates",
    "warning_type_parent_type",
    "warning_type_trial_period",
    "view_hr_employee_warning_type_list",
    "view_hr_employee_warning_type_form",
    "action_hr_employee_warning_type",
    "menu_hr_employee_warning_type",
)


def pre_init_hook(env):
    """Antes de cargar datos: reclama xmlids desde l10n_hn_hr_payroll si existían."""
    env.cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'gn_hr_employee_warnings'
        WHERE module = 'l10n_hn_hr_payroll' AND name IN %s
        """,
        (tuple(_XMLID_NAMES),),
    )


def post_init_hook(env):
    """Copia parámetro legacy HN al parámetro neutro si aún no existe."""
    ICP = env["ir.config_parameter"].sudo()
    new_key = "gn_hr_employee_warnings.contract_expiration_warning_days"
    old_key = "l10n_hn_hr_payroll.contract_expiration_warning_days"
    if not ICP.get_param(new_key) and ICP.get_param(old_key):
        ICP.set_param(new_key, ICP.get_param(old_key))
