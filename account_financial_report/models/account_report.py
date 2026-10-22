from odoo import models


class AccountReport(models.AbstractModel):
    _inherit = "account.report"

    def _unlink_if_no_variant(self):
        """Allow transient account reports to vacuum their variants safely."""
        if getattr(self, "_transient", False):
            self.variant_report_ids.unlink()
            return
        return super()._unlink_if_no_variant()
