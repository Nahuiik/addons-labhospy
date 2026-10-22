# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrRecruitmentStage(models.Model):
    _inherit = 'hr.recruitment.stage'

    survey_id = fields.Many2one(
        'survey.survey',
        string="Entrevista",
        domain=[('survey_type', '=', 'recruitment')],
        help="Si se define, al enviar la entrevista desde una postulación en esta etapa se usará esta encuesta. "
             "Si no se define, se usará la entrevista del puesto de trabajo."
    )
