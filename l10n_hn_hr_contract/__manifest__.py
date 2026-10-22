# © 2025 Grupo Nahuiik
# See README.rst for license details.

{
    "name": "l10n HN HR Contract",
    "version": "19.0.1.0.0",
    "summary": "Agrega la opcion de contrato a Odoo 19",
    "description": """
Honduras HR Contract extensions
==============================

Reintroduce the Odoo 18 Enterprise salary configurator concepts (benefits, wage with holidays,
employer yearly cost and automatic leave allocations) on top of Odoo 19 Community +
bi_hr_payroll stack.
""",
    "author": "Grupo Nahuiik",
    "website": "https://www.gruponahuiik.com",
    "category": "Human Resources",
    "license": "OPL-1",
    "depends": [
        "hr",
        "hr_holidays",
        "bi_hr_payroll",
        "bi_hr_payroll_account",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/hr_contract_benefit_template.xml",
        "views/benefit_views.xml",
        "views/hr_contract_list_view.xml",
        "views/hr_contract_menu.xml",
        "views/hr_bank_accounts_menu.xml",
        "views/hr_version_views.xml",
        "views/res_config_settings_views.xml",
        "views/apply_benefit_template_wizard_views.xml",
    ],
    "test": [
        "tests/test_contract_benefits.py",
    ],
    "installable": True,
    "application": False,
}


