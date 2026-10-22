# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models, tools
from odoo.http import request


class IrActionsReport(models.Model):

    _inherit = 'ir.actions.report'


    print_report_options = fields.Selection([('sent_to_client', 'Sent to Client'),
                                            ('open_print_dialog','Open Print Dialog')],string="Print Report Options")      
