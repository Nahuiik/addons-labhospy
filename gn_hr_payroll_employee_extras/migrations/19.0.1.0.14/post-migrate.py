# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# Marca como plantillas los conceptos compartidos (sin empleado) existentes.


def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_employee_recurring_concept
        SET is_template = TRUE
        WHERE employee_id IS NULL
        """
    )
