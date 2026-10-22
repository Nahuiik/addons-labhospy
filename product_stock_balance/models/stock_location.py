# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class stock_location(models.Model):
    """
    Overwrite to add calculate for products
    """
    _inherit = "stock.location"
    _qty_fields = ("qty_available", "free_qty", "reserved_qty", "virtual_available", "incoming_qty", "outgoing_qty")

    @api.depends_context("product_id", "template_id")
    def _compute_qty_available(self):
        """
        Compute method for qty_available, virtual_available, incoming_qty, outgoing_qty, free_qty, reserved_qty
        The method depends on current context: which product comes (it might be either a product variant or a product
        template)

        Methods:
         * _get_sbl_qty of product.product or product.template
        """
        ctx = self.env.context
        product_id = ctx.get("product_id")
        template_id = ctx.get("template_id")
        if product_id or template_id:
            source = self.env["product.{}".format("product" if product_id else "template")].browse(
                product_id if product_id else template_id
            )
            for rec in self:
                by_locations = source.with_context(location=[rec.id])._get_sbl_qty().get(source.id)
                for field in self._qty_fields:
                    if field != "reserved_qty":
                        rec.__setattr__(field, by_locations.get(field))
                else:
                    rec.__setattr__("reserved_qty", rec.qty_available - rec.free_qty)
        else:
            for rec in self:
                for field in self._qty_fields:
                    rec.__setattr__(field, 0)

    qty_available = fields.Float(
        string="Quantity On Hand",
        compute=_compute_qty_available,
        help="Quantity On Hand for product specified on the context",
        digits="Product Unit of Measure",
    )
    virtual_available = fields.Float(
        string="Forecast Quantity",
        compute=_compute_qty_available,
        help="Forecast Quantity for product specified on the context",
        digits="Product Unit of Measure",
    )
    incoming_qty = fields.Float(
        string="Incoming",
        compute=_compute_qty_available,
        help="Incoming for product specified on the context",
        digits="Product Unit of Measure",
    )
    outgoing_qty = fields.Float(
        string="Outgoing",
        compute=_compute_qty_available,
        help="Outgoing for product specified on the context",
        digits="Product Unit of Measure",
    )
    free_qty = fields.Float(
        string="Free To Use Quantity",
        compute=_compute_qty_available,
        help="Free to use for product specified on the context",
        digits="Product Unit of Measure",
    )
    reserved_qty = fields.Float(
        string="Reserved Quantity",
        compute=_compute_qty_available,
        help="Reserved for product specified on the context",
        digits="Product Unit of Measure",
    )

    def action_prepare_elements_for_hierarchy(self):
        """
        The method which returns hierarchy of locations based on this locations dict

        1. Filter inviable (zero-inventory) locations
        2. Get all missing parents. They might miss for 2 reasons:
           * A user doesn't have access to this location. That's why we are under sudo()
           * It is a view location. We do not pass view locations, since they might relate
             to virtual or partner locations
           Now as location_ids we have all locations to show (union of stated locations and missing parents)
        3. Build hierachy of locations with levels and calculated inventories.
           The latter is needed since virtual parents should reflect inventories of its childred

        Methods:
         * _return_parent_ids
         * _parse_hierarchy

        Returns:
         * list of dicts - sorted by parents
           ** id
           ** name
           ** qty_available
           ** free_qty
           ** reserved_qty
           ** virtual_available
           ** incoming_qty
           ** outgoing_qty
           ** location_id - the parent
           ** level - level of hierarchy for interface purposes
           ** no_children - boolean (whether this location has shown children)
        """
        read_elements = self.read(fields=["id", "name"] + list(self._qty_fields))
        # 1
        clean_elements = []
        for elem in read_elements:
            for qty_field in self._qty_fields:
                if elem.get(qty_field) != 0:
                    clean_elements.append(elem)
                    break
        # 2
        element_ids = [elem["id"] for elem in clean_elements]
        location_ids = self.env["stock.location"].browse(element_ids)
        parent_ids = self.env["stock.location"]
        for location in location_ids:
            parent_ids = parent_ids | location.sudo()._return_parent_ids()
        location_ids = parent_ids | location_ids
        # 3
        new_elements = list(reversed(location_ids.sudo()._parse_hierarchy(clean_elements=clean_elements)))
        return new_elements

    @api.model
    def action_get_settings(self):
        """
        The method to get max level to be expanded and precision for rounding

        Returns:
         * int
        """
        ICPSudo = self.env["ir.config_parameter"].sudo()
        max_level = int(ICPSudo.get_param("product_stock_balance_default_levels", default="3")) - 1
        show_dates = safe_eval(ICPSudo.get_param("product_stock_balance_dates", default="False"))
        allow_export = safe_eval(ICPSudo.get_param("product_stock_balance_export", default="False"))
        show_total = safe_eval(ICPSudo.get_param("product_stock_balance_total", default="False"))
        settings_num = len([setting for setting in [show_dates, allow_export, show_total] if setting])
        return {
            "max_level": max_level >= 0 and max_level or 0,
            "show_dates": show_dates,
            "allow_export": allow_export,
            "show_total": show_total,
            "columns": settings_num and 12 / settings_num or 12,
        }

    @api.model
    def action_get_decimal_precision(self):
        """
        The method to get decimal points

        Returns:
         * int
        """
        return self.env["decimal.precision"].precision_get("Product Unit of Measure")

    def _return_parent_ids(self):
        """
        Method helper to return all parent location of this recursively

        Returns:
         * stock.location rerordset

        Extra info:
         * Expected singleton
        """
        parent_ids = self.env["stock.location"]
        if self.location_id:
            parent_ids += self.location_id
            parent_ids += self.location_id._return_parent_ids()
        return parent_ids

    def _parse_hierarchy(self, clean_elements):
        """
        Method helper to return location values in simple-parser format

        Args:
         * clean_elements - list of dicts (look at action_prepare_elements_for_hierarchy "elements")

        Methods:
         * _prepare_vals_recursively

        Returns:
         * list of dicts
           ** id
           ** name
           ** qty_available
           ** virtual_available
           ** incoming_qty
           ** outgoing_qty
           *** location - the parent
           *** level - level of hierarchy for interface purposes
           *** no_children - boolean (whether this location has shown children)
        """
        res = []
        no_parent_location_ids = self.filtered(lambda loc: not loc.location_id)
        for parent in no_parent_location_ids:
            res += parent._prepare_vals_recursively(clean_elements=clean_elements, permitted_locations=self)
        return res

    def _prepare_vals_recursively(self, clean_elements, permitted_locations, level=0):
        """
        Method helper to parse value for each location recursively
        We firstly go thorugh children, since we need to accumulate values for parents. That's why the list should be
        reversed to use

        Args:
         * clean_elements - list of dicts (the same format as _parse_hierarchy returns)
         * permitted_locations - stock.location recordset  (locations which we really need to consider)
         * level - int

        Methods:
         * _return_inventory_level()

        Returns:
         * list of dicts
           ** id
           ** name
           ** qty_available
           ** virtual_available
           ** incoming_qty
           ** outgoing_qty
           *** location - the parent
           *** level - level of hierarchy for interface purposes
           *** no_children - boolean (whether this location has shown children)

        Extra info:
         * Expected singleton
        """
        child_location_ids = permitted_locations.filtered(lambda loc: loc.location_id.id == self.id)
        res = []
        for child in child_location_ids:
            res += child._prepare_vals_recursively(
                clean_elements=clean_elements,
                permitted_locations=permitted_locations,
                level=level+1,
        )
        # 1
        own_values = self._return_inventory_level(
            clean_elements=clean_elements,
            child_res=res,
            level=level,
        )
        res.append(own_values)
        return res

    def _return_inventory_level(self, clean_elements, child_res, level):
        """
        Method to define inventory level. There are 2 ways:
         1. Either we take it from js already
         2. Or we should calculate sum of child params, since this location was not on form yet

        Args:
         * clean_elements - list of dicts (the same format as _parse_hierarchy returns)
         * child_res - values of prepared children (the same format as _parse_hierarchy returns)
         * level - int

        Returns:
         * dict
           ** id
           ** name
           ** qty_available
           ** virtual_available
           ** incoming_qty
           ** outgoing_qty
           *** location - the parent
           *** level - level of hierarchy for interface purposes
           *** no_children - boolean (whether this location has shown children)

        Extra info:
         * Expected singleton
        """
        value = {
            "location_id": self.location_id.id,
            "level": level,
            "no_children": len(child_res) == 0 and True or False,
        }
        existing_elements = [elem for elem in clean_elements if elem.get("id") == self.id]
        # 1
        if len(existing_elements) > 0:
            value.update(existing_elements[0])
        # 2
        else:
            value.update({
                "id": self.id,
                "name": self.name,
            })
            child_elements = [elem for elem in child_res if elem.get("location_id") == self.id]
            for qty_field in self._qty_fields:
                value[qty_field] = 0

            for elem in child_elements:
                for qty_field in self._qty_fields:
                    value[qty_field] += elem.get(qty_field, 0)
        return value
