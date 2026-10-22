# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Copia valores desde columnas antiguas (l10n_hn_hr_payroll) antes de que el ORM las elimine."""
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_type' AND column_name = 'is_hn_vacation'
        """
    )
    has_old_primary = bool(cr.fetchone())
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_type' AND column_name = 'gn_vacation_is_primary'
        """
    )
    has_new_primary = bool(cr.fetchone())
    if has_old_primary and not has_new_primary:
        cr.execute(
            """
            ALTER TABLE hr_leave_type ADD COLUMN gn_vacation_is_primary boolean DEFAULT false;
            UPDATE hr_leave_type SET gn_vacation_is_primary = COALESCE(is_hn_vacation, false);
            """
        )
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_type' AND column_name = 'hn_block_vacation_before_anniversary'
        """
    )
    has_old_block = bool(cr.fetchone())
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_leave_type' AND column_name = 'gn_vacation_block_before_anniversary'
        """
    )
    has_new_block = bool(cr.fetchone())
    if has_old_block and not has_new_block:
        cr.execute(
            """
            ALTER TABLE hr_leave_type ADD COLUMN gn_vacation_block_before_anniversary boolean DEFAULT false;
            UPDATE hr_leave_type SET gn_vacation_block_before_anniversary = COALESCE(hn_block_vacation_before_anniversary, false);
            """
        )
