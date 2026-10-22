# Copyright 2026 Grupo Nahuiik (parche LabHosPy)
# Repara BD donde el ORM ya expone el campo pero la columna no existió (p. ej. -u incompleto).
import logging

_logger = logging.getLogger(__name__)


def _ensure_res_company_age_partner_column(cr):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'res_company'
          AND column_name = 'age_partner_config_id'
        """
    )
    if cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'account_age_report_configuration'
        """
    )
    if not cr.fetchone():
        _logger.warning(
            "account_financial_report: sin tabla account_age_report_configuration; "
            "no se crea age_partner_config_id en res_company"
        )
        return
    cr.execute(
        """
        ALTER TABLE res_company
        ADD COLUMN age_partner_config_id INTEGER
        REFERENCES account_age_report_configuration(id) ON DELETE SET NULL
        """
    )
    _logger.info(
        "account_financial_report: creada columna res_company.age_partner_config_id"
    )


def post_init_hook(cr, registry):
    _ensure_res_company_age_partner_column(cr)
