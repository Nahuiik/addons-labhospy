# -*- coding: utf-8 -*-

import base64
import logging
import tempfile

from odoo import _, api, models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.warning("Cannot import xlsxwriter")
    xlsxwriter = False


class product_template(models.Model):
    """
    Overwrite to add calculations of stock locations
    """
    _inherit = "product.template"

    def _compute_location_ids(self):
        """
        Compute method for location_ids - as all internal locations

        Extra info:
         * To show only viable location (with positive inventories) we filter locations already in js
         * We should include inactive locations, since configurable inputs are deactivated
         * No restrictionon company_id, since it managed by security rules
        """
        for product_id in self:
            allowed_company_ids = self.env.context.get("allowed_company_ids") or []
            location_ids = self.env["stock.location"].with_context(active_test=False, template_id=product_id.id).search([
                ("usage", "=", "internal"),
                "|", ("company_id", "in", allowed_company_ids), ("company_id", "=", False),
            ])
            product_id.location_ids = [(6, 0, location_ids.ids)]

    def _compute_qty_available_total(self):
        """
        Compute method for qty_available_total

        Methods:
         * _get_sbl_qty of product.product
        """
        variants_total_available = self.with_context(total_warehouse=True).mapped("product_variant_ids")._get_sbl_qty()
        for template in self:
            qty_available_total = virtual_available_total = 0
            for p in template.product_variant_ids:
                qty_line = variants_total_available[p.id]
                qty_available_total += qty_line.get("qty_available")
                virtual_available_total += qty_line.get("virtual_available")

            template.qty_available_total = qty_available_total
            template.virtual_available_total = virtual_available_total

    def _inverse_location_ids(self):
        """
        Inverse method for location_ids: dummy method so that we can edit vouchers and save changes
        """
        return True

    location_ids = fields.One2many(
        "stock.location", compute=_compute_location_ids, inverse=_inverse_location_ids, string="Locations",
    )
    qty_available_total = fields.Float(
        "Total Quantity", compute=_compute_qty_available_total, digits="Product Unit of Measure",
    )
    virtual_available_total = fields.Float(
        "Total Forecast", compute=_compute_qty_available_total, digits="Product Unit of Measure",
    )

    def action_show_table_sbl(self):
        """
        The method to open the tbale of stocks by locations

        Returns:
         * action of opening the table form

        Extra info:
         * Expected singleton
        """
        action_id = self.sudo().env.ref("product_stock_balance.product_template_sbl_button_only_action").read()[0]
        action_id["res_id"] = self.id
        return action_id

    def action_prepare_xlsx_balance(self):
        """
        The method to make .xlsx table of stock balances

        1. Prepare workbook and styles
        2. Prepare header row
          2.1 Get column name like "A" or "S" (ascii char depends on counter)
        3. Prepare each row of locations
        4. Create an attachment

        Methods:
         * action_prepare_elements_for_hierarchy

        Returns:
         * action of downloading the xlsx table

        Extra info:
         * Expected singleton
        """
        if not xlsxwriter:
            raise UserError(_("The Python library xlsxwriter is installed. Contact your system administrator"))
        # 1
        file_path = tempfile.mktemp(suffix=".xlsx")
        workbook = xlsxwriter.Workbook(file_path)
        styles = {
            "main_header_style": workbook.add_format({"bold": True, "font_size": 11, "border": 1}),
            "main_data_style": workbook.add_format({"font_size": 11, "border": 1}),
        }
        worksheet = workbook.add_worksheet(u"{}#{}.xlsx".format(self.name, fields.Date.today()))
        # 2
        cur_column = 0
        clabels = [_("Location"), _("On Hand"), _("Free To Use"), _("Reserved"), _("Forecast"), _("Incoming"),
            _("Outgoing")]
        for column in clabels:
            worksheet.write(0, cur_column, column, styles.get("main_header_style"))
            # 2.1
            col_letter = chr(cur_column + 97).upper()
            column_width = cur_column == 0 and 60 or 14
            worksheet.set_column("{c}:{c}".format(c=col_letter), column_width)
            cur_column += 1
        # 3
        elements = self.location_ids.action_prepare_elements_for_hierarchy()
        row = 1
        for loc in elements:
            spaces = ""
            level = loc.get("level")
            itera = 0
            while itera != level:
                spaces += "    "
                itera += 1
            instance = (
                spaces + loc.get("name"),
                loc.get("qty_available"),
                loc.get("free_qty"),
                loc.get("reserved_qty"),
                loc.get("virtual_available"),
                loc.get("incoming_qty"),
                loc.get("outgoing_qty"),
            )
            for counter, column in enumerate(instance):
                value = column
                worksheet.write(
                    row,
                    counter,
                    value,
                    styles.get("main_data_style")
                )
            row += 1
        workbook.close()
        # 4
        with open(file_path, "rb") as r:
            xls_file = base64.b64encode(r.read())
        att_vals = {
            "name":  u"{}#{}.xlsx".format(self.name, fields.Date.today()),
            "type": "binary",
            "datas": xls_file,
        }
        attachment_id = self.env["ir.attachment"].create(att_vals)
        self.env.cr.commit()
        action = {
            "type": "ir.actions.act_url",
            "url": "/web/content/{}?download=true".format(attachment_id.id),
            "target": "new",
        }
        return action

    def _compute_quantities_dict(self):
        """
        Fully re-write to add free_qty

        Methods:
         * _get_sbl_qty of product.product
        """
        variants_available = self.mapped("product_variant_ids")._get_sbl_qty()
        prod_available = {}
        for template in self:
            qty_available = 0
            virtual_available = 0
            incoming_qty = 0
            outgoing_qty = 0
            free_qty = 0
            for p in template.product_variant_ids:
                qty_available += variants_available[p.id]["qty_available"]
                virtual_available += variants_available[p.id]["virtual_available"]
                incoming_qty += variants_available[p.id]["incoming_qty"]
                outgoing_qty += variants_available[p.id]["outgoing_qty"]
                free_qty += variants_available[p.id]["free_qty"]
            prod_available[template.id] = {
                "qty_available": qty_available,
                "virtual_available": virtual_available,
                "incoming_qty": incoming_qty,
                "outgoing_qty": outgoing_qty,
                "free_qty": free_qty,
            }
        return prod_available

    def _get_sbl_qty(self):
        """
        The method to get dict of various product qty

        Methods:
         * _compute_quantities_dict
        """
        return self._compute_quantities_dict()
