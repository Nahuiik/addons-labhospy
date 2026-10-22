# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move isr_manual/amount_isr_manual → amount_isr_calculated.

    Previously, "Establecer ISR" wrote the calculated ISR amount into the
    manual-override fields.  Now those are separated: amount_isr_calculated
    holds the process-computed value, while isr_manual + amount_isr_manual
    are reserved for true user overrides.
    """
    if not version:
        return

    cr.execute("""
        UPDATE hr_version
        SET amount_isr_calculated = amount_isr_manual,
            isr_manual = FALSE,
            amount_isr_manual = 0
        WHERE isr_manual = TRUE
          AND amount_isr_manual > 0
    """)
    count = cr.rowcount
    if count:
        _logger.info(
            "Migrated %d hr.version records: amount_isr_manual → amount_isr_calculated",
            count,
        )
