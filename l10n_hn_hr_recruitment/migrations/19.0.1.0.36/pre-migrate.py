# -*- coding: utf-8 -*-
"""
Antes de cargar l10n_hn_hr_recruitment: elimina la vista `hr_employee_view_form_inherit_skills_cert_to_education`
si quedó en la BD. Esa herencia (xpath a //page certificación sobre hr.view_employee_form) dejó de
ser válida con gn_hr_recruitment_core (quita la pestaña); si el registro persiste, el registry puede fallar.
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
