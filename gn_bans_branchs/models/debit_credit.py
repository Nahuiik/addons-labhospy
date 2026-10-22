# -*- coding: utf-8 -*-
from odoo import api, models


class DebitCredit(models.Model):
    _inherit = "debit.credit"

    def _branch_bank_distribution(self):
        """Distribución analítica configurada en la sucursal del documento."""
        self.ensure_one()
        return self.branch_id.bank_analytic_distribution if self.branch_id else False

    def _apply_branch_analytic_to_lines(self):
        """Rellena la analítica de las líneas vacías con la de la sucursal.

        No sobrescribe la analítica capturada manualmente (distribución o
        cuenta analítica) en una línea. La analítica nunca es obligatoria.
        """
        for record in self:
            distribution = record._branch_bank_distribution()
            if not distribution:
                continue
            for line in record.debit_line_ids:
                if not line.analytic_distribution and not line.analytic_account_id:
                    line.analytic_distribution = distribution

    @api.onchange("branch_id")
    def _onchange_branch_id_bank_analytic(self):
        """Al elegir la sucursal, sugerir su analítica en las líneas vacías."""
        distribution = self._branch_bank_distribution()
        if not distribution:
            return
        for line in self.debit_line_ids:
            if not line.analytic_distribution and not line.analytic_account_id:
                line.analytic_distribution = distribution

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._apply_branch_analytic_to_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "branch_id" in vals or "debit_line_ids" in vals:
            self._apply_branch_analytic_to_lines()
        return res
