# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.urls import urljoin


class SurveyUrlWizard(models.TransientModel):
    _name = 'hr.applicant.survey.url.wizard'
    _description = 'URL de entrevista'

    applicant_id = fields.Many2one('hr.applicant', required=True)
    survey_url = fields.Char('URL', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        applicant_id = self.env.context.get('active_id')
        if applicant_id and 'survey_url' in fields_list:
            applicant = self.env['hr.applicant'].browse(applicant_id)
            # Obtener entrevista de la etapa actual (misma lógica que applicant.survey_id)
            # para evitar problemas de caché al abrir el wizard
            survey = False
            if applicant.stage_id and applicant.stage_id.survey_id:
                survey = applicant.stage_id.survey_id
            elif applicant.job_id and applicant.job_id.survey_id:
                survey = applicant.job_id.survey_id
            if not survey:
                raise UserError(_('No hay entrevista asignada para esta postulación.'))
            if not applicant.partner_id:
                if not applicant.partner_name:
                    raise UserError(_('Indique el nombre del candidato para generar el enlace.'))
                applicant.partner_id = self.env['res.partner'].sudo().create({
                    'is_company': False,
                    'name': applicant.partner_name,
                    'email': applicant.email_from,
                    'phone': applicant.partner_phone,
                })
            answer = applicant.response_ids.filtered(lambda r: r.survey_id == survey)
            if not answer:
                answer = survey.sudo()._create_answer(
                    partner=applicant.partner_id,
                    applicant_id=applicant.id,
                )
            else:
                answer = answer[0]
            base_url = survey.get_base_url()
            path = answer.get_start_url()
            res['survey_url'] = urljoin(base_url, path)
            res['applicant_id'] = applicant_id
        return res
