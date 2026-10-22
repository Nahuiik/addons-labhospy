# -*- coding: utf-8 -*-
from odoo import models


class ReportGnLabhospyControlledSubstancesHtml(models.AbstractModel):
    """Misma lógica y plantilla principal; report_name dedicado para QWeb HTML."""

    _name = 'report.gn_labhospy.report_controlled_substances_html'
    _inherit = 'report.gn_labhospy.report_controlled_substances_document'
    _description = 'HTML sustancias controladas'

