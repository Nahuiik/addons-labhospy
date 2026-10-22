# -*- coding: utf-8 -*-


def migrate(cr, version):
    names = (
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
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'gn_hr_employee_warnings'
        WHERE module = 'l10n_hn_hr_payroll' AND name IN %s
        """,
        (names,),
    )
