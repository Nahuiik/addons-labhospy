# -*- coding: utf-8 -*-
# © 2026 Grupo Nahuiik
# License: LGPL-3

from odoo import api, fields, models


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    structure_country_code = fields.Char(
        related="structure_id.country_id.code",
        string="País estructura (código)",
        readonly=True,
    )

    send_payslip_email_on_validate = fields.Boolean(
        string="Correo al validar recibos",
        default=True,
        help="Si está activo, al confirmar el lote y generarse los PDF de los recibos se envía el "
        "correo estándar de nuevo recibo a cada empleado. Desactívelo para este lote si no deben "
        "recibir correo.",
    )

    def _gn_sync_send_email_from_period(self):
        """Copia el valor desde la quincena SV/HN al enlazar o cambiar el período."""
        for run in self:
            period = False
            if "payroll_period_id" in run._fields and run.payroll_period_id:
                period = run.payroll_period_id
            elif "l10n_sv_payroll_period_id" in run._fields and run.l10n_sv_payroll_period_id:
                period = run.l10n_sv_payroll_period_id
            if period and hasattr(period, "send_payslip_email_on_validate"):
                val = period.send_payslip_email_on_validate
                if run.send_payslip_email_on_validate != val:
                    super(HrPayslipRun, run).write(
                        {"send_payslip_email_on_validate": val}
                    )

    @api.model_create_multi
    def create(self, vals_list):
        runs = super().create(vals_list)
        runs._gn_sync_send_email_from_period()
        return runs

    def write(self, vals):
        res = super().write(vals)
        if any(
            k in vals
            for k in ("payroll_period_id", "l10n_sv_payroll_period_id")
        ):
            self._gn_sync_send_email_from_period()
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Structure = self.env["hr.payroll.structure"]
        if "structure_id" not in fields_list or res.get("structure_id"):
            return res
        if "is_default" not in Structure._fields:
            return res

        cid = res.get("company_id")
        if not cid:
            cid = self.env.company.id
        elif isinstance(cid, (list, tuple)):
            # Comandos Many2one en algunos contextos
            if cid and cid[0] == 6 and len(cid) == 3 and cid[2]:
                cid = cid[2][0]
            else:
                cid = self.env.company.id

        dom_base = [("active", "=", True), ("is_default", "=", True)]
        struct = Structure.search(dom_base + [("company_id", "=", cid)], limit=1)
        if not struct:
            struct = Structure.search(dom_base + [("company_id", "=", False)], limit=1)
        if struct:
            res["structure_id"] = struct.id
            if "schedule_pay" in fields_list and struct.type_id:
                res["schedule_pay"] = struct.type_id.default_schedule_pay
        return res
