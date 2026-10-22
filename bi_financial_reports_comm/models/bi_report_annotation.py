# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BiReportAnnotation(models.Model):
    _name = 'bi.report.annotation'
    _description = 'Anotación en celda de informe financiero (BI CE)'

    _cell_company_uniq = models.Constraint(
        'unique(company_id, report_type, cell_key)',
        'Ya existe una anotación para esta celda en la compañía.',
    )

    report_type = fields.Char(required=True, index=True)
    cell_key = fields.Char(required=True, index=True, string='Clave de celda')
    note = fields.Text(required=True)
    user_id = fields.Many2one('res.users', default=lambda s: s.env.user, required=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company, required=True)
    date = fields.Date(default=fields.Date.context_today)

    @api.model
    def get_note(self, report_type, cell_key):
        ann = self.search([
            ('report_type', '=', report_type),
            ('cell_key', '=', cell_key),
            ('company_id', '=', self.env.company.id),
        ], limit=1, order='date desc, id desc')
        return {'note': ann.note or '', 'id': ann.id}

    @api.model
    def set_note(self, report_type, cell_key, note):
        ann = self.search([
            ('report_type', '=', report_type),
            ('cell_key', '=', cell_key),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        note = (note or '').strip()
        if not note:
            if ann:
                ann.unlink()
            return {'id': False, 'note': ''}
        if ann:
            ann.write({
                'note': note,
                'date': fields.Date.context_today(self),
                'user_id': self.env.user.id,
            })
            return {'id': ann.id, 'note': note}
        ann = self.create({
            'report_type': report_type,
            'cell_key': cell_key,
            'note': note,
        })
        return {'id': ann.id, 'note': note}
