# -*- coding: utf-8 -*-
"""Reasignar el grupo de gn_contacts_configuration a este módulo."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'gn_hr_payroll_employee_extras',
               name = 'group_gn_contacts_configuration'
         WHERE module = 'gn_contacts_configuration'
           AND name = 'group_contacts_configuration'
           AND model = 'res.groups'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'gn_contacts_configuration'
        """
    )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled'
         WHERE name = 'gn_contacts_configuration'
        """
    )
