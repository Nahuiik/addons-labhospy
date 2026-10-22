# -*- coding: utf-8 -*-
"""
Elimina la vista heredada obsoleta (contenido en gn_hr_recruitment_core).
"""


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'l10n_hn_hr_recruitment'
          AND name = 'hr_employee_view_form_inherit_skills_cert_to_education'
          AND model = 'ir.ui.view'
        RETURNING res_id
        """
    )
    row = cr.fetchone()
    if not row or not row[0]:
        return
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (row[0],))
