# -*- coding: utf-8 -*-
"""
Odoo Proprietary License v1.0.

see License:
https://www.odoo.com/documentation/user/17.0/legal/licenses/licenses.html#odoo-apps
# Copyright ©2023 Bernard K. Too<bernard.too@optima.co.ke>
"""
from odoo import api, fields, models


class IrActionsReportXml(models.Model):
    """ @inherit report action model to add watermark and lastpage fields """
    _inherit = 'ir.actions.report'

    pdf_watermark = fields.Binary(
            'Watermark PDF',
            help=
            'Upload a watermark PDF to be used as the background of each page printed.\n\
                    Watermark uploaded here will override the one uploaded at company \
                    level in the general settings.')
    pdf_watermark_fname = fields.Char('Watermark Filename', company_dependent=True)
    pdf_last_page = fields.Binary(
            'Last Pages PDF',
            help=
            'Here you can upload a PDF document that contain some specific content \
                    such as product brochure,\n promotional content, advert, sale terms and\
                    Conditions,..etc.\nThis document will be appended to the printed report. \n\
                    Last pages PDF uploaded here will override the one uploaded at company \
                    level in the general settings.')
    pdf_last_page_fname = fields.Char('Last Pages Filename', company_dependent=True)

    @api.model
    def _auto_init(self):
        self._ensure_json_company_fields(['pdf_watermark_fname', 'pdf_last_page_fname'])
        return super()._auto_init()

    def _ensure_json_company_fields(self, columns):
        for column in columns:
            self.env.cr.execute(
                """
                SELECT data_type
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name = %s
                   AND column_name = %s
                """,
                (self._table, column),
            )
            row = self.env.cr.fetchone()
            if row and row[0] != 'jsonb':
                self.env.cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (self._table, column))
