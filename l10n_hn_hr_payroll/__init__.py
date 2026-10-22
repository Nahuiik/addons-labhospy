# -*- coding: utf-8 -*-
# © 2025 Grupo Nahuiik

from . import models
from . import wizard
from . import report


def _post_init_migrate_isr_calculated(env):
    """Migrate existing isr_manual/amount_isr_manual → amount_isr_calculated.

    For versions where isr_manual was set by the "Establecer ISR" process
    (not by a real manual override), move the value to amount_isr_calculated
    and reset the manual fields to their defaults (False / 0).
    """
    env.cr.execute("""
        UPDATE hr_version
        SET amount_isr_calculated = amount_isr_manual,
            isr_manual = FALSE,
            amount_isr_manual = 0
        WHERE isr_manual = TRUE
          AND amount_isr_manual > 0
    """)
    count = env.cr.rowcount
    if count:
        import logging
        logging.getLogger(__name__).info(
            "Migrated %d hr.version records: amount_isr_manual → amount_isr_calculated", count
        )
    _post_init_hr_version_rule(env)
    _post_init_liquidation_legal_reason(env)


def _post_init_hr_version_rule(env):
    """Actualizar regla hr.version para usar user.company_ids (solo si gn_hr_intercompany no está instalado).

    Si gn_hr_intercompany está instalado, él gestiona la regla. Si no, aplicamos el fix aquí.
    """
    if env["ir.module.module"].search(
        [("name", "=", "gn_hr_intercompany"), ("state", "=", "installed")], limit=1
    ):
        return
    rule = env.ref("hr.ir_rule_hr_contract_multi_company", raise_if_not_found=False)
    if rule:
        domain = (
            "['|', '|', '|', "
            "('company_id', '=', False), "
            "('company_id', 'in', (user.company_ids.ids or company_ids)), "
            "('employee_id.parent_id.user_id', '=', user.id), "
            "('employee_id.user_id', '=', user.id)]"
        )
        rule.sudo().write({"domain_force": domain})


def _post_init_liquidation_legal_reason(env):
    """Tras añadir legal_termination_reason, alinear con reason legacy."""
    Liquid = env["l10n.hn.liquidation"].sudo()
    for rec in Liquid.search([]):
        if not rec.reason:
            continue
        mapped = rec._map_legacy_reason()
        if rec.legal_termination_reason != mapped:
            rec.write({"legal_termination_reason": mapped})


def post_init_hook(env):
    from .hooks import run_post_init

    run_post_init(env)