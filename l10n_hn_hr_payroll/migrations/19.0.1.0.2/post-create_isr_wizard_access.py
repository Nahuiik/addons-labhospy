# -*- coding: utf-8 -*-
# Create ir.model.access for l10n.hn.isr.calculation.wizard if missing (fix for CSV load failure)

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Ensure ir.model.access records exist for ISR calculation wizard."""
    cr.execute("""
        SELECT COUNT(*) FROM ir_model_access a
        JOIN ir_model m ON m.id = a.model_id
        WHERE m.model = 'l10n.hn.isr.calculation.wizard'
    """)
    if cr.fetchone()[0] > 0:
        _logger.info("ir.model.access for l10n.hn.isr.calculation.wizard already exists")
        return

    cr.execute("SELECT id FROM ir_model WHERE model = 'l10n.hn.isr.calculation.wizard' LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.warning("Model l10n.hn.isr.calculation.wizard not found in ir.model")
        return

    model_id = row[0]

    def get_group_id(module, name):
        cr.execute("""
            SELECT res_id FROM ir_model_data
            WHERE module = %s AND name = %s AND model = 'res.groups' AND res_id IS NOT NULL
        """, (module, name))
        r = cr.fetchone()
        return r[0] if r else None

    access_names = {
        ('l10n_hn_hr_payroll', 'group_hr_payroll_admin'): 'access_l10n_hn_isr_calculation_wizard_admin',
        ('l10n_hn_hr_payroll', 'group_hr_payroll_user'): 'access_l10n_hn_isr_calculation_wizard_user',
        ('base', 'group_user'): 'access_l10n_hn_isr_calculation_wizard_user_base',
        ('base', 'group_system'): 'access_l10n_hn_isr_calculation_wizard_system',
    }
    for (module, name), access_name in access_names.items():
        gid = get_group_id(module, name)
        if not gid:
            _logger.warning("Group %s.%s not found, skipping", module, name)
            continue
        cr.execute("""
            INSERT INTO ir_model_access (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink, active, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, true, true, true, true, true, 1, NOW(), 1, NOW())
        """, (access_name, model_id, gid))

    _logger.info("Created ir.model.access records for l10n.hn.isr.calculation.wizard")
