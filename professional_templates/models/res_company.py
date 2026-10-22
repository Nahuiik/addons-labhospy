# -*- coding: utf-8 -*-
"""
# License LGPL-3.0 or later (https://opensource.org/licenses/LGPL-3.0).
#
#This software and associated files (the "Software") may only be used (executed,
#modified, executed after modifications) if you have purchased a valid license
#from the authors, typically via Odoo Apps, or if you have received a written
#agreement from the authors of the Software (see the COPYRIGHT section below).
#
#You may develop Odoo modules that use the Software as a library (typically
#by depending on it, importing it and using its resources), but without copying
#any source code or material from the Software. You may distribute those
#modules under the license of your choice, provided that this license is
#compatible with the terms of the Odoo Proprietary License (For example:
#LGPL, MIT, or proprietary licenses similar to this one).
#
#It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#or modified copies of the Software.
#
#The above copyright notice and this permission notice must be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#DEALINGS IN THE SOFTWARE.
#
#########COPYRIGHT#####
# © 2017 Bernard K Too<bernard.too@optima.co.ke>
"""
from odoo import api, fields, models


class ReportDefaultSettings(models.Model):
    """Extend company to store report defaults without altering base relations."""
    _inherit = "res.company"

    facebook = fields.Char('Facebook ID')
    twitter = fields.Char('Twitter Handle')
    youtube = fields.Char('YouTube ID')

    df_style = fields.Many2one(
        'report.template.settings',
        'Default Style',
        help=
        "If no other report style is specified during the printing of document,\
                    this default style will be used")

    pdf_watermark = fields.Binary(
        'Watermark PDF',
        help=
        'Upload your company letterhead PDF or a PDF to form the background of your reports.\
                    This PDF will be used as the background of each an every page printed.'
    )

    pdf_watermark_fname = fields.Char('Watermark Filename', company_dependent=True)

    pdf_last_page = fields.Binary(
        'Last Pages PDF',
        help=
        'Here you can upload a PDF document that contain some specific content \
                    such as product brochure,\n promotional content, advert, sale terms \
                    and Conditions,..etc.\n This document will be appended to the printed report'
    )
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
