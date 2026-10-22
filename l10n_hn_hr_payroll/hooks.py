# -*- coding: utf-8 -*-


def run_post_init(env):
    """Post-instalación: migraciones SQL y datos legacy (Odoo 19 pasa solo env)."""
    cr = env.cr
    cr.execute("DROP VIEW IF EXISTS gn_hn_vacation_pending_report CASCADE")
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'hr_employee' AND column_name = 'x_l10n_hn_blood_type_legacy'
    """)
    if cr.fetchone():
        Blood = env['l10n_hn_hr_payroll.blood.type']
        cr.execute("""
            SELECT id, x_l10n_hn_blood_type_legacy FROM hr_employee
            WHERE x_l10n_hn_blood_type_legacy IS NOT NULL AND blood_type_id IS NULL
        """)
        for emp_id, code in cr.fetchall():
            if not code:
                continue
            bt = Blood.search([('code', '=', code)], limit=1)
            if bt:
                cr.execute(
                    "UPDATE hr_employee SET blood_type_id = %s WHERE id = %s",
                    (bt.id, emp_id),
                )
        cr.execute("ALTER TABLE hr_employee DROP COLUMN IF EXISTS x_l10n_hn_blood_type_legacy")

    from odoo.addons.l10n_hn_hr_payroll import _post_init_migrate_isr_calculated

    _post_init_migrate_isr_calculated(env)
